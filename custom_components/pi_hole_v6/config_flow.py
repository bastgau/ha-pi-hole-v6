"""Config flow to configure the Pi-hole V6 integration."""

from __future__ import annotations

import logging
import ssl
from typing import TYPE_CHECKING, Any

import probatio

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
from .certificate import async_get_certificate_fingerprint
from .const import (
    CONF_CERT_FINGERPRINT,
    CONF_DEVICE_TRACKER_MAC_LIST,
    CONF_DEVICE_TRACKER_WHITELIST,
    CONF_ENABLE_DEVICE_TRACKER,
    CONF_UPDATE_INTERVAL_LIVE,
    CONF_UPDATE_INTERVAL_STATS,
    CONF_VERIFY_SSL,
    CONFIG_ENTRY_VERSION,
    DEFAULT_DEVICE_TRACKER_MAC_LIST,
    DEFAULT_DEVICE_TRACKER_WHITELIST,
    DEFAULT_ENABLE_DEVICE_TRACKER,
    DEFAULT_NAME,
    DEFAULT_PASSWORD,
    DEFAULT_URL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    EXAMPLE_URL,
    LEGACY_VERIFY_SSL,
    MIN_TIME_BETWEEN_UPDATES_LIVE,
    MIN_TIME_BETWEEN_UPDATES_STATS,
)
from .exceptions import (
    CertificateChangedError,
    CertificateError,
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

    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

CONF_CONFIRM_CERTIFICATE = "confirm_certificate"


def _get_pin_certificate_schema() -> probatio.Schema:
    """Build and return the probatio schema for the certificate confirmation form.

    Returns:
        probatio.Schema: The schema asking the user to confirm the certificate fingerprint.

    """
    return probatio.Schema(
        {
            probatio.Required(
                CONF_CONFIRM_CERTIFICATE,
                default=False,
            ): selector.BooleanSelector(),  # pyright: ignore[reportUnknownMemberType]
        }
    )


def _warn_insecure_settings(url: str, verify_ssl: bool) -> None:
    """Log a warning when the settings saved by the user expose the password on the network.

    Called only when the configuration is saved, so the warning is not repeated at every start.

    Args:
        url (str): The Pi-hole API URL.
        verify_ssl (bool): Whether the TLS certificate is verified.

    """
    if not verify_ssl:
        _LOGGER.warning(
            "TLS certificate verification is disabled for %s: the password could be intercepted on your network",
            url,
        )
    if url.lower().startswith("http://"):
        _LOGGER.warning(
            "%s uses an unencrypted connection: the password and session are sent in clear text",
            url,
        )


def _get_data_config_schema(user_input: Any) -> probatio.Schema:
    """Build and return the probatio schema for the main config flow form.

    Args:
        user_input (Any): Previously entered user input used to pre-fill default values.

    Returns:
        probatio.Schema: The schema to be used in the config flow form.

    """
    return probatio.Schema(
        {
            probatio.Required(
                CONF_NAME,
                default=user_input.get(CONF_NAME, DEFAULT_NAME),
            ): str,
            probatio.Required(
                CONF_URL,
                default=user_input.get(CONF_URL, DEFAULT_URL),
            ): str,
            probatio.Optional(
                CONF_PASSWORD,
                default=user_input.get(CONF_PASSWORD, DEFAULT_PASSWORD),
            ): str,
            probatio.Optional(
                CONF_VERIFY_SSL,
                default=user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
            ): selector.BooleanSelector(),  # pyright: ignore[reportUnknownMemberType]
        }
    )


class ConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Pi-hole V6 config flow.

    Attributes:
        _config (Any): TODO
        _certificate_fingerprint (str | None): SHA-256 fingerprint of the certificate read from the Pi-hole, awaiting confirmation.
        _untrusted (bool): Whether the last connection attempt was refused because the certificate is not trusted.
        _reauth_pin (bool): Whether the certificate confirmation step runs for a reauthentication.

    """

    VERSION = CONFIG_ENTRY_VERSION

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._config: dict[str, Any] = {}
        self._certificate_fingerprint: str | None = None
        self._untrusted: bool = False
        self._reauth_pin: bool = False

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
                CONF_VERIFY_SSL: user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
            }

            await self.async_set_unique_id(user_input[CONF_URL].lower())
            self._abort_if_unique_id_configured()

            if not (errors := await self._async_try_connect()):
                _warn_insecure_settings(self._config[CONF_URL], self._config[CONF_VERIFY_SSL])
                return self.async_create_entry(title=user_input[CONF_NAME], data=self._config)
            if self._untrusted:
                return await self.async_step_pin_certificate()
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
            CONF_PASSWORD: entry_data.get(CONF_PASSWORD, DEFAULT_PASSWORD),
            CONF_VERIFY_SSL: entry_data.get(CONF_VERIFY_SSL, LEGACY_VERIFY_SSL),
        }

        stored_fingerprint: str | None = entry_data.get(CONF_CERT_FINGERPRINT)
        if stored_fingerprint is not None:
            self._config[CONF_CERT_FINGERPRINT] = stored_fingerprint
            try:
                current_fingerprint = await async_get_certificate_fingerprint(self.hass, self._config[CONF_URL])
            except (OSError, ValueError, ssl.SSLError):
                # Unreachable: the password step reports the connection problem.
                current_fingerprint = None

            if current_fingerprint is not None and current_fingerprint != stored_fingerprint:
                self._certificate_fingerprint = current_fingerprint
                self._reauth_pin = True
                return await self.async_step_pin_certificate()

        return await self.async_step_reauth_confirm()

    async def async_step_pin_certificate(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask the user to confirm the certificate of the Pi-hole, then pin its fingerprint.

        The certificate is read without validating it, so the user must compare the fingerprint shown
        here with the one displayed by the Pi-hole before confirming.

        Args:
            user_input (dict[str, Any] | None): The input submitted by the user, or None when displaying the form.

        Returns:
            ConfigFlowResult: The result of the confirmation step.

        """
        errors: dict[str, str] = {}

        if self._certificate_fingerprint is None:
            try:
                self._certificate_fingerprint = await async_get_certificate_fingerprint(
                    self.hass, self._config[CONF_URL]
                )
            except (OSError, ValueError, ssl.SSLError):
                return self.async_abort(reason="cannot_connect")

        if user_input is not None:
            if not user_input.get(CONF_CONFIRM_CERTIFICATE):
                errors[CONF_CONFIRM_CERTIFICATE] = "certificate_not_confirmed"
            else:
                self._config[CONF_CERT_FINGERPRINT] = self._certificate_fingerprint
                if not (errors := await self._async_try_connect()):
                    if self._reauth_pin:
                        return self.async_update_reload_and_abort(
                            self._get_reauth_entry(),
                            data_updates={CONF_CERT_FINGERPRINT: self._certificate_fingerprint},
                        )
                    return self.async_create_entry(title=self._config[CONF_NAME], data=self._config)
                self._config.pop(CONF_CERT_FINGERPRINT, None)

        return self.async_show_form(
            step_id="pin_certificate",
            data_schema=_get_pin_certificate_schema(),
            errors=errors,
            description_placeholders={
                "url": self._config[CONF_URL],
                "fingerprint": self._certificate_fingerprint or "",
            },
        )

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
            data_schema=probatio.Schema(
                {
                    probatio.Optional(
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
        errors, self._untrusted = await _async_check_connection(self.hass, self._config)
        return errors


async def _async_check_connection(hass: HomeAssistant, config: dict[str, Any]) -> tuple[dict[str, str], bool]:
    """Attempt to connect to the Pi-hole API with the given configuration.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        config (dict[str, Any]): The URL, password, certificate verification and pinned fingerprint to test.

    Returns:
        tuple[dict[str, str], bool]: An empty dict on success, or a dict mapping a field key to an error string,
        and whether the failure is an untrusted certificate that the user can confirm.

    """
    session: client.ClientSession = async_get_clientsession(hass, verify_ssl=config[CONF_VERIFY_SSL])

    fingerprint: str | None = config.get(CONF_CERT_FINGERPRINT)

    api_client: ClientAPI = ClientAPI(
        session=session,
        url=config[CONF_URL],
        password=config[CONF_PASSWORD],
        certificate_fingerprint=bytes.fromhex(fingerprint) if fingerprint else None,
    )

    try:
        await api_client.call_authentification_status()
    except CertificateError:
        _LOGGER.error("Certificate not trusted (%s)", api_client.url)  # noqa: TRY400
        return {CONF_URL: "untrusted_certificate"}, True
    except CertificateChangedError:
        _LOGGER.error("Certificate changed (%s)", api_client.url)  # noqa: TRY400
        return {CONF_URL: "certificate_changed"}, False
    except ClientConnectorError:
        _LOGGER.error("Connection failed (%s)", api_client.url)  # noqa: TRY400
        return {CONF_URL: "cannot_connect"}, False
    except (
        NotFoundError,
        ContentTypeError,
        MethodNotAllowedError,
    ):
        _LOGGER.error("Connection failed (%s)", api_client.url)  # noqa: TRY400
        return {CONF_URL: "invalid_path"}, False
    except (UnauthorizedError, ForbiddenError):
        _LOGGER.error("Connection failed (%s)", api_client.url)  # noqa: TRY400
        return {CONF_PASSWORD: "invalid_auth"}, False

    return {}, False


def _get_data_option_schema() -> probatio.Schema:
    """Build and return the probatio schema for the options flow form.

    Returns:
        probatio.Schema: The schema to be used in the options flow form.

    """
    return probatio.Schema(
        {
            probatio.Required(
                CONF_UPDATE_INTERVAL_LIVE,
            ): probatio.All(
                selector.NumberSelector(  # pyright: ignore[reportUnknownMemberType]
                    selector.NumberSelectorConfig(
                        min=1,
                        max=3600,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                probatio.Coerce(int),
            ),
            probatio.Required(
                CONF_UPDATE_INTERVAL_STATS,
            ): probatio.All(
                selector.NumberSelector(  # pyright: ignore[reportUnknownMemberType]
                    selector.NumberSelectorConfig(
                        min=60,
                        max=86400,
                        step=1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                probatio.Coerce(int),
            ),
            probatio.Required(
                CONF_URL,
            ): probatio.All(
                selector.TextSelector(),  # pyright: ignore[reportUnknownMemberType]
                probatio.Coerce(str),
            ),
            probatio.Required(
                CONF_ENABLE_DEVICE_TRACKER,
            ): selector.BooleanSelector(),  # pyright: ignore[reportUnknownMemberType]
            probatio.Required(
                CONF_DEVICE_TRACKER_WHITELIST,
            ): selector.BooleanSelector(),  # pyright: ignore[reportUnknownMemberType]
            probatio.Optional(
                CONF_DEVICE_TRACKER_MAC_LIST,
            ): probatio.All(
                selector.TextSelector(  # pyright: ignore[reportUnknownMemberType]
                    selector.TextSelectorConfig(multiline=True)
                ),
                probatio.Coerce(str),
            ),
            probatio.Required(
                CONF_VERIFY_SSL,
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
    if user_input[CONF_UPDATE_INTERVAL_LIVE] == 1:
        return {CONF_UPDATE_INTERVAL_LIVE: "invalid_update_interval_live"}

    if user_input[CONF_UPDATE_INTERVAL_STATS] < user_input[CONF_UPDATE_INTERVAL_LIVE]:
        return {CONF_UPDATE_INTERVAL_STATS: "invalid_update_interval_stats"}

    return {}


class OptionsFlowHandler(OptionsFlow):
    """Change the configuration (options) of an existing instance of the integration.

    Attributes:
        _pending (dict[str, Any]): The submitted options waiting for the confirmation of an untrusted certificate.
        _certificate_fingerprint (str | None): SHA-256 fingerprint of the certificate read from the Pi-hole, awaiting confirmation.

    """

    def __init__(self) -> None:
        """Initialize the options flow."""
        self._pending: dict[str, Any] = {}
        self._certificate_fingerprint: str | None = None

    async def async_step_pin_certificate(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask the user to confirm the certificate before enabling its verification in the options.

        Args:
            user_input (dict[str, Any] | None): The input submitted by the user, or None when displaying the form.

        Returns:
            ConfigFlowResult: The result of the confirmation step.

        """
        errors: dict[str, str] = {}

        if self._certificate_fingerprint is None:
            try:
                self._certificate_fingerprint = await async_get_certificate_fingerprint(
                    self.hass, self._pending[CONF_URL]
                )
            except (OSError, ValueError, ssl.SSLError):
                return self.async_abort(reason="cannot_connect")

        if user_input is not None:
            if not user_input.get(CONF_CONFIRM_CERTIFICATE):
                errors[CONF_CONFIRM_CERTIFICATE] = "certificate_not_confirmed"
            else:
                self._pending[CONF_CERT_FINGERPRINT] = self._certificate_fingerprint
                connection_errors, _ = await _async_check_connection(
                    self.hass, {**self.config_entry.data, **self._pending}
                )
                if not connection_errors:
                    self.hass.config_entries.async_update_entry(
                        self.config_entry, data={**self.config_entry.data, **self._pending}
                    )
                    return self.async_create_entry(title="", data={})
                errors = connection_errors
                self._pending.pop(CONF_CERT_FINGERPRINT, None)

        return self.async_show_form(
            step_id="pin_certificate",
            data_schema=_get_pin_certificate_schema(),
            errors=errors,
            description_placeholders={
                "url": self._pending[CONF_URL],
                "fingerprint": self._certificate_fingerprint or "",
            },
        )

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

            if not errors and user_input[CONF_VERIFY_SSL]:
                # Enabling verification must not leave the integration broken: test the connection first.
                connection_errors, untrusted = await _async_check_connection(
                    self.hass, {**self.config_entry.data, **user_input}
                )
                if untrusted:
                    self._pending = dict(user_input)
                    self._certificate_fingerprint = None
                    return await self.async_step_pin_certificate()
                errors = connection_errors

            if not errors:
                _warn_insecure_settings(user_input[CONF_URL], user_input[CONF_VERIFY_SSL])
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

        update_interval_live = self.config_entry.data.get(CONF_UPDATE_INTERVAL_LIVE, None)
        update_interval_stats = self.config_entry.data.get(CONF_UPDATE_INTERVAL_STATS, None)
        enable_device_tracker = self.config_entry.data.get(CONF_ENABLE_DEVICE_TRACKER, None)
        device_tracker_whitelist = self.config_entry.data.get(CONF_DEVICE_TRACKER_WHITELIST, None)
        device_tracker_mac_list = self.config_entry.data.get(CONF_DEVICE_TRACKER_MAC_LIST, None)

        if (
            update_interval_live is None
            or update_interval_stats is None
            or enable_device_tracker is None
            or device_tracker_whitelist is None
            or device_tracker_mac_list is None
        ):
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={
                    **self.config_entry.data,
                    CONF_UPDATE_INTERVAL_LIVE: update_interval_live or MIN_TIME_BETWEEN_UPDATES_LIVE.seconds,
                    CONF_UPDATE_INTERVAL_STATS: (update_interval_stats or MIN_TIME_BETWEEN_UPDATES_STATS.seconds),
                    CONF_ENABLE_DEVICE_TRACKER: (
                        DEFAULT_ENABLE_DEVICE_TRACKER if enable_device_tracker is None else enable_device_tracker
                    ),
                    CONF_DEVICE_TRACKER_WHITELIST: (
                        DEFAULT_DEVICE_TRACKER_WHITELIST
                        if device_tracker_whitelist is None
                        else device_tracker_whitelist
                    ),
                    CONF_DEVICE_TRACKER_MAC_LIST: (
                        DEFAULT_DEVICE_TRACKER_MAC_LIST if device_tracker_mac_list is None else device_tracker_mac_list
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
