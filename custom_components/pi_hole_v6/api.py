"""The above class represents Pi-hole API Client with methods for authentication, retrieving summary data, managing blocking status, and logging requests."""

import asyncio
import json
import logging
from socket import gaierror
from typing import TYPE_CHECKING, Any

from aiohttp import ClientError, ContentTypeError, client
import requests

from .exceptions import (
    AbortLogoutError,
    APIError,
    ClientConnectorError,
    UnauthorizedError,
    handle_status,
)

if TYPE_CHECKING:
    from datetime import datetime


_LOGGER = logging.getLogger(__name__)


class Api:  # pylint: disable=too-many-public-methods, too-many-instance-attributes
    """Pi-hole API Client."""

    def __init__(
        self,
        session: client.ClientSession,
        url: str = "http://pi.hole",
        password: str = "",
    ) -> None:
        """Initialize Pi-hole API Client object with an API URL.

        Args:
          session (client.ClientSession): The aiohttp client session used to perform HTTP requests.
          url (str): Represents the URL of API endpoint. Defaults to "http://pi.hole".
          password (str): The password used to authenticate against the Pi-hole API. Defaults to "".


        """
        self._call_lock = asyncio.Lock()
        self._password: str = password
        self._session: client.ClientSession = session
        self._sid: str | None = None
        self.url: str = url

        self.cache_auth_sessions: dict[str, Any] = {}
        self.cache_blocking: dict[str, Any] = {}
        self.cache_configured_clients: dict[str, dict[str, Any]] = {}
        self.cache_dhcp_leases: dict[str, dict[str, Any]] = {}
        self.cache_ftl_info: dict[str, dict[str, Any]] = {}
        self.cache_groups: dict[str, dict[str, Any]] = {}
        self.cache_padd: dict[str, Any] = {}
        self.cache_remaining_dates: dict[str, datetime] = {}
        self.cache_summary: dict[str, Any] = {}

        self.just_initialized: bool = False
        self.last_refresh: datetime | None = None

    async def _call(
        self,
        route: str,
        method: str,
        action: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send HTTP requests with specified method, route, and data.

        Args:
            route (str): Represents the specific endpoint that you want to call.
            method (str): Represents the HTTP method to be used. It can be one of the following: "post", "put", "delete", or "get".
            action (str): Represents the action name requested.
            data (dict[str, Any] | None): Used to pass a dictionary containing data to be sent in the request when making a POST request.

        Returns:
          result (dict[str, Any]): A dictionary is being returned with keys "code", "reason", and "data".

        """

        await self._authentification_step_with_lock(action)

        url: str = f"{self.url}{route}"

        headers: dict[str, str] = {
            "accept": "application/json",
            "content-type": "application/json",
        }

        if self._sid is not None and self._sid != "no password set":
            headers = headers | {"sid": self._sid}

        request: requests.Response

        try:
            async with asyncio.timeout(60):
                if method.lower() == "post":
                    request = await self._session.post(url, json=data, headers=headers)
                elif method.lower() == "put":
                    request = await self._session.put(url, json=data, headers=headers)
                elif method.lower() == "delete":
                    request = await self._session.delete(url, headers=headers)
                elif method.lower() == "get":
                    request = await self._session.get(url, headers=headers)
                else:
                    msg: str = f"Method ({method.lower()}) is not supported/implemented."
                    _LOGGER.critical(msg)
                    raise RuntimeError(msg)

        except (TimeoutError, ClientError, gaierror) as err:
            raise ClientConnectorError(str(err)) from err

        try:
            handle_status(request.status)
        except APIError as api_error:
            log_message: str = await self._create_log_message_on_api_exception(api_error, request, method, url)
            _LOGGER.exception(log_message)
            raise

        result_data: str | None = None

        if request.status < 400 and request.text != "":
            try:
                result_data = await self._try_to_retrieve_json_result(request, privacy=False)
                message: str = await self._create_log_message_on_api_result(request, method, url)

                if "password incorrect" not in message:
                    _LOGGER.debug(message)
                else:
                    _LOGGER.error(message)

            except ContentTypeError as err:
                raise ContentTypeError from err

        return {
            "code": request.status,
            "reason": request.reason,
            "data": result_data,
        }

    async def _try_to_retrieve_json_result(self, request: requests.Response, privacy: bool = True) -> str | None:
        """Attempt to parse the JSON body from an HTTP response.

        Handles encoding errors gracefully and optionally redacts the session SID for privacy.

        Args:
            request (requests.Response): The HTTP response object to parse.
            privacy (bool): If True, redacts the session SID from the result. Defaults to True.

        Returns:
            str | None: The parsed JSON content, or None if the response has no body.

        """

        text: str | None = None

        try:
            if request.status != 204:
                text = await request.json()
        except UnicodeDecodeError:
            raw_data = await request.read()
            text_data = raw_data.decode(encoding="utf-8", errors="replace")  # ou un autre encodage
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

    async def _create_log_message_on_api_result(self, request: requests.Response, method: str, url: str) -> str:
        """Build a log message string from an HTTP response.

        Args:
            request (requests.Response): The HTTP response object.
            method (str): The HTTP method used for the request.
            url (str): The URL of the request.

        Returns:
            str: A formatted log message containing status, reason, method, URL and response body.

        """

        text: str | None = await self._try_to_retrieve_json_result(request)
        status: str = str(request.status)
        reason: str = str(request.reason)

        return f"{status} {reason} # {method.upper()} {url} : {text}"

    async def _create_log_message_on_api_exception(
        self, api_error: APIError, request: requests.Response, method: str, url: str
    ) -> str:
        """Build a log message string from an API exception and its associated HTTP response.

        Args:
            api_error (APIError): The API exception that was raised.
            request (requests.Response): The HTTP response object associated with the error.
            method (str): The HTTP method used for the request.
            url (str): The URL of the request.

        Returns:
            str: A formatted log message prefixed with the exception type name.

        """

        log: str = await self._create_log_message_on_api_result(request, method, url)
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

        """

        if action == "logout" and (self._sid is None or self._sid == "no password set"):
            raise AbortLogoutError

    async def call_authentification_status(self) -> dict[str, Any]:
        """Retrieve the current authentication session status.

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

        Returns:
          result (dict[str, Any]): A dictionary with the keys "code", "reason", and "data".

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

        Returns:
          result (dict[str, Any]): A dictionary with the keys "code", "reason", and "data".

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

        Returns:
          result (dict[str, Any]): A dictionary with the keys "code", "reason", and "data".

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

        Args:
          full (bool): If True, retrieves the full dashboard data. Defaults to True.

        Returns:
          result (dict[str, Any]): A dictionary with the keys "code", "reason", and "data".

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

    async def call_get_auth_sessions(self) -> dict[str, Any]:
        """Retrieve all active sessions.

        Returns:
          result (dict[str, Any]): A Dictionary with the keys "code", "reason", and "data".

        """

        url: str = "/auth/sessions"

        result: dict[str, Any] = await self._call(
            url,
            action="auth_sessions",
            method="GET",
        )

        self.cache_auth_sessions = result["data"]["sessions"]

        return {
            "code": result["code"],
            "reason": result["reason"],
            "data": result["data"],
        }

    async def call_blocking_status(self) -> dict[str, Any]:
        """Retrieve current blocking status.

        Returns:
          result (dict[str, Any]): A Dictionary with the keys "code", "reason", and "data".

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

        Returns:
          result (dict[str, Any]): A dictionary with the keys "code", "reason", and "data".

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

        Args:
          duration (int | None): The time duration in seconds for which blocking will be disabled. Pass None to disable indefinitely.

        Returns:
          result (dict[str, Any]): A dictionary with the keys "code", "reason", and "data".

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

        Returns:
          result (dict[str, Any]): A dictionary with the keys "code", "reason", and "data".

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

        Returns:
          result (dict[str, Any]): A dictionary with the keys "code", "reason", and "data".

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

        Returns:
          result (dict[str, Any]): A dictionary with the keys "code", "reason", and "data".

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

        Returns:
          result (dict[str, Any]): A dictionary with the keys "code", "reason", and "data".

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

        Returns:
          result (dict[str, Any]): A dictionary with the keys "code", "reason", and "data".

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

    async def call_group_disable(self, group: str) -> dict[str, Any]:
        """Disable a Pi-hole group.

        Args:
          group (str): The name of the group to disable.

        Returns:
          result (dict[str, Any]): A dictionary with the keys "code", "reason", and "data".

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

        Args:
          group (str): The name of the group to enable.

        Returns:
          result (dict[str, Any]): A dictionary with the keys "code", "reason", and "data".

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

        Returns:
          result (dict[str, Any]): A dictionary with the keys "code", "reason", and "data".

        """

        return await self._call_action("flush_arp")

    async def call_action_flush_logs(self) -> dict[str, Any]:
        """Flush the DNS logs.

        This includes emptying the DNS log file and purging the most recent 24 hours from both the database and FTL's internal memory.'

        Returns:
          result (dict[str, Any]): A dictionary with the keys "code", "reason", and "data".

        """

        return await self._call_action("flush_logs")

    async def call_action_gravity(self) -> dict[str, Any]:
        """Run gravity.

        Update Pi-hole's adlists by running pihole -g.

        Returns:
          result (dict[str, Any]): A dictionary with the keys "code", "reason", and "data".

        """

        return await self._call_action("gravity")

    async def call_action_restartdns(self) -> dict[str, Any]:
        """Restart the pihole-FTL service.

        Returns:
          result (dict[str, Any]): A dictionary with the keys "code", "reason", and "data".

        """

        return await self._call_action("restartdns")

    async def call_action_ftl_purge_diagnosis_messages(self) -> dict[str, Any]:
        """Purge all FTL diagnosis messages.

        Returns:
          result (dict[str, Any]): A dictionary with the keys "code", "reason", and "data".

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

        self.cache_ftl_info["message_list"] = []

        return {
            "code": result["code"],
            "reason": result["reason"],
            "data": result["data"],
        }

    async def _call_action(self, action_name: str) -> dict[str, Any]:
        """Execute an Pi-hole action.

        Args:
          action_name (str): Represents the action to execute

        Returns:
          result (dict[str, Any]): A dictionary with the keys "code", "reason", and "data".

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
            self.cache_ftl_info["message_list"] = {}
            self.cache_ftl_info["status"] = "NOK: Messages fetched unsuccessfully"
