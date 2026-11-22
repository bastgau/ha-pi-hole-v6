"""Check the presence block of the diagnostics: its shape, its values, and that it holds counters only."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

from custom_components.pi_hole_v6.api import Api
from custom_components.pi_hole_v6.const import (
    CONF_ENABLE_DEVICE_TRACKER,
    CONF_UPDATE_INTERVAL_LIVE,
    CONF_UPDATE_INTERVAL_PRESENCE,
    CONF_UPDATE_INTERVAL_STATS,
    DOMAIN,
)
from custom_components.pi_hole_v6.diagnostics import async_get_config_entry_diagnostics
from custom_components.pi_hole_v6.presence import PresenceSnapshot
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_URL

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from custom_components.pi_hole_v6 import PiHoleV6ConfigEntry

    from homeassistant.core import HomeAssistant

INTEGRATION = "custom_components.pi_hole_v6"
URL = "https://pihole.example:8443/api"
MAC = "aa:bb:cc:dd:ee:ff"
IP = "192.168.77.42"
DOMAIN_MARKER = "presence.domain.marker.example"
PSEUDO_MAC = "ip-192.168.77.43"
FETCHED_AT = datetime(2026, 6, 1, 12, 0, 30, tzinfo=UTC)
MARKERS = [MAC, IP, DOMAIN_MARKER, PSEUDO_MAC, "192.168.77", "aa:bb"]
BLOCK_KEYS = {"enabled", "listening", "update_interval", "last_update_success", "last_exception", "last_read"}
LAST_READ_KEYS = {
    "fetched_at",
    "complete",
    "pages",
    "queries_read",
    "duration_seconds",
    "clients_seen",
    "clients_matched",
}


def _entry(**overrides: Any) -> MockConfigEntry:
    """Build a config entry with the network tracking and the presence refresh enabled."""
    data: dict[str, Any] = {
        CONF_NAME: "Pi-hole",
        CONF_URL: URL,
        CONF_PASSWORD: "pw",
        CONF_UPDATE_INTERVAL_LIVE: 30,
        CONF_UPDATE_INTERVAL_STATS: 600,
        CONF_ENABLE_DEVICE_TRACKER: True,
        CONF_UPDATE_INTERVAL_PRESENCE: 30,
    }
    for key, value in overrides.items():
        if value is None:
            data.pop(key, None)
        else:
            data[key] = value
    return MockConfigEntry(domain=DOMAIN, unique_id=URL, data=data)


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> PiHoleV6ConfigEntry:
    """Set the entry up without entities and with the data fetches replaced, so nothing reaches the network."""
    entry.add_to_hass(hass)

    with (
        patch(f"{INTEGRATION}.PLATFORMS", []),
        patch(f"{INTEGRATION}.async_get_live_data", AsyncMock()),
        patch(f"{INTEGRATION}.async_get_stats_data", AsyncMock()),
        patch.object(Api, "call_get_ftl_info_messages", AsyncMock(return_value={})),
        patch.object(Api, "call_logout", AsyncMock()),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    return entry  # type: ignore[return-value]


@pytest.fixture(name="loaded")
async def loaded_fixture(hass: HomeAssistant) -> AsyncGenerator[PiHoleV6ConfigEntry]:
    """Return a loaded entry whose presence coordinator exists, unloaded afterwards."""
    entry = await _setup(hass, _entry())
    yield entry
    with patch.object(Api, "call_logout", AsyncMock()):
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


def _snapshot(**overrides: Any) -> PresenceSnapshot:
    """Return a snapshot whose maps hold markers that must stay out of the report."""
    values: dict[str, Any] = {
        "last_seen_by_mac": {MAC: 1700000000.5, PSEUDO_MAC: 1700000001.5},
        "fetched_at": FETCHED_AT,
        "complete": True,
        "pages": 2,
        "queries_read": 1500,
        "clients_seen": 7,
        "clients_matched": 5,
        "duration": 1.23456,
    }
    values.update(overrides)
    return PresenceSnapshot(**values)


async def test_enabled_coordinator_before_any_read(hass: HomeAssistant, loaded: PiHoleV6ConfigEntry) -> None:
    """The coordinator exists but has not read yet: nobody listens, there is no last read."""
    result = await async_get_config_entry_diagnostics(hass, loaded)

    assert result["presence"] == {
        "enabled": True,
        "listening": False,
        "update_interval": 30.0,
        "last_update_success": None,
        "last_exception": None,
        "last_read": None,
    }
    assert result["settings"]["update_interval_presence"] == 30
    assert set(result["coordinators"]) == {"live", "stats"}


async def test_last_read_has_the_documented_shape(hass: HomeAssistant, loaded: PiHoleV6ConfigEntry) -> None:
    """After a read the block holds the statistics of the read, as counters, with the duration rounded."""
    coordinator = loaded.runtime_data.coordinator_presence
    assert coordinator is not None
    coordinator.async_set_updated_data(_snapshot())

    presence = (await async_get_config_entry_diagnostics(hass, loaded))["presence"]

    assert set(presence) == BLOCK_KEYS
    assert presence["last_read"] == {
        "fetched_at": FETCHED_AT.isoformat(),
        "complete": True,
        "pages": 2,
        "queries_read": 1500,
        "duration_seconds": 1.235,
        "clients_seen": 7,
        "clients_matched": 5,
    }
    assert set(presence["last_read"]) == LAST_READ_KEYS
    assert presence["last_update_success"] is True


async def test_incomplete_read_is_reported(hass: HomeAssistant, loaded: PiHoleV6ConfigEntry) -> None:
    """The page limit or the time budget shows as complete = false."""
    coordinator = loaded.runtime_data.coordinator_presence
    assert coordinator is not None
    coordinator.async_set_updated_data(_snapshot(complete=False, pages=3))

    last_read = (await async_get_config_entry_diagnostics(hass, loaded))["presence"]["last_read"]

    assert last_read["complete"] is False
    assert last_read["pages"] == 3


async def test_listening_follows_the_listeners(hass: HomeAssistant, loaded: PiHoleV6ConfigEntry) -> None:
    """The block says whether a tracker listens, which is what makes the coordinator poll."""
    coordinator = loaded.runtime_data.coordinator_presence
    assert coordinator is not None

    remove = coordinator.async_add_listener(lambda: None)
    listening = (await async_get_config_entry_diagnostics(hass, loaded))["presence"]["listening"]
    remove()
    stopped = (await async_get_config_entry_diagnostics(hass, loaded))["presence"]["listening"]

    assert listening is True
    assert stopped is False


async def test_failure_is_reported_by_class_name_only(hass: HomeAssistant, loaded: PiHoleV6ConfigEntry) -> None:
    """A failed read gives the class name of the error, and the last good read stays."""
    coordinator = loaded.runtime_data.coordinator_presence
    assert coordinator is not None
    coordinator.async_set_updated_data(_snapshot())
    coordinator.last_update_success = False
    coordinator.last_read_error = "ForbiddenError"

    presence = (await async_get_config_entry_diagnostics(hass, loaded))["presence"]

    assert presence["last_update_success"] is False
    assert presence["last_exception"] == "ForbiddenError"
    assert presence["last_read"] is not None


@pytest.mark.parametrize("overrides", [{CONF_UPDATE_INTERVAL_PRESENCE: 0}, {CONF_UPDATE_INTERVAL_PRESENCE: None}])
async def test_disabled_presence_block(hass: HomeAssistant, overrides: dict[str, Any]) -> None:
    """With the option off the block says so and holds nothing else; the setting is 0 whether stored or not."""
    entry = await _setup(hass, _entry(**overrides))

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert entry.runtime_data.coordinator_presence is None
    assert result["presence"] == {
        "enabled": False,
        "listening": False,
        "update_interval": None,
        "last_update_success": None,
        "last_exception": None,
        "last_read": None,
    }
    assert result["settings"]["update_interval_presence"] == 0
    with patch.object(Api, "call_logout", AsyncMock()):
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_disabled_tracking_gives_a_disabled_block(hass: HomeAssistant) -> None:
    """The option is stored but the tracking is off: there is no coordinator, and the setting still reads 30."""
    entry = await _setup(hass, _entry(**{CONF_ENABLE_DEVICE_TRACKER: False}))

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["presence"]["enabled"] is False
    assert result["settings"]["update_interval_presence"] == 30
    with patch.object(Api, "call_logout", AsyncMock()):
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


@pytest.mark.parametrize("value", ["30", True, None, [30]], ids=repr)
async def test_unreadable_setting_is_null(hass: HomeAssistant, value: Any) -> None:
    """A stored value that is not a number is reported as null, never as is."""
    entry = _entry()
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_UPDATE_INTERVAL_PRESENCE: value})

    result = await async_get_config_entry_diagnostics(hass, entry)  # type: ignore[arg-type]

    assert result["settings"]["update_interval_presence"] is None


async def test_entry_not_loaded_has_no_presence_block(hass: HomeAssistant) -> None:
    """An entry that is not loaded reports its settings (with the presence one) and no runtime block."""
    entry = _entry()
    entry.add_to_hass(hass)

    result = await async_get_config_entry_diagnostics(hass, entry)  # type: ignore[arg-type]

    assert "presence" not in result
    assert result["settings"]["update_interval_presence"] == 30


async def test_nothing_personal_in_the_serialized_report(hass: HomeAssistant, loaded: PiHoleV6ConfigEntry) -> None:
    """No address, no MAC, no domain, no cursor and no window start reaches the report, whatever the snapshot holds."""
    coordinator = loaded.runtime_data.coordinator_presence
    assert coordinator is not None
    coordinator.async_set_updated_data(_snapshot())
    # In memory only, what the coordinator holds to build the next window: never reported.
    coordinator._since = 1700000123.456  # pylint: disable=protected-access
    coordinator._last_seen_by_ip = {IP: 1700000100.0}  # pylint: disable=protected-access
    coordinator.last_read_error = "ForbiddenError"
    loaded.runtime_data.api.cache_network_devices = [
        {"hwaddr": MAC, "lastQuery": 1700000000, "ips": [{"ip": IP, "name": DOMAIN_MARKER}]}
    ]

    result = await async_get_config_entry_diagnostics(hass, loaded)
    dumped = json.dumps(result)

    for marker in (*MARKERS, "1700000123", "1700000100"):
        assert marker not in dumped
    for value in result["presence"].values():
        assert value is None or isinstance(value, (bool, int, float, str, dict))
    for value in result["presence"]["last_read"].values():
        assert isinstance(value, (bool, int, float, str))


async def test_failure_before_any_read_is_a_real_false(hass: HomeAssistant, loaded: PiHoleV6ConfigEntry) -> None:
    """Once a read was attempted and failed, the flag is False even though no read ever succeeded."""
    coordinator = loaded.runtime_data.coordinator_presence
    assert coordinator is not None
    coordinator.last_update_success = False
    coordinator.last_read_error = "ForbiddenError"

    presence = (await async_get_config_entry_diagnostics(hass, loaded))["presence"]

    assert presence["last_update_success"] is False
    assert presence["last_read"] is None
