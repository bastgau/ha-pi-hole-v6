"""Pi-hole V6 API client for authentication, data retrieval, and blocking management."""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
import ipaddress
import json
import logging
import math
from socket import gaierror
import time
from typing import Any, cast

from aiohttp import (
    ClientConnectorCertificateError,
    ClientError,
    ClientResponse,
    ContentTypeError,
    Fingerprint,
    ServerFingerprintMismatch,
    client,
)

from .const import (
    ACCESS_APP_NO_SUDO,
    ACCESS_APP_SUDO,
    ACCESS_MAIN_PASSWORD,
    ACCESS_RESTRICTED,
    MAX_NETWORK_DEVICES,
    PRIVACY_LEVELS,
)
from .exceptions import (
    AbortLogoutError,
    APIError,
    BadRequestError,
    CertificateChangedError,
    CertificateError,
    ClientConnectorError,
    DataStructureError,
    ForbiddenError,
    MethodNotAllowedError,
    NotFoundError,
    QueryLogUnavailableError,
    UnauthorizedError,
    handle_status,
)

_LOGGER = logging.getLogger(__name__)

# Reading of the query log (GET /queries), used to detect the arrival of a device faster.
QUERY_LOG_PAGE_SIZE = 1000
QUERY_LOG_MAX_PAGES = 3
# Refusals that mean the query log cannot be used: the caller handles them, they are not logged as errors.
_QUERY_LOG_EXPECTED_ERRORS: tuple[type[APIError], ...] = (
    ForbiddenError,
    NotFoundError,
    BadRequestError,
    MethodNotAllowedError,
)
QUERY_LOG_ENDPOINT = "get_query_activity"
QUERY_LOG_TIMEOUT_MESSAGE = "timeout"
# Duration allowed to the whole read, every page included, in seconds.
QUERY_LOG_BUDGET_SECONDS = 8.0
QUERY_LOG_PAGE_TIMEOUT_SECONDS = 5.0
# Bounds, in seconds, of the delay taken from a Retry-After header.
RETRY_AFTER_MIN_SECONDS = 1.0
RETRY_AFTER_MAX_SECONDS = 3600.0
# Timeout of an ordinary request, in seconds.
DEFAULT_REQUEST_TIMEOUT_SECONDS = 60.0


@dataclass(frozen=True, slots=True)
class QueryActivity:
    """What the integration keeps from the query log: client addresses and times only, never a domain.

    Attributes:
        last_seen_by_ip (dict[str, float]): Normalized client IP address -> time of its newest query (Pi-hole clock, Unix seconds).
        newest_time (float | None): The newest query time read, None when the window held no usable query.
        pages (int): The number of pages read.
        queries_read (int): The number of rows read (a count only).
        complete (bool): False when the read stopped at the page limit or the time budget.
        duration (float): The duration of the read in seconds, the login included.

    """

    last_seen_by_ip: dict[str, float]
    newest_time: float | None
    pages: int
    queries_read: int
    complete: bool
    duration: float


def normalize_ip(value: object) -> str | None:
    """Normalize an IP address to its compressed form, so two spellings of an address compare equal.

    Args:
        value (object): The value to normalize.

    Returns:
        str | None: The compressed lowercase address, None when the value is not a valid IP address.

    """
    if not isinstance(value, str):
        return None

    try:
        return ipaddress.ip_address(value.strip()).compressed
    except ValueError:
        return None


def _is_hidden_client(address: str) -> bool:
    """Tell whether Pi-hole replaced the address of a client by a placeholder.

    At its privacy level "hide domains and clients", Pi-hole records every client as 0.0.0.0: no device can own such an address.

    Args:
        address (str): A normalized IP address.

    Returns:
        bool: True for an unspecified address (0.0.0.0 or ::).

    """
    return ipaddress.ip_address(address).is_unspecified


def count_hidden_clients(queries: object) -> int:
    """Count the rows of the query log whose client address is hidden by the privacy level of Pi-hole.

    Args:
        queries (object): The "queries" value of a GET /queries response.

    Returns:
        int: The number of rows whose `client.ip` is an unspecified address, 0 when the value is not a list.

    """
    if not isinstance(queries, list):
        return 0

    hidden: int = 0

    for row in cast("list[Any]", queries):
        source: Any = cast("dict[str, Any]", row).get("client") if isinstance(row, dict) else None
        address: str | None = (
            normalize_ip(cast("dict[str, Any]", source).get("ip")) if isinstance(source, dict) else None
        )

        if address is not None and _is_hidden_client(address):
            hidden += 1

    return hidden


def parse_query_activity(queries: object) -> tuple[dict[str, float], int]:
    """Keep the newest query time of each client from the rows of the query log.

    Only `client.ip` and `time` are read: no other field of a row (the domain above all) is looked at or kept. A client whose address is hidden by the privacy level of Pi-hole (0.0.0.0) is skipped, like any row without a usable address.

    Args:
        queries (object): The "queries" value of a GET /queries response.

    Returns:
        tuple[dict[str, float], int]: The newest time per normalized client IP, and the number of rows read. A row that is not a dictionary, with no usable IP or with a time that is not a positive finite number is skipped.

    """
    if not isinstance(queries, list):
        return {}, 0

    rows: list[Any] = cast("list[Any]", queries)
    newest: dict[str, float] = {}

    for row in rows:
        if not isinstance(row, dict):
            continue

        source: Any = cast("dict[str, Any]", row).get("client")
        moment: Any = cast("dict[str, Any]", row).get("time")

        if not isinstance(source, dict):
            continue
        if isinstance(moment, bool) or not isinstance(moment, (int, float)):
            continue
        if not math.isfinite(moment) or moment <= 0:
            continue

        address: str | None = normalize_ip(cast("dict[str, Any]", source).get("ip"))
        if address is None or _is_hidden_client(address):
            continue

        if float(moment) > newest.get(address, 0.0):
            newest[address] = float(moment)

    return newest, len(rows)


def parse_retry_after(value: str | None, now: datetime) -> float | None:
    """Read a Retry-After header, given as a number of seconds or as an HTTP date.

    Args:
        value (str | None): The value of the header, None when absent.
        now (datetime): The current time, used when the header holds a date.

    Returns:
        float | None: The delay in seconds, clamped between 1 and 3600, None when the header is absent or unreadable.

    """
    if value is None or value.strip() == "":
        return None

    delay: float
    try:
        delay = float(value)
    except ValueError:
        try:
            moment: datetime = parsedate_to_datetime(value)
        except (TypeError, ValueError, IndexError):
            return None
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        delay = (moment - now).total_seconds()

    if not math.isfinite(delay):
        return None

    return min(max(delay, RETRY_AFTER_MIN_SECONDS), RETRY_AFTER_MAX_SECONDS)


class Api:  # pylint: disable=too-many-public-methods, too-many-instance-attributes
    """Pi-hole API Client.

    Attributes:
        url (str): The URL of the Pi-hole API endpoint.
        _ssl_kwargs (dict[str, Any]): Extra keyword arguments for every request, carrying the pinned certificate fingerprint when there is one.
        just_initialized (dict[str, bool]): Per coordinator flag indicating the client was just initialized, used to skip the first scheduled data fetch.
        last_refresh (dict[str, datetime]): Timestamp of the last data refresh of each coordinator, keyed by coordinator identifier.
        account_access (str | None): The kind of access of the account used by the integration (ACCESS_* constants), deduced from GET /auth/sessions. None while unknown.
        cache_auth_sessions (list[dict[str, Any]]): Cached list of active authentication sessions.
        cache_blocking (dict[str, Any]): Cached blocking status data.
        cache_configured_clients (list[dict[str, Any]]): Cached list of configured clients.
        cache_dhcp_leases (list[dict[str, Any]]): Cached list of active DHCP leases.
        cache_ftl_info (dict[str, Any]): Cached FTL diagnosis messages and status.
        cache_privacy_level (int | None): Cached privacy level of Pi-hole (0 to 3), None while unknown or when the account is not allowed to read it.
        cache_network_devices (list[dict[str, Any]]): Cached list of known network devices.
        cache_groups (dict[str, dict[str, Any]]): Cached Pi-hole groups indexed by group name.
        cache_padd (dict[str, Any]): Cached Pi-hole dashboard data.
        cache_remaining_dates (dict[str, datetime]): Cached expiration dates for blocking timers.
        cache_summary (dict[str, Any]): Cached Pi-hole activity summary.
        _call_lock (asyncio.Lock): The lock serializing the calls to the API.
        _password (str): The password used to authenticate against the API.
        _session (aiohttp.ClientSession): The HTTP session used to call the API.
        _sid (str | None): The session identifier returned by the API after the authentication.

    """

    def __init__(
        self,
        session: client.ClientSession,
        url: str = "http://pi.hole",
        password: str = "",
        certificate_fingerprint: bytes | None = None,
    ) -> None:
        """Initialize Pi-hole API Client object with an API URL.

        Args:
            session (client.ClientSession): The aiohttp client session used to perform HTTP requests.
            url (str): Represents the URL of API endpoint. Defaults to "http://pi.hole".
            password (str): The password used to authenticate against the Pi-hole API. Defaults to "".
            certificate_fingerprint (bytes | None): The confirmed SHA-256 digest of the Pi-hole certificate. When set, the connection is accepted only if the server presents this certificate, instead of relying on the CA store. Defaults to None.

        """
        self._call_lock = asyncio.Lock()
        self._password: str = password
        self._session: client.ClientSession = session
        # Passed to every request: an empty mapping keeps the session's own verification.
        self._ssl_kwargs: dict[str, Any] = (
            {"ssl": Fingerprint(certificate_fingerprint)} if certificate_fingerprint is not None else {}
        )
        self._sid: str | None = None
        self.url: str = url
        self.account_access: str | None = None

        self.cache_auth_sessions: list[dict[str, Any]] = []
        self.cache_blocking: dict[str, Any] = {}
        self.cache_configured_clients: list[dict[str, Any]] = []
        self.cache_dhcp_leases: list[dict[str, Any]] = []
        self.cache_ftl_info: dict[str, Any] = {}
        self.cache_privacy_level: int | None = None
        self.cache_network_devices: list[dict[str, Any]] = []
        self.cache_groups: dict[str, dict[str, Any]] = {}
        self.cache_padd: dict[str, Any] = {}
        self.cache_remaining_dates: dict[str, datetime] = {}
        self.cache_summary: dict[str, Any] = {}

        self.just_initialized: dict[str, bool] = {}
        self.last_refresh: dict[str, datetime] = {}

    async def _call(  # noqa: PLR0913, PLR0917  # pylint: disable=too-many-branches, too-many-arguments, too-many-positional-arguments, too-many-locals
        self,
        route: str,
        method: str,
        action: str = "",
        data: dict[str, Any] | None = None,
        expected_errors: tuple[type[APIError], ...] = (),
        timeout: float = DEFAULT_REQUEST_TIMEOUT_SECONDS,  # noqa: ASYNC109
        log_body: bool = True,
    ) -> dict[str, Any]:
        """Send HTTP requests with specified method, route, and data.

        Args:
            route (str): Represents the specific endpoint that you want to call.
            method (str): Represents the HTTP method to be used. It can be one of the following: "post", "put", "delete", or "get".
            action (str): Represents the action name requested.
            data (dict[str, Any] | None): Used to pass a dictionary containing data to be sent in the request when making a POST request.
            expected_errors (tuple[type[APIError], ...]): Errors the caller handles itself: they are still raised, but logged at debug level instead of error level.
            timeout (float): Seconds allowed to send the request and get its response. Defaults to 60.
            log_body (bool): Whether the body of the responses is written to the debug log. Pass False for a route whose body must never be logged: only the number of rows of a "queries" list is logged then. Defaults to True.

        Returns:
            dict[str, Any]: A dictionary with keys "code", "reason", and "data".

        Raises:
            ClientConnectorError: If a network-level error occurs (timeout, connection refused, DNS failure).
            CertificateError: If the certificate is not trusted by the CA store and no fingerprint is pinned.
            CertificateChangedError: If the certificate does not match the pinned fingerprint.
            RuntimeError: If the HTTP method is not supported.

        """

        await self._authentification_step_with_lock(action)

        url: str = f"{self.url}{route}"

        headers: dict[str, str] = {
            "accept": "application/json",
            "content-type": "application/json",
        }

        if self._sid is not None and self._sid != "no password set":
            headers = headers | {"sid": self._sid}

        request: ClientResponse

        try:
            method = method.lower()

            async with asyncio.timeout(timeout):
                if method == "post":
                    request = await self._session.post(url, json=data, headers=headers, **self._ssl_kwargs)
                elif method == "put":
                    request = await self._session.put(url, json=data, headers=headers, **self._ssl_kwargs)
                elif method == "delete":
                    request = await self._session.delete(url, headers=headers, **self._ssl_kwargs)
                elif method == "get":
                    request = await self._session.get(url, headers=headers, **self._ssl_kwargs)
                else:
                    msg: str = f"Method ({method}) is not supported/implemented."
                    _LOGGER.critical(msg)
                    raise RuntimeError(msg)

        except ServerFingerprintMismatch as err:
            raise CertificateChangedError from err
        except ClientConnectorCertificateError as err:
            raise CertificateError from err
        except (TimeoutError, ClientError, gaierror) as err:
            raise ClientConnectorError(str(err)) from err

        try:
            handle_status(request.status)
        except APIError as api_error:
            api_error.retry_after = parse_retry_after(request.headers.get("Retry-After"), datetime.now(UTC))
            await self._log_api_error(api_error, request, method, url, expected_errors, log_body=log_body)
            raise

        result_data: dict[str, Any] | None = None

        if request.status < 400 and request.text != "":
            result_data = await self._try_to_retrieve_json_result(request, privacy=False)
            message: str = await self._create_log_message_on_api_result(
                request, method, url, log_body=log_body, parsed=result_data
            )

            if "password incorrect" not in message:
                _LOGGER.debug(message)
            else:
                _LOGGER.error(message)

        return {
            "code": request.status,
            "reason": request.reason,
            "data": result_data,
        }

    async def _log_api_error(  # noqa: PLR0913
        self,
        api_error: APIError,
        request: ClientResponse,
        method: str,
        url: str,
        expected_errors: tuple[type[APIError], ...],
        *,
        log_body: bool = True,
    ) -> None:
        """Keep the body of an error response on the exception, and log the error.

        Args:
            api_error (APIError): The API exception that was raised.
            request (ClientResponse): The HTTP response object associated with the error.
            method (str): The HTTP method used for the request.
            url (str): The URL of the request.
            expected_errors (tuple[type[APIError], ...]): Errors the caller handles itself, logged at debug level instead of error level.
            log_body (bool): Whether the body of the response may be written to the log. Defaults to True.

        """

        log_message: str = await self._create_log_message_on_api_exception(
            api_error, request, method, url, log_body=log_body
        )
        api_error.body = await self._try_to_retrieve_json_result(request)

        if isinstance(api_error, expected_errors):
            _LOGGER.debug(log_message)
        else:
            _LOGGER.error(log_message)

    async def _try_to_retrieve_json_result(
        self,
        request: ClientResponse,
        privacy: bool = True,
    ) -> dict[str, Any] | None:
        """Attempt to parse the JSON body from an HTTP response.

        Handles encoding errors gracefully and optionally redacts the session SID for privacy.

        Args:
            request (ClientResponse): The HTTP response object to parse.
            privacy (bool): If True, redacts the session SID from the result. Defaults to True.

        Returns:
            dict[str, Any] | None: The parsed JSON content, or None if the response has no body.

        Raises:
            json.JSONDecodeError: If the response body cannot be parsed as valid JSON after decoding.

        """

        text: dict[str, Any] | None = None

        try:
            if request.status != 204:
                text = await request.json()
        except UnicodeDecodeError:
            raw_data = await request.read()
            text_data = raw_data.decode(encoding="utf-8", errors="replace")
            text = json.loads(text_data)
        except ContentTypeError:
            pass

        if (
            text is not None
            and privacy is True
            and "session" in text
            and "sid" in text["session"]
            and text["session"]["sid"] is not None
        ):
            text["session"]["sid"] = "[redacted]"

        return text

    async def _create_log_message_on_api_result(
        self,
        request: ClientResponse,
        method: str,
        url: str,
        *,
        log_body: bool = True,
        parsed: dict[str, Any] | None = None,
    ) -> str:
        """Build a log message string from an HTTP response.

        Args:
            request (ClientResponse): The HTTP response object.
            method (str): The HTTP method used for the request.
            url (str): The URL of the request.
            log_body (bool): Whether the body may appear in the message. When False, the message only holds the number of rows of the "queries" list, if there is one. Defaults to True.
            parsed (dict[str, Any] | None): The body when the caller has already parsed it, so it is not parsed again to count its rows. Defaults to None.

        Returns:
            str: A formatted log message containing status, reason, method, URL and response body (or its number of rows).

        """

        status: str = str(request.status)
        reason: str = str(request.reason)

        if not log_body:
            rows: int = 0
            if isinstance(parsed, dict):
                queries: Any = parsed.get("queries")
                rows = len(cast("list[Any]", queries)) if isinstance(queries, list) else 0
            return f"{status} {reason} # {method.upper()} {url} : {rows} rows"

        text: dict[str, Any] | None = await self._try_to_retrieve_json_result(request)

        return f"{status} {reason} # {method.upper()} {url} : {text}"

    async def _create_log_message_on_api_exception(
        self, api_error: APIError, request: ClientResponse, method: str, url: str, *, log_body: bool = True
    ) -> str:
        """Build a log message string from an API exception and its associated HTTP response.

        Args:
            api_error (APIError): The API exception that was raised.
            request (ClientResponse): The HTTP response object associated with the error.
            method (str): The HTTP method used for the request.
            url (str): The URL of the request.
            log_body (bool): Whether the body of the response may appear in the message. Defaults to True.

        Returns:
            str: A formatted log message prefixed with the exception type name.

        """

        log: str = await self._create_log_message_on_api_result(request, method, url, log_body=log_body)
        exception_name: str = str(type(api_error))

        return f"{exception_name} - {log}"

    async def _authentification_step(self, action: str) -> None:
        """Execute the full authentication sequence for a given action.

        Checks current authentication status, aborts logout if not needed,
        and requests a login if no session is active.

        Args:
            action (str): The name of the action being performed, used to determine authentication behavior.

        """
        await self._check_authentification(action)
        await self._abort_logout(action)
        await self._request_login(action)

    async def _authentification_step_with_lock(self, action: str) -> None:
        """Execute the authentication sequence with a lock for non-auth actions.

        Acquires the call lock before running the authentication step to prevent
        concurrent authentication attempts. Auth-related actions bypass the lock.

        Args:
            action (str): The name of the action being performed.

        """

        if action not in ("login", "authentification_status", "logout"):
            try:
                await asyncio.wait_for(self._call_lock.acquire(), timeout=10)

                try:
                    await self._authentification_step(action)
                finally:
                    self._call_lock.release()

            except TimeoutError:
                pass

        else:
            await self._authentification_step(action)

    async def _check_authentification(self, action: str) -> None:
        """Verify the current session is still valid and reset it if not.

        Calls the authentication status endpoint and sets the SID to None
        if the session has expired or become invalid.

        Args:
            action (str): The name of the action being performed, used to skip the check for auth-related actions.

        """

        try:
            if (
                action not in ("login", "authentification_status")
                and self._sid is not None
                and self._sid != "no password set"
            ):
                response: dict[str, Any] = await self.call_authentification_status()

                if response["code"] != 200 or response["data"]["session"]["valid"] is False:
                    self._sid = None

        except UnauthorizedError:
            self._sid = None

    async def _request_login(self, action: str) -> None:
        """Request a login if no active session exists.

        Triggers a login call when the action is not already a login
        and no session ID is currently set.

        Args:
            action (str): The name of the action being performed.

        """

        if action != "login" and self._sid is None:
            await self.call_login()

    async def _abort_logout(self, action: str) -> None:
        """Abort a logout call if no active session exists.

        Raises AbortLogoutError when a logout is requested but there is
        no active session to terminate.

        Args:
            action (str): The name of the action being performed.

        Raises:
            AbortLogoutError: If a logout is attempted with no active session.

        """

        if action == "logout" and (self._sid is None or self._sid == "no password set"):
            raise AbortLogoutError

    async def call_authentification_status(self) -> dict[str, Any]:
        """Retrieve the current authentication session status.

        The errors of the underlying call propagate unchanged: APIError (if the API returns an error status code), ClientConnectorError (if the server is unreachable).

        Returns:
            dict[str, Any]: A dictionary with the keys "code", "reason", and "data".

        """

        url: str = "/auth"

        result: dict[str, Any] = await self._call(
            url,
            action="authentification_status",
            method="GET",
        )

        return {
            "code": result["code"],
            "reason": result["reason"],
            "data": result["data"],
        }

    async def call_login(self) -> dict[str, Any]:
        """Authenticate against the Pi-hole API using the configured password.

        The errors of the underlying call propagate unchanged: APIError (if the API returns an error status code).

        Returns:
            dict[str, Any]: A dictionary with the keys "code", "reason", and "data".

        Raises:
            UnauthorizedError: If the password is incorrect or the session is invalid.

        """

        url: str = "/auth"

        result: dict[str, Any] = await self._call(
            url,
            action="login",
            method="POST",
            data={"password": self._password},
        )

        if result["data"]["session"]["valid"] is False or result["data"]["session"]["message"] == "password incorrect":
            raise UnauthorizedError

        if result["data"]["session"]["sid"] is not None:
            self._sid = result["data"]["session"]["sid"]
        else:
            self._sid = "no password set"

        return {
            "code": result["code"],
            "reason": result["reason"],
            "data": result["data"],
        }

    async def call_logout(self) -> dict[str, Any]:
        """Drop the current session.

        The errors of the underlying call propagate unchanged: APIError (if the API returns an error status code during logout).

        Returns:
            dict[str, Any]: A dictionary with the keys "code", "reason", and "data".

        """

        url: str = "/auth"

        result: dict[str, Any] = {"code": None, "reason": None, "data": {}}

        try:
            result = await self._call(
                url,
                action="logout",
                method="DELETE",
            )

            self._sid = None

        except AbortLogoutError as err:
            result["code"] = err.code
            result["reason"] = err.reason

        return {
            "code": result["code"],
            "reason": result["reason"],
            "data": result["data"],
        }

    async def call_summary(self) -> dict[str, Any]:
        """Retrieve an overview of Pi-hole activity.

        The errors of the underlying call propagate unchanged: APIError (if the API returns an error status code), ClientConnectorError (if the server is unreachable).

        Returns:
            dict[str, Any]: A dictionary with the keys "code", "reason", and "data".

        """

        url: str = "/stats/summary"

        result: dict[str, Any] = await self._call(
            url,
            action="summary",
            method="GET",
        )

        self.cache_summary = result["data"]

        return {
            "code": result["code"],
            "reason": result["reason"],
            "data": result["data"],
        }

    async def call_padd(self, full: bool = True) -> dict[str, Any]:
        """Retrieve the Pi-hole API Dashboard information.

        The errors of the underlying call propagate unchanged: APIError (if the API returns an error status code), ClientConnectorError (if the server is unreachable).

        Args:
            full (bool): If True, retrieves the full dashboard data. Defaults to True.

        Returns:
            dict[str, Any]: A dictionary with the keys "code", "reason", and "data".

        """

        url: str = f"/padd?full={str(full).lower()}"

        result: dict[str, Any] = await self._call(
            url,
            action="padd",
            method="GET",
        )

        self.cache_padd = result["data"]

        return {
            "code": result["code"],
            "reason": result["reason"],
            "data": result["data"],
        }

    def cpu_temperature_report(self) -> dict[str, Any] | None:
        """Return the temperature data as Pi-hole reports it, for the attributes of the sensor.

        Only the hot limit and the unit are kept: the temperature is already the state of the sensor, and the other entries of the "sensors" object (the list of probes) stay out.

        Returns:
            dict[str, Any] | None: The "hot_limit" and "unit" entries that Pi-hole gave, None when the padd cache holds neither.

        """
        padd: Any = self.cache_padd
        sensors: Any = cast("dict[str, Any]", padd).get("sensors") if isinstance(padd, dict) else None

        if not isinstance(sensors, dict):
            return None

        report: dict[str, Any] = {
            key: value for key, value in cast("dict[str, Any]", sensors).items() if key in ("hot_limit", "unit")
        }

        return report or None

    def cpu_temperature_celsius(self) -> float | None:
        """Return the CPU temperature of the Pi-hole host converted to °C.

        Read from the "sensors" object of the padd cache: no request is made. Pi-hole already converts
        the value to the unit it is configured with ("C", "F" or "K"), which is converted back here.

        Returns:
            float | None: The temperature in °C, or None when Pi-hole does not report one (no probe, a value that is not a finite number, an unknown unit or an unexpected shape).

        """
        padd: Any = self.cache_padd
        sensors: Any = cast("dict[str, Any]", padd).get("sensors") if isinstance(padd, dict) else None

        if not isinstance(sensors, dict):
            return None

        value: Any = sensors.get("cpu_temp")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            return None

        unit: str = str(sensors.get("unit", "C")).upper()  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]

        if unit == "C":
            return float(value)
        if unit == "F":
            return (value - 32) / 1.8
        if unit == "K":
            return value - 273.15

        _LOGGER.debug("Unknown temperature unit reported by Pi-hole: %s", unit)
        return None

    @property
    def privacy_level(self) -> str | None:
        """Return the privacy level of Pi-hole as the state of its sensor.

        Returns:
            str | None: One of PRIVACY_LEVELS, None while the level is unknown or not readable.

        """
        level: int | None = self.cache_privacy_level

        if level is None or not 0 <= level < len(PRIVACY_LEVELS):
            return None

        return PRIVACY_LEVELS[level]

    async def call_get_privacy_level(self) -> dict[str, Any]:
        """Retrieve the privacy level of Pi-hole.

        A refusal of the route (403, or 404 on an older Pi-hole) is not an error here: it is logged at debug level and the level becomes unknown. A body that does not hold a level from 0 to 3 gives an unknown level too.

        The other errors of the underlying call propagate unchanged: APIError (if the API returns another error status code), ClientConnectorError (if the server is unreachable).

        Returns:
            dict[str, Any]: A dictionary with the keys "code", "reason", and "data".

        """

        url: str = "/config/misc/privacylevel"

        try:
            result: dict[str, Any] = await self._call(
                url,
                action="privacy_level",
                method="GET",
                expected_errors=(ForbiddenError, NotFoundError),
            )
        except (ForbiddenError, NotFoundError) as err:
            self.cache_privacy_level = None

            return {"code": 403 if isinstance(err, ForbiddenError) else 404, "reason": "Refused", "data": {}}

        self.cache_privacy_level = self._read_privacy_level(result["data"])

        return {
            "code": result["code"],
            "reason": result["reason"],
            "data": result["data"],
        }

    @staticmethod
    def _read_privacy_level(data: Any) -> int | None:
        """Read the level from the body of GET /config/misc/privacylevel.

        Args:
            data (Any): The body of the response, expected as {"config": {"misc": {"privacylevel": <0 to 3>}}}.

        Returns:
            int | None: The level, None when the body does not hold an integer from 0 to 3.

        """
        node: Any = data

        for key in ("config", "misc", "privacylevel"):
            if not isinstance(node, dict):
                return None

            node = cast("dict[str, Any]", node).get(key)

        if isinstance(node, bool) or not isinstance(node, int) or not 0 <= node < len(PRIVACY_LEVELS):
            return None

        return node

    async def call_get_auth_sessions(self) -> dict[str, Any]:
        """Retrieve all active sessions, and use the outcome to detect the kind of access of the account.

        Pi-hole refuses the route (403) to an application session without `webserver.api.app_sudo`. That refusal is not an error here: it is logged at debug level, the sessions cache is emptied and `account_access` is deduced from it (see `_detect_access_from_refusal`). When the call succeeds, `account_access` is deduced from the `app` flag of the current session.

        The other errors of the underlying call propagate unchanged: APIError (if the API returns another error status code), ClientConnectorError (if the server is unreachable).

        Returns:
            dict[str, Any]: A dictionary with the keys "code", "reason", and "data".

        """

        url: str = "/auth/sessions"

        try:
            result: dict[str, Any] = await self._call(
                url,
                action="auth_sessions",
                method="GET",
                expected_errors=(ForbiddenError,),
            )
        except ForbiddenError as err:
            self.account_access = self._detect_access_from_refusal(err)
            self.cache_auth_sessions = []

            return {"code": 403, "reason": "Forbidden", "data": {}}

        self.cache_auth_sessions = result["data"]["sessions"]
        self.account_access = self._detect_access_from_sessions(self.cache_auth_sessions)

        return {
            "code": result["code"],
            "reason": result["reason"],
            "data": result["data"],
        }

    @staticmethod
    def _detect_access_from_refusal(error: ForbiddenError) -> str:
        """Deduce the kind of access from a 403 returned by GET /auth/sessions.

        The refusal text of Pi-hole names `webserver.api.app_sudo` when the cause is an application session without that setting. The text is only used to refine the analysis: without it, the refusal stays a generic restriction.

        Args:
            error (ForbiddenError): The refusal, carrying the body of the response when there was one.

        Returns:
            str: ACCESS_APP_NO_SUDO if the refusal mentions app_sudo, ACCESS_RESTRICTED otherwise.

        """

        if "app_sudo" in str(error.body):
            return ACCESS_APP_NO_SUDO

        return ACCESS_RESTRICTED

    @staticmethod
    def _detect_access_from_sessions(sessions: list[dict[str, Any]]) -> str | None:
        """Deduce the kind of access from the current session in the list of sessions.

        Args:
            sessions (list[dict[str, Any]]): The sessions returned by GET /auth/sessions.

        Returns:
            str | None: ACCESS_APP_SUDO if the current session is an application one, ACCESS_MAIN_PASSWORD if not, None if the current session is not in the list.

        """

        for session in sessions:
            if session.get("current_session") is True:
                return ACCESS_APP_SUDO if session.get("app") is True else ACCESS_MAIN_PASSWORD

        return None

    async def call_blocking_status(self) -> dict[str, Any]:
        """Retrieve current blocking status.

        The errors of the underlying call propagate unchanged: APIError (if the API returns an error status code), ClientConnectorError (if the server is unreachable).

        Returns:
            dict[str, Any]: A dictionary with the keys "code", "reason", and "data".

        """

        url: str = "/dns/blocking"

        result: dict[str, Any] = await self._call(
            url,
            action="blocking_status",
            method="GET",
        )

        self.cache_blocking = result["data"]

        return {
            "code": result["code"],
            "reason": result["reason"],
            "data": result["data"],
        }

    async def call_blocking_enabled(self) -> dict[str, Any]:
        """Enable blocking for DNS requests.

        The errors of the underlying call propagate unchanged: APIError (if the API returns an error status code), ClientConnectorError (if the server is unreachable).

        Returns:
            dict[str, Any]: A dictionary with the keys "code", "reason", and "data".

        """

        url: str = "/dns/blocking"

        result: dict[str, Any] = await self._call(
            url,
            action="blocking_enabled",
            method="POST",
            data={"blocking": True, "timer": None},
        )

        self.cache_blocking = result["data"]

        return {
            "code": result["code"],
            "reason": result["reason"],
            "data": result["data"],
        }

    async def call_blocking_disabled(self, duration: int | None) -> dict[str, Any]:
        """Disable blocking for DNS requests.

        The errors of the underlying call propagate unchanged: APIError (if the API returns an error status code), ClientConnectorError (if the server is unreachable).

        Args:
            duration (int | None): The time duration in seconds for which blocking will be disabled. Pass None to disable indefinitely.

        Returns:
            dict[str, Any]: A dictionary with the keys "code", "reason", and "data".

        """

        timer: int = 0

        if duration is not None:
            timer = duration

        url: str = "/dns/blocking"

        result: dict[str, Any] = await self._call(
            url,
            action="blocking_disabled",
            method="POST",
            data={"blocking": False, "timer": timer},
        )

        self.cache_blocking = result["data"]

        return {
            "code": result["code"],
            "reason": result["reason"],
            "data": result["data"],
        }

    async def call_get_ftl_info_messages(self) -> dict[str, Any]:
        """Retrieve the list of FTL diagnosis messages.

        The errors of the underlying call propagate unchanged: APIError (if the API returns an error status code), ClientConnectorError (if the server is unreachable).

        Returns:
            dict[str, Any]: A dictionary with the keys "code", "reason", and "data".

        """

        url: str = "/info/messages"

        result: dict[str, Any] = await self._call(
            url,
            action="ftl_info_messages",
            method="GET",
        )

        self.cache_ftl_info["message_list"] = result["data"]["messages"]
        self.cache_ftl_info["status"] = "OK: Messages fetched successfully"

        return {
            "code": result["code"],
            "reason": result["reason"],
            "data": result["data"],
        }

    async def call_get_ftl_info_messages_count(self) -> dict[str, Any]:
        """Retrieve the count of FTL diagnosis messages.

        The errors of the underlying call propagate unchanged: APIError (if the API returns an error status code), ClientConnectorError (if the server is unreachable).

        Returns:
            dict[str, Any]: A dictionary with the keys "code", "reason", and "data".

        """

        url: str = "/info/messages/count"

        result: dict[str, Any] = await self._call(
            url,
            action="ftl_info_messages_count",
            method="GET",
        )

        self.cache_ftl_info["message_count"] = result["data"]["count"]

        return {
            "code": result["code"],
            "reason": result["reason"],
            "data": result["data"],
        }

    async def call_get_groups(self) -> dict[str, Any]:
        """Retrieve the list of Pi-hole groups.

        The errors of the underlying call propagate unchanged: APIError (if the API returns an error status code), ClientConnectorError (if the server is unreachable).

        Returns:
            dict[str, Any]: A dictionary with the keys "code", "reason", and "data".

        """

        url: str = "/groups"

        result: dict[str, Any] = await self._call(
            url,
            action="groups",
            method="GET",
        )

        self.cache_groups = {}

        for group in result["data"]["groups"]:
            self.cache_groups[group["name"]] = {
                "name": group["name"],
                "comment": group["comment"],
                "enabled": group["enabled"],
                "id": group["id"],
            }

        return {
            "code": result["code"],
            "reason": result["reason"],
            "data": result["data"],
        }

    async def call_get_configured_clients(self) -> dict[str, Any]:
        """Retrieve the configured clients.

        The errors of the underlying call propagate unchanged: APIError (if the API returns an error status code), ClientConnectorError (if the server is unreachable).

        Returns:
            dict[str, Any]: A dictionary with the keys "code", "reason", and "data".

        """

        url: str = "/clients"

        result: dict[str, Any] = await self._call(
            url,
            action="configured_clients",
            method="GET",
        )

        self.cache_configured_clients = result["data"]["clients"]

        return {
            "code": result["code"],
            "reason": result["reason"],
            "data": result["data"],
        }

    async def call_get_dhcp_leases(self) -> dict[str, Any]:
        """Retrieve the active DHCP leases.

        The errors of the underlying call propagate unchanged: APIError (if the API returns an error status code), ClientConnectorError (if the server is unreachable).

        Returns:
            dict[str, Any]: A dictionary with the keys "code", "reason", and "data".

        """

        url: str = "/dhcp/leases"

        result: dict[str, Any] = await self._call(
            url,
            action="dhcp_leases",
            method="GET",
        )

        self.cache_dhcp_leases = result["data"]["leases"]

        return {
            "code": result["code"],
            "reason": result["reason"],
            "data": result["data"],
        }

    async def call_get_network_devices(
        self, max_devices: int = MAX_NETWORK_DEVICES, max_addresses: int | None = None
    ) -> dict[str, Any]:
        """Retrieve the list of known network devices.

        The errors of the underlying call propagate unchanged: APIError (if the API returns an error status code), ClientConnectorError (if the server is unreachable).

        Args:
            max_devices (int): The maximum number of devices to retrieve. Defaults to MAX_NETWORK_DEVICES.
            max_addresses (int | None): The maximum number of addresses to retrieve per device. None (default) leaves the parameter out, so Pi-hole answers with its own default of 3.

        Returns:
            dict[str, Any]: A dictionary with the keys "code", "reason", and "data".

        """

        url: str = f"/network/devices?max_devices={max_devices}"
        if max_addresses is not None:
            url = f"{url}&max_addresses={max_addresses}"

        result: dict[str, Any] = await self._call(
            url,
            action="network_devices",
            method="GET",
        )

        self.cache_network_devices = result["data"]["devices"]

        return {
            "code": result["code"],
            "reason": result["reason"],
            "data": result["data"],
        }

    async def call_get_query_activity(  # pylint: disable=too-many-locals,missing-raises-doc
        self,
        since: float,
        *,
        page_size: int = QUERY_LOG_PAGE_SIZE,
        max_pages: int = QUERY_LOG_MAX_PAGES,
        budget: float = QUERY_LOG_BUDGET_SECONDS,
    ) -> QueryActivity:
        """Read the time of the latest query of each client, from the query log of the Pi-hole.

        The queries made since `since` (Pi-hole clock) are read newest first. The first page is GET /queries?from=..&length=..; the next ones repeat it with the cursor of the first page and a `start` offset, which is how Pi-hole paginates (the cursor alone gives the same page again). The domains travel in the responses but nothing is kept besides the client addresses and times, no cache is filled and the body of the responses is never logged. No filter (domain, client...) is sent.

        It raises QueryLogUnavailableError when the first page comes without cursor (Pi-hole records nothing, privacy level "anonymous") or when the queries read only hold hidden clients (0.0.0.0, privacy level "hide domains and clients"), DataStructureError when a response is not made as expected and ClientConnectorError when the first page times out or the server is unreachable. The other errors of the underlying call propagate unchanged (APIError, CertificateError, CertificateChangedError). The read stops at a page shorter than `page_size` (complete), at `max_pages` or when the time `budget` is spent (incomplete). A timeout on a page after the first ends the read as incomplete.

        Args:
            since (float): The start of the window, as a Pi-hole Unix time in seconds.
            page_size (int): The number of rows asked per page. Defaults to QUERY_LOG_PAGE_SIZE.
            max_pages (int): The maximum number of pages to read. Defaults to QUERY_LOG_MAX_PAGES.
            budget (float): The seconds allowed to the whole read, every page included. Defaults to QUERY_LOG_BUDGET_SECONDS.

        Returns:
            QueryActivity: The newest query time per client address, with the counters of the read.

        Raises:
            QueryLogUnavailableError: If the queries read only hold hidden clients (0.0.0.0).

        """

        started: float = time.monotonic()
        newest: dict[str, float] = {}
        queries_read: int = 0
        hidden_clients: int = 0
        pages: int = 0
        complete: bool = False
        cursor: int | None = None

        while pages < max_pages:
            remaining: float = budget - (time.monotonic() - started)
            if remaining <= 0 < pages:
                break

            route: str = f"/queries?from={since:.3f}&length={page_size}"
            if cursor is not None:
                route = f"{route}&cursor={cursor}&start={pages * page_size}"

            try:
                body: dict[str, Any] = await self._read_query_page(
                    route, max(min(QUERY_LOG_PAGE_TIMEOUT_SECONDS, remaining), 0.1)
                )
            except ClientConnectorError:
                if pages == 0:
                    raise
                break

            if cursor is None:
                cursor = self._query_log_cursor(body)

            page_newest, rows = parse_query_activity(cast("list[Any]", body["queries"]))
            hidden_clients += count_hidden_clients(body["queries"])
            pages += 1
            queries_read += rows

            for address, moment in page_newest.items():
                newest[address] = max(moment, newest.get(address, 0.0))

            if rows < page_size:
                complete = True
                break

        if not newest and hidden_clients:
            # Every client read is the placeholder of the privacy level: no device can be matched, now or later.
            raise QueryLogUnavailableError

        return QueryActivity(
            last_seen_by_ip=newest,
            newest_time=max(newest.values()) if newest else None,
            pages=pages,
            queries_read=queries_read,
            complete=complete,
            duration=time.monotonic() - started,
        )

    async def _read_query_page(self, route: str, request_timeout: float) -> dict[str, Any]:
        """Read one page of the query log, without ever logging its body.

        Args:
            route (str): The route of the page, with its parameters.
            request_timeout (float): Seconds allowed to the request. The reading of the body is bounded a little beyond.

        Returns:
            dict[str, Any]: The body of the response, whose "queries" is a list.

        Raises:
            ClientConnectorError: If the request or the reading of the body times out.
            DataStructureError: If the body is not a dictionary holding a list of queries.

        """

        try:
            # The outer timeout also covers the reading of the body, which `_call` does not bound.
            async with asyncio.timeout(request_timeout + 2):
                result: dict[str, Any] = await self._call(
                    route,
                    action="query_activity",
                    method="GET",
                    timeout=request_timeout,
                    log_body=False,
                    expected_errors=_QUERY_LOG_EXPECTED_ERRORS,
                )
        except TimeoutError as err:
            raise ClientConnectorError(QUERY_LOG_TIMEOUT_MESSAGE) from err

        body: Any = result["data"]

        if not isinstance(body, dict) or not isinstance(cast("dict[str, Any]", body).get("queries"), list):
            raise DataStructureError(QUERY_LOG_ENDPOINT)

        return cast("dict[str, Any]", body)

    @staticmethod
    def _query_log_cursor(body: dict[str, Any]) -> int:
        """Read the cursor of the first page of the query log, which freezes the result set for the next pages.

        Args:
            body (dict[str, Any]): The body of the first page.

        Returns:
            int: The cursor.

        Raises:
            QueryLogUnavailableError: If there is no cursor: Pi-hole records nothing at its anonymous privacy level.
            DataStructureError: If the cursor is not an integer.

        """

        cursor: Any = body.get("cursor")

        if cursor is None:
            raise QueryLogUnavailableError

        if isinstance(cursor, bool) or not isinstance(cursor, int):
            raise DataStructureError(QUERY_LOG_ENDPOINT)

        return cursor

    async def call_group_disable(self, group: str) -> dict[str, Any]:
        """Disable a Pi-hole group.

        The errors of the underlying call propagate unchanged: APIError (if the API returns an error status code), ClientConnectorError (if the server is unreachable).

        Args:
            group (str): The name of the group to disable.

        Returns:
            dict[str, Any]: A dictionary with the keys "code", "reason", and "data".

        """

        url: str = f"/groups/{group}"

        result: dict[str, Any] = await self._call(
            url,
            action="group-disable",
            method="PUT",
            data={
                "name": group,
                "comment": self.cache_groups[group]["comment"],
                "enabled": False,
            },
        )

        return {
            "code": result["code"],
            "reason": result["reason"],
            "data": result["data"],
        }

    async def call_group_enable(self, group: str) -> dict[str, Any]:
        """Enable a Pi-hole group.

        The errors of the underlying call propagate unchanged: APIError (if the API returns an error status code), ClientConnectorError (if the server is unreachable).

        Args:
            group (str): The name of the group to enable.

        Returns:
            dict[str, Any]: A dictionary with the keys "code", "reason", and "data".

        """

        url: str = f"/groups/{group}"

        result: dict[str, Any] = await self._call(
            url,
            action="group-enable",
            method="PUT",
            data={
                "name": group,
                "comment": self.cache_groups[group]["comment"],
                "enabled": True,
            },
        )

        return {
            "code": result["code"],
            "reason": result["reason"],
            "data": result["data"],
        }

    async def call_action_flush_arp(self) -> dict[str, Any]:
        """Flush the network table.

        This includes emptying the ARP table and removing both all known devices and their associated addresses.

        The errors of the underlying call propagate unchanged: APIError (if the API returns an error status code), ClientConnectorError (if the server is unreachable).

        Returns:
            dict[str, Any]: A dictionary with the keys "code", "reason", and "data".

        """

        return await self._call_action("flush_arp")

    async def call_action_flush_logs(self) -> dict[str, Any]:
        """Flush the DNS logs.

        This includes emptying the DNS log file and purging the most recent 24 hours from both the database and FTL's internal memory.

        The errors of the underlying call propagate unchanged: APIError (if the API returns an error status code), ClientConnectorError (if the server is unreachable).

        Returns:
            dict[str, Any]: A dictionary with the keys "code", "reason", and "data".

        """

        return await self._call_action("flush_logs")

    async def call_action_gravity(self) -> dict[str, Any]:
        """Run gravity.

        Update Pi-hole's adlists by running pihole -g.

        The errors of the underlying call propagate unchanged: APIError (if the API returns an error status code), ClientConnectorError (if the server is unreachable).

        Returns:
            dict[str, Any]: A dictionary with the keys "code", "reason", and "data".

        """

        return await self._call_action("gravity")

    async def call_action_restartdns(self) -> dict[str, Any]:
        """Restart the pihole-FTL service.

        The errors of the underlying call propagate unchanged: APIError (if the API returns an error status code), ClientConnectorError (if the server is unreachable).

        Returns:
            dict[str, Any]: A dictionary with the keys "code", "reason", and "data".

        """

        return await self._call_action("restartdns")

    async def call_action_ftl_purge_diagnosis_messages(self) -> dict[str, Any]:
        """Purge all FTL diagnosis messages.

        Iterates over cached messages and deletes each one via the API.
        Clears the local message cache after deletion.

        The errors of the underlying call propagate unchanged: APIError (if the API returns an error status code), ClientConnectorError (if the server is unreachable).

        Returns:
            dict[str, Any]: A dictionary with the keys "code", "reason", and "data".

        """

        messages: list[Any] = self.cache_ftl_info["message_list"]

        result: dict[str, Any] = {"code": 200, "reason": "No FTL diagnosis message to delete", "data": {}}

        if len(messages) == 0:
            return result

        for message in messages:
            url: str = f"/info/messages/{message['id']}"

            await self._call(
                url,
                action="action_ftl_purge_diagnosis_messages",
                method="DELETE",
            )

        # Every known message was just deleted, so the cached count would otherwise stay stale until
        # the next refresh. Pi-hole may have raised a new one meanwhile, which that refresh will correct.
        self.cache_ftl_info["message_list"] = []
        self.cache_ftl_info["message_count"] = 0

        return {
            "code": result["code"],
            "reason": result["reason"],
            "data": result["data"],
        }

    async def _call_action(self, action_name: str) -> dict[str, Any]:
        """Execute a Pi-hole action.

        The errors of the underlying call propagate unchanged: APIError (if the API returns an error status code), ClientConnectorError (if the server is unreachable).

        Args:
            action_name (str): Represents the action to execute.

        Returns:
            dict[str, Any]: A dictionary with the keys "code", "reason", and "data".

        """

        url: str = f"/action/{action_name.replace('_', '/')}"

        result: dict[str, Any] = await self._call(
            url,
            action=f"action_{action_name}",
            method="POST",
        )

        return {
            "code": result["code"],
            "reason": result["reason"],
            "data": result["data"],
        }

    def remove_cache(self, data_name: str) -> None:
        """Reset a specific cache entry to its default error state.

        Args:
            data_name (str): The name of the cache to reset. Currently supports "ftl_info_messages".

        """

        if data_name == "ftl_info_messages":
            self.cache_ftl_info["message_list"] = []
            self.cache_ftl_info["status"] = "NOK: Messages fetched unsuccessfully"
