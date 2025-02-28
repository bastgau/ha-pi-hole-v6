"""Config flow to configure the Pi-hole V6 integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_URL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import API as ClientAPI
from .const import DEFAULT_NAME, DEFAULT_PASSWORD, DEFAULT_URL, DOMAIN
from .exceptions import (
    ClientConnectorException,
    ContentTypeException,
    NotFoundException,
    UnauthorizedException,
)

_LOGGER = logging.getLogger(__name__)


class PiHoleV6dFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Pi-hole V6 config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._config: dict = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            self._config = {
                CONF_NAME: user_input[CONF_NAME],
                CONF_URL: user_input[CONF_URL],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }

            self._async_abort_entries_match(
                {
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_URL: user_input[CONF_URL],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                }
            )

            if not (errors := await self._async_try_connect()):
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=self._config
                )

        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME,
                        default=user_input.get(CONF_NAME, DEFAULT_NAME),
                    ): str,
                    vol.Required(
                        CONF_URL,
                        default=user_input.get(CONF_URL, DEFAULT_URL),
                    ): str,
                    vol.Required(
                        CONF_PASSWORD,
                        default=user_input.get(CONF_PASSWORD, DEFAULT_PASSWORD),
                    ): str,
                }
            ),
            errors=errors,
        )

    async def _async_try_connect(self) -> dict[str, str]:
        session = async_get_clientsession(self.hass, False)

        api_client = ClientAPI(
            session=session,
            url=self._config[CONF_URL],
            password=self._config[CONF_PASSWORD],
            logger=_LOGGER,
        )

        try:
            await api_client.call_authentification_status()
        except ClientConnectorException as err:
            _LOGGER.debug("Connection failed: %s", err)
            return {CONF_URL: "cannot_connect"}
        except (NotFoundException, ContentTypeException) as err:
            _LOGGER.debug("Connection failed: %s", err)
            return {CONF_URL: "invalid_path"}
        except UnauthorizedException as err:
            _LOGGER.debug("Connection failed: %s", err)
            return {CONF_PASSWORD: "invalid_auth"}

        if not isinstance(await api_client.call_summary(), dict):
            return {"base": "coco"}

        if not isinstance(await api_client.call_blocking_status(), dict):
            return {"base": "coco"}

        return {}
