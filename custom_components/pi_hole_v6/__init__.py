"""The pi_hole_v6 component."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from homeassistant.config_entries import ConfigEntry, ConfigEntryAuthFailed
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_URL,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import API as PiholeAPI
from .const import CONF_UPDATE_INTERVAL, DOMAIN, MIN_TIME_BETWEEN_UPDATES
from .exceptions import DataStructureException, UnauthorizedException

_LOGGER = logging.getLogger(__name__)


PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
    Platform.BUTTON,
    # Platform.NUMBER,
]

type PiHoleV6ConfigEntry = ConfigEntry[PiHoleV6Data]


@dataclass
class PiHoleV6Data:
    """Runtime data definition."""

    api: PiholeAPI
    coordinator: DataUpdateCoordinator[None]


async def async_setup_entry(hass: HomeAssistant, entry: PiHoleV6ConfigEntry) -> bool:
    """Set up Pi-hole V6 entry."""
    password = entry.data.get(CONF_PASSWORD, "")
    name = entry.data[CONF_NAME]
    url = entry.data[CONF_URL]

    _LOGGER.debug("Setting up %s integration with host %s", DOMAIN, url)

    session = async_get_clientsession(hass, False)
    api_client = PiholeAPI(
        session=session,
        url=url,
        password=password,
        logger=_LOGGER,
    )

    async def async_logout(_: Event) -> None:
        await api_client.call_logout()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_logout))

    async def async_update_data() -> None:
        """Fetch data from API endpoint."""

        if api_client.just_initialized is True:
            api_client.just_initialized = False
            return None

        try:
            if not isinstance(await api_client.call_summary(), dict):
                raise DataStructureException()

            if not isinstance(await api_client.call_blocking_status(), dict):
                raise DataStructureException()

            if not isinstance(await api_client.call_padd(), dict):
                raise DataStructureException()

            if not isinstance(await api_client.call_get_groups(), dict):
                raise DataStructureException()

            api_client.last_refresh = datetime.now(timezone.utc)

        except UnauthorizedException as err:
            raise ConfigEntryAuthFailed("Credentials must be updated.") from err

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
    )

    await coordinator.async_config_entry_first_refresh()
    api_client.just_initialized = True

    entry.runtime_data = PiHoleV6Data(api_client, coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Pi-hole entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
