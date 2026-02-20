"""The pi_hole_v6 component."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_URL,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import Api as PiholeAPI
from .const import CONF_UPDATE_INTERVAL, DOMAIN, MIN_TIME_BETWEEN_UPDATES
from .exceptions import APIError, DataStructureError, UnauthorizedError

if TYPE_CHECKING:
    from aiohttp import client

    from homeassistant.core import Event, HomeAssistant


_LOGGER = logging.getLogger(__name__)


PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]

type PiHoleV6ConfigEntry = ConfigEntry[PiHoleV6Data]


@dataclass
class PiHoleV6Data:
    """Runtime data definition."""

    api: PiholeAPI
    coordinator: DataUpdateCoordinator[Any]


async def check_result(result: Any, api_client: PiholeAPI) -> None:
    """Check that the API result is a valid dictionary.

    If the result is not a dict, logs an error, calls logout and raises DataStructureError.

    Args:
        result (Any): The result returned by the API call.
        api_client (PiholeAPI): The Pi-hole API client instance used to call logout.

    """

    if not isinstance(result, dict):
        await api_client.call_logout()
        _LOGGER.error("DataStructureError Debug: %s", str(result))
        raise DataStructureError


async def async_get_all_data(api_client: PiholeAPI) -> None:
    """Fetch all required data from the Pi-hole API.

    Sequentially calls each API endpoint and validates the result structure.

    Args:
        api_client (PiholeAPI): The Pi-hole API client instance used to perform the calls.

    """

    result = await api_client.call_summary()
    await check_result(result, api_client)

    result = await api_client.call_blocking_status()
    await check_result(result, api_client)

    result = await api_client.call_get_groups()
    await check_result(result, api_client)

    result = await api_client.call_padd()
    await check_result(result, api_client)

    result = await api_client.call_get_ftl_info_messages_count()
    await check_result(result, api_client)

    result = await api_client.call_get_configured_clients()
    await check_result(result, api_client)

    result = await api_client.call_get_dhcp_leases()
    await check_result(result, api_client)

    result = await api_client.call_get_auth_sessions()
    await check_result(result, api_client)


async def async_setup_entry(hass: HomeAssistant, entry: PiHoleV6ConfigEntry) -> bool:
    """Set up Pi-hole V6 entry."""

    password = entry.data.get(CONF_PASSWORD, "")
    name = entry.data[CONF_NAME]
    url = entry.data[CONF_URL]

    _LOGGER.debug("Setting up %s integration with host %s", DOMAIN, url)

    session: client.ClientSession = async_get_clientsession(hass, verify_ssl=False)

    api_client: PiholeAPI = PiholeAPI(
        session=session,
        url=url,
        password=password,
    )

    async def async_logout(_: Event) -> None:
        await api_client.call_logout()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_logout))

    async def async_update_data() -> dict[str, Any] | None:
        """Fetch data from API endpoint."""

        if api_client.just_initialized is True:
            api_client.just_initialized = False
            return None

        api_client.last_refresh = datetime.now(UTC)

        result: Any = {}

        try:
            await async_get_all_data(api_client=api_client)

        except UnauthorizedError as err:
            msg: str = "Credentials must be updated."
            raise ConfigEntryAuthFailed(msg) from err

        try:
            result = await api_client.call_get_ftl_info_messages()
            if not isinstance(result, dict):
                api_client.remove_cache("ftl_info_messages")
                _LOGGER.error("DataStructureError Debug: %s", str(result))
                raise DataStructureError

        except APIError:
            api_client.remove_cache("ftl_info_messages")
        finally:
            await api_client.call_logout()

        api_client.last_refresh = datetime.now(UTC)

        return {"last_refresh": api_client.last_refresh}

    conf_update_interval: int | None = entry.data.get(CONF_UPDATE_INTERVAL)

    if conf_update_interval is None:
        update_interval = MIN_TIME_BETWEEN_UPDATES
    else:
        update_interval = timedelta(seconds=conf_update_interval)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        config_entry=entry,
        name=name,
        update_method=async_update_data,
        update_interval=update_interval,
        always_update=False,
    )

    await coordinator.async_config_entry_first_refresh()
    api_client.just_initialized = True

    entry.runtime_data = PiHoleV6Data(api_client, coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Pi-hole entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
