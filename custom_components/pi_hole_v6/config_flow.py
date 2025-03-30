"""Config flow to configure the Pi-hole V6 integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_URL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import API as ClientAPI
from .const import (
    CONF_UPDATE_INTERVAL,
    CONFIG_ENTRY_VERSION,
    DEFAULT_NAME,
    DEFAULT_PASSWORD,
    DEFAULT_URL,
    DOMAIN,
    MIN_TIME_BETWEEN_UPDATES,
)
from .exceptions import (
    ClientConnectorException,
    ContentTypeException,
    ForbiddenException,
    MethodNotAllowedException,
    NotFoundException,
    UnauthorizedException,
)

_LOGGER = logging.getLogger(__name__)


def _get_data_config_schema(user_input) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_NAME,
                default=user_input.get(CONF_NAME, DEFAULT_NAME),
            ): str,
            vol.Required(
                CONF_URL,
                default=user_input.get(CONF_URL, DEFAULT_URL),
            ): str,
            vol.Optional(
                CONF_PASSWORD,
                default=user_input.get(CONF_PASSWORD, DEFAULT_PASSWORD),
            ): str,
        }
    )


class ConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Pi-hole V6 config flow."""

    VERSION = CONFIG_ENTRY_VERSION

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._config: dict = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            self._config = {
                CONF_NAME: user_input[CONF_NAME],
                CONF_URL: user_input[CONF_URL],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }

            await self.async_set_unique_id(user_input[CONF_URL].lower())
            self._abort_if_unique_id_configured()

            if not (errors := await self._async_try_connect()):
                return self.async_create_entry(title=user_input[CONF_NAME], data=self._config)
            else:
                user_input["password"] = ""

        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=_get_data_config_schema(user_input),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Perform reauth if the user credentials have changed."""
        self._config = {
            CONF_NAME: entry_data[CONF_NAME],
            CONF_URL: entry_data[CONF_URL],
        }
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle user's reauth credentials."""
        errors: dict[str, str] = {}
        if user_input:
            self._config[CONF_PASSWORD] = user_input[CONF_PASSWORD]

            if not (errors := await self._async_try_connect()):
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates=user_input,
                )
            else:
                del user_input[CONF_PASSWORD]

        user_input = user_input or {}
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_PASSWORD,
                        default=user_input.get(CONF_PASSWORD, DEFAULT_PASSWORD),
                    ): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler()

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
            _LOGGER.error("Connection failed (%s): %s", api_client.url, err)
            return {CONF_URL: "cannot_connect"}
        except (
            NotFoundException,
            ContentTypeException,
            MethodNotAllowedException,
        ) as err:
            _LOGGER.error("Connection failed (%s): %s", api_client.url, err)
            return {CONF_URL: "invalid_path"}
        except (UnauthorizedException, ForbiddenException) as err:
            _LOGGER.error("Connection failed (%s): %s", api_client.url, err)
            return {CONF_PASSWORD: "invalid_auth"}


def _get_data_option_schema(user_input) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_UPDATE_INTERVAL,
            ): vol.All(
                selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=3600,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Coerce(int),
            ),
        }
    )


async def _async_validate_input(
    hass: HomeAssistant,
    user_input: dict[str, Any],
) -> Any:
    if user_input[CONF_UPDATE_INTERVAL] == 1:
        return {CONF_UPDATE_INTERVAL: "invalid_update_interval"}

    return {}


class OptionsFlowHandler(OptionsFlow):
    """Options flow used to change configuration (options) of existing instance of integration."""

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:  # we asked to validate values entered by user
            errors = await _async_validate_input(self.hass, user_input)

            if not errors:
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data={**self.config_entry.data, **user_input}
                )
                return self.async_create_entry(title="", data={})
            else:
                return self.async_show_form(
                    step_id="init",
                    data_schema=self.add_suggested_values_to_schema(
                        _get_data_option_schema(user_input),
                        user_input,
                    ),
                    errors=dict(errors),
                )

        update_interval = self.config_entry.data.get(CONF_UPDATE_INTERVAL, None)

        if update_interval is None:
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={
                    **self.config_entry.data,
                    **{CONF_UPDATE_INTERVAL: MIN_TIME_BETWEEN_UPDATES.seconds},
                },
            )

        # we asked to provide default values for the form
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                _get_data_option_schema(user_input),
                self.config_entry.data,
            ),
        )
