"""The above class represents Pi-hole API Client with methods for authentication, retrieving summary data, managing blocking status, and logging requests."""

import asyncio
import copy
import hashlib
import logging
from socket import gaierror as GaiError
from typing import Any

import requests
from aiohttp import ClientError, ContentTypeError

from .exceptions import (
    AbortLogoutException,
    ClientConnectorException,
    ContentTypeException,
    UnauthorizedException,
    handle_status,
)


class API:
    """Pi-hole API Client."""

    _logger: logging.Logger | None
    _password: Any = ""
    _session: Any = None
    _sid: str | None = None

    cache_blocking: dict[str, Any] = {}
    cache_padd: dict[str, Any] = {}
    cache_summary: dict[str, Any] = {}
    cache_groups: dict[str, dict[str, Any]] = {}

    url: str = ""

    def __init__(  # noqa: D417
        self,
        session,
        url: str = "http://pi.hole",
        password: str = "",
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialize Pi-hole API Client object with an API URL and an optional logger.

        Args:
          url (str): Represents the URL of API endpoint. Defaults to "http://pi.hole".
          logger (Logger | None): Expects an object of type `Logger` or `None` which will be used to display debug message.

        """

        self.url = url
        self._logger = logger
        self._password = password
        self._session = session

    def _get_logger(self) -> logging.Logger:
        """Return a logger if it exists, otherwise it creates a new logger.

        Returns:
          result (Logger): The logger provided during object initialization, otherwise a new logger is created.

        """

        if self._logger is None:
            return logging.getLogger()

        return self._logger

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
            method (str): Represents the HTTP method to be used. It can be one of the following: "post", "delete", or "get".
            action (str): Represents the action name requested.
            data (dict[str, Any] | None): Used to pass a dictionary containing data to be sent in the request when making a POST request.

        Returns:
          result (dict[str, Any]): A dictionary is being returned with keys "code", "reason", and "data".

        """

        await self._check_authentification(action)
        await self._abort_logout(action)
        await self._request_login(action)

        self._get_logger().debug("Session ID Hash: %s", self._get_sid_hash(self._sid))

        url: str = f"{self.url}{route}"

        headers: dict[str, str] = {
            "accept": "application/json",
            "content-type": "application/json",
        }

        if self._sid is not None:
            headers = headers | {"sid": self._sid}

        self._get_logger().debug("Request: %s %s", method.upper(), url)

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
                    self._get_logger().error(
                        "Method (%s) is not supported/implemented.", method.lower()
                    )
                    raise RuntimeError("Method is not supported/implemented.")

        except (TimeoutError, ClientError, GaiError) as err:
            raise ClientConnectorException from err

        result_data: dict[str, Any] = {}

        self._get_logger().debug("Status Code: %d", request.status)

        try:
            handle_status(request.status)
        except RuntimeError as err1:
            self._get_logger().error("Status Code: %d", request.status)
            raise err1
        except Exception as err2:
            self._get_logger().error("Status Code: %d", request.status)
            raise err2

        if request.status < 400 and request.text != "":
            try:
                result_data_debug: dict[str, Any] | None = None

                if request.status != 204:
                    result_data = await request.json()
                    result_data_debug = copy.deepcopy(result_data)

                if action == "login":
                    result_data_debug["session"]["sid"] = "[redacted]"

                if result_data_debug is not None:
                    self._get_logger().debug("Data: %s", result_data_debug)

            except ContentTypeError as err:
                raise ContentTypeException from err

        return {
            "code": request.status,
            "reason": request.reason,
            "data": result_data,
        }

    async def _check_authentification(self, action: str) -> None:
        """..."""

        try:
            if (
                action not in ("login", "authentification_status")
                and self._sid is not None
            ):
                response: dict[str, Any] = await self.call_authentification_status()

                if (
                    response["code"] != 200
                    or response["data"]["session"]["valid"] is False
                ):
                    self._sid = None

        except UnauthorizedException:
            self._sid = None

    async def _request_login(self, action: str) -> None:
        """..."""

        if action != "login" and self._sid is None:
            await self.call_login()

    async def _abort_logout(self, action: str) -> None:
        """..."""

        if action == "logout" and self._sid is None:
            raise AbortLogoutException()

    def _get_sid_hash(self, sid: str) -> str | None:
        """..."""

        if self._sid is not None:
            return str(hashlib.sha256(self._sid.encode("utf-8")).hexdigest())

        return None

    async def call_authentification_status(self) -> dict[str, Any]:
        """..."""

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
        """Authenticate a user with a password.

        Args:
          password (str): Represents tne password used to authenticate the user during the login process.

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

        if result["data"]["session"]["message"] == "password incorrect":
            raise UnauthorizedException()

        self._sid = result["data"]["session"]["sid"]

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

        except AbortLogoutException as err:
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
          duration (int | None): Represents the time duration in seconds for which the blocking feature will be disabled. Defaults to 120

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
            }

        return {
            "code": result["code"],
            "reason": result["reason"],
            "data": result["data"],
        }

    async def call_group_disable(self, group: str) -> dict[str, Any]:
        """Disable Pi-hole group.

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
        """Enable Pi-hole group.

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
                "enabled": True,
            },
        )

        return {
            "code": result["code"],
            "reason": result["reason"],
            "data": result["data"],
        }
