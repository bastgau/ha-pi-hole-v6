"""Config flow to configure the Pi-hole V6 integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_URL,
)
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import Api as ClientAPI
from .const import (
    CONF_ENABLE_DEVICE_TRACKER,
    CONF_UPDATE_INTERVAL,
    CONFIG_ENTRY_VERSION,
    DEFAULT_ENABLE_DEVICE_TRACKER,
    DEFAULT_NAME,
    DEFAULT_PASSWORD,
    DEFAULT_URL,
    DOMAIN,
    EXAMPLE_URL,
    MIN_TIME_BETWEEN_UPDATES,
)
from .exceptions import (
    ClientConnectorError,
    ContentTypeError,
    ForbiddenError,
    MethodNotAllowedError,
    NotFoundError,
    UnauthorizedError,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from aiohttp import client

_LOGGER = logging.getLogger(__name__)


def _get_data_config_schema(user_input: Any) -> vol.Schema:
    """Build and return the voluptuous schema for the main config flow form.

    Args:
        user_input (Any): Previously entered user input used to pre-fill default values.

    Returns:
        vol.Schema: The schema to be used in the config flow form.

    """
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
        self._config: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle a flow initiated by the user.

        Args:
            user_input (dict[str, Any] | None): The input submitted by the user, or None when displaying the form.

        Returns:
            ConfigFlowResult: The result of the config flow step.

        """
        errors = {}

        if user_input is not None:
            if CONF_NAME in user_input:
                user_input[CONF_NAME] = user_input[CONF_NAME].strip()

            if CONF_URL in user_input:
                user_input[CONF_URL] = user_input[CONF_URL].strip()

            self._config = {
                CONF_NAME: user_input[CONF_NAME],
                CONF_URL: user_input[CONF_URL],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }

            await self.async_set_unique_id(user_input[CONF_URL].lower())
            self._abort_if_unique_id_configured()

            if not (errors := await self._async_try_connect()):
                return self.async_create_entry(title=user_input[CONF_NAME], data=self._config)
            user_input["password"] = ""

        user_input = user_input or {}

        return self.async_show_form(
            step_id="user",
            data_schema=_get_data_config_schema(user_input),
            errors=errors,
            description_placeholders={
                "example_url": EXAMPLE_URL,
            },
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Perform reauth if the user credentials have changed.

        Args:
            entry_data (Mapping[str, Any]): The existing config entry data.

        Returns:
            ConfigFlowResult: The result of the reauth flow step.

        """
        self._config = {
            CONF_NAME: entry_data[CONF_NAME],
            CONF_URL: entry_data[CONF_URL],
        }
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle user's reauth credentials.

        Args:
            user_input (dict[str, Any] | None): The input submitted by the user, or None when displaying the form.

        Returns:
            ConfigFlowResult: The result of the reauth confirmation step.

        """
        errors: dict[str, str] | None = {}
        if user_input:
            self._config[CONF_PASSWORD] = user_input[CONF_PASSWORD]

            if not (errors := await self._async_try_connect()):
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates=user_input,
                )
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
    def async_get_options_flow(config_entry: Any) -> OptionsFlowHandler:  # noqa: ARG004
        """Get the options flow for this handler.

        Args:
            config_entry (Any): The current config entry (unused).

        Returns:
            OptionsFlowHandler: The options flow handler instance.

        """
        return OptionsFlowHandler()

    async def _async_try_connect(self) -> dict[str, str]:
        """Attempt to connect to the Pi-hole API using the current config.

        Returns:
            dict[str, str]: An empty dict on success, or a dict mapping a field key
            to an error string on failure.

        """
        session: client.ClientSession = async_get_clientsession(self.hass, verify_ssl=False)

        api_client: ClientAPI = ClientAPI(
            session=session,
            url=self._config[CONF_URL],
            password=self._config[CONF_PASSWORD],
        )

        try:
            await api_client.call_authentification_status()
        except ClientConnectorError:
            _LOGGER.error("Connection failed (%s)", api_client.url)  # noqa: TRY400
            return {CONF_URL: "cannot_connect"}
        except (
            NotFoundError,
            ContentTypeError,
            MethodNotAllowedError,
        ):
            _LOGGER.error("Connection failed (%s)", api_client.url)  # noqa: TRY400
            return {CONF_URL: "invalid_path"}
        except (UnauthorizedError, ForbiddenError):
            _LOGGER.error("Connection failed (%s)", api_client.url)  # noqa: TRY400
            return {CONF_PASSWORD: "invalid_auth"}

        return {}


def _get_data_option_schema() -> vol.Schema:
    """Build and return the voluptuous schema for the options flow form.

    Returns:
        vol.Schema: The schema to be used in the options flow form.

    """
    return vol.Schema(
        {
            vol.Required(
                CONF_UPDATE_INTERVAL,
            ): vol.All(
                selector.NumberSelector(  # pyright: ignore[reportUnknownMemberType]
                    selector.NumberSelectorConfig(
                        min=1,
                        max=3600,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Coerce(int),
            ),
            vol.Required(
                CONF_URL,
            ): vol.All(
                selector.TextSelector(),  # pyright: ignore[reportUnknownMemberType]
                vol.Coerce(str),
            ),
            vol.Required(
                CONF_ENABLE_DEVICE_TRACKER,
            ): selector.BooleanSelector(),  # pyright: ignore[reportUnknownMemberType]
        }
    )


async def _async_validate_input(
    user_input: dict[str, Any],
) -> Any:
    """Validate the user input from the options flow form.

    Args:
        user_input (dict[str, Any]): The input submitted by the user in the options form.

    Returns:
        Any: An empty dict if the input is valid, or a dict mapping a field key to an error string.

    """
    if user_input[CONF_UPDATE_INTERVAL] == 1:
        return {CONF_UPDATE_INTERVAL: "invalid_update_interval"}

    return {}


class OptionsFlowHandler(OptionsFlow):
    """Options flow used to change configuration (options) of existing instance of integration."""

    async def async_step_init(self, user_input: Any) -> ConfigFlowResult:
        """Handle the initial step of the options flow.

        Validates the user input if provided, updates the config entry and
        returns the form pre-filled with current values otherwise.

        Args:
            user_input (Any): The input submitted by the user, or None when displaying the form.

        Returns:
            ConfigFlowResult: The result of the options flow step.

        """
        if user_input is not None:  # we asked to validate values entered by user
            errors = await _async_validate_input(user_input)

            if not errors:
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data={**self.config_entry.data, **user_input}
                )
                return self.async_create_entry(title="", data={})
            return self.async_show_form(
                step_id="init",
                data_schema=self.add_suggested_values_to_schema(
                    _get_data_option_schema(),
                    user_input,
                ),
                errors=dict(errors),
            )

        update_interval = self.config_entry.data.get(CONF_UPDATE_INTERVAL, None)
        enable_device_tracker = self.config_entry.data.get(CONF_ENABLE_DEVICE_TRACKER, None)

        if update_interval is None or enable_device_tracker is None:
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={
                    **self.config_entry.data,
                    CONF_UPDATE_INTERVAL: update_interval or MIN_TIME_BETWEEN_UPDATES.seconds,
                    CONF_ENABLE_DEVICE_TRACKER: (
                        DEFAULT_ENABLE_DEVICE_TRACKER if enable_device_tracker is None else enable_device_tracker
                    ),
                },
            )

        # we asked to provide default values for the form
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                _get_data_option_schema(),
                self.config_entry.data,
            ),
        )
