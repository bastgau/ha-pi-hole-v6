"""Check the network device tracker with its away delay and its stale device setting, through a real setup.

The data fetches are replaced by fake ones filling the network device cache of the client from a holder the
tests edit, so nothing reaches the network. Time is frozen: a device is "N seconds old" relative to it.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.pi_hole_v6.api import Api
from custom_components.pi_hole_v6.const import (
    CONF_DEVICE_TRACKER_CONSIDER_HOME,
    CONF_DEVICE_TRACKER_MAC_LIST,
    CONF_DEVICE_TRACKER_STALE_DAYS,
    CONF_DEVICE_TRACKER_WHITELIST,
    CONF_ENABLE_DEVICE_TRACKER,
    CONF_UPDATE_INTERVAL_LIVE,
    CONF_UPDATE_INTERVAL_STATS,
    DOMAIN,
)
from custom_components.pi_hole_v6.device_tracker import PiHoleV6DeviceTracker, _has_registered_entity
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_URL,
    STATE_HOME,
    STATE_NOT_HOME,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Iterator

    from custom_components.pi_hole_v6 import PiHoleV6ConfigEntry
    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant

INTEGRATION = "custom_components.pi_hole_v6"
FIXTURES = Path(__file__).parent / "fixtures"
URL = "https://pihole.example/api"
NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
DAY = 86400
STALE = 60 * DAY
FRESH = 60


def _template(label: str) -> dict[str, Any]:
    """Return a fresh copy of one device of the network devices fixture."""
    devices = json.loads((FIXTURES / "network_devices.json").read_text(encoding="utf-8"))
    return devices[label]


def _mac(label: str) -> str:
    """Return the MAC address of a fixture device."""
    return _template(label)["hwaddr"]


def _device(label: str, age: int | None, *, at: datetime = NOW) -> dict[str, Any]:
    """Return a fixture device whose last query is `age` seconds before `at`, or without any last query."""
    device = _template(label)
    if age is not None:
        device["lastQuery"] = int(at.timestamp()) - age
    return device


class Harness:
    """Load the entry with only the device tracker platform, and drive its refreshes."""

    def __init__(self, hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
        """Keep the Home Assistant instance and the clock, and prepare an empty network."""
        self.hass = hass
        self.freezer = freezer
        self.devices: list[dict[str, Any]] = []
        self.failing = False
        self.live_calls = 0
        self.entry: PiHoleV6ConfigEntry | None = None

    def make_entry(self, **options: Any) -> MockConfigEntry:
        """Add to Home Assistant an entry with tracking enabled, plus the given options (a None value removes a key)."""
        data: dict[str, Any] = {
            CONF_NAME: "Pihole",
            CONF_URL: URL,
            CONF_PASSWORD: "pw",
            CONF_UPDATE_INTERVAL_LIVE: 120,
            CONF_UPDATE_INTERVAL_STATS: 300,
            CONF_ENABLE_DEVICE_TRACKER: True,
        }
        for key, value in options.items():
            if value is None:
                data.pop(key, None)
            else:
                data[key] = value
        entry = MockConfigEntry(domain=DOMAIN, unique_id=URL, data=data)
        entry.add_to_hass(self.hass)
        self.entry = entry  # type: ignore[assignment]
        return entry

    def prefill(self, label: str) -> None:
        """Create the device and the entity of a tracked device in the registries, as a previous run left them.

        ScannerEntity uses the bare MAC address as unique id, whatever `_attr_unique_id` says, so that is the id registered.
        """
        assert self.entry is not None
        mac = _mac(label)
        device = dr.async_get(self.hass).async_get_or_create(
            config_entry_id=self.entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, mac)},
            name=f"device {label}",
        )
        er.async_get(self.hass).async_get_or_create(
            Platform.DEVICE_TRACKER,
            DOMAIN,
            mac,
            config_entry=self.entry,
            device_id=device.id,
            disabled_by=None,
        )

    @contextmanager
    def fetches(self) -> Iterator[None]:
        """Replace every fetch: the live one copies `self.devices` into the cache, or fails."""

        async def fake_live(api_client: Api, **_: Any) -> None:
            """Fill the network device cache like the live fetch does."""
            self.live_calls += 1
            if self.failing:
                message = "down"
                raise UpdateFailed(message)
            api_client.cache_network_devices = [dict(device) for device in self.devices]

        with (
            patch(f"{INTEGRATION}.PLATFORMS", [Platform.DEVICE_TRACKER]),
            # Home Assistant registers a scanner entity disabled by default, which writes no state: enable it so
            # that the states under test exist. Whether an entity is created is read from the registry.
            patch.object(PiHoleV6DeviceTracker, "_attr_entity_registry_enabled_default", new=True),
            patch(f"{INTEGRATION}.async_get_live_data", AsyncMock(side_effect=fake_live)),
            patch(f"{INTEGRATION}.async_get_stats_data", AsyncMock()),
            patch.object(Api, "call_get_ftl_info_messages", AsyncMock(return_value={})),
            patch.object(Api, "call_logout", AsyncMock()),
        ):
            yield

    async def setup(self) -> PiHoleV6ConfigEntry:
        """Set the entry up."""
        assert self.entry is not None
        with self.fetches():
            await self.hass.config_entries.async_setup(self.entry.entry_id)
            await self.hass.async_block_till_done()
        assert self.entry.state is ConfigEntryState.LOADED
        return self.entry

    async def refresh(self) -> None:
        """Run one live refresh, the way the coordinator does when its interval elapses."""
        assert self.entry is not None
        api = self.entry.runtime_data.api
        api.just_initialized = dict.fromkeys(api.just_initialized, False)
        with self.fetches():
            await self.entry.runtime_data.coordinator.async_refresh()
            await self.hass.async_block_till_done()

    def advance(self, seconds: float) -> None:
        """Move the frozen clock forward."""
        self.freezer.tick(timedelta(seconds=seconds))

    def entity_id(self, label: str) -> str | None:
        """Return the entity id registered for a fixture device, None when it has no entity."""
        assert self.entry is not None
        return er.async_get(self.hass).async_get_entity_id(Platform.DEVICE_TRACKER, DOMAIN, _mac(label))

    def state(self, label: str) -> str | None:
        """Return the state of the entity of a fixture device, None when there is no such state."""
        entity_id = self.entity_id(label)
        state = self.hass.states.get(entity_id) if entity_id else None
        return state.state if state else None

    def has_device(self, label: str) -> bool:
        """Tell whether the device registry holds a device with the MAC of a fixture device."""
        assert self.entry is not None
        return bool(
            dr.async_get(self.hass).async_get_devices(
                connections={(dr.CONNECTION_NETWORK_MAC, _mac(label))}, config_entry_id=self.entry.entry_id
            )
        )


@pytest.fixture(name="expected_lingering_timers")
def expected_lingering_timers_fixture() -> bool:
    """Accept the timer of a platform that outlives an entry which could not be unloaded cleanly."""
    return True


@pytest.fixture(name="harness")
async def harness_fixture(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> AsyncGenerator[Harness]:
    """Return a harness on the frozen clock, unloading its entry afterwards to stop the coordinators."""
    freezer.move_to(NOW)
    harness = Harness(hass, freezer)
    yield harness
    if harness.entry is not None and harness.entry.state is ConfigEntryState.LOADED:
        with patch.object(Api, "call_logout", AsyncMock()):
            await hass.config_entries.async_unload(harness.entry.entry_id)
            await hass.async_block_till_done()


# --------------------------------------------------------------------------------------------------
# Away delay
# --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("age", "expected"),
    [(0, STATE_HOME), (239, STATE_HOME), (240, STATE_HOME), (241, STATE_NOT_HOME), (3600, STATE_NOT_HOME)],
)
async def test_default_delay_is_the_historic_240_seconds(harness: Harness, age: int, expected: str) -> None:
    """An entry that stores no away delay keeps the former threshold of 240 seconds."""
    harness.make_entry()
    harness.devices = [_device("B", age)]

    await harness.setup()

    assert harness.state("B") == expected


@pytest.mark.parametrize(
    ("option", "age", "expected"),
    [
        (600, 500, STATE_HOME),
        (600, 600, STATE_HOME),
        (600, 601, STATE_NOT_HOME),
        (60, 61, STATE_NOT_HOME),
        (60, 59, STATE_HOME),
        (240, 241, STATE_NOT_HOME),
    ],
)
async def test_stored_delay_is_used(harness: Harness, option: int, age: int, expected: str) -> None:
    """The away delay stored in the entry replaces the default threshold."""
    harness.make_entry(**{CONF_DEVICE_TRACKER_CONSIDER_HOME: option})
    harness.devices = [_device("B", age)]

    await harness.setup()

    assert harness.state("B") == expected


@pytest.mark.parametrize("live_interval", [30, 120, 900])
async def test_delay_does_not_depend_on_the_live_refresh_interval(harness: Harness, live_interval: int) -> None:
    """The default threshold stays at 240 seconds whatever the live refresh frequency."""
    harness.make_entry(**{CONF_UPDATE_INTERVAL_LIVE: live_interval})
    harness.devices = [_device("A", 239), _device("B", 241)]

    await harness.setup()

    assert harness.state("A") == STATE_HOME
    assert harness.state("B") == STATE_NOT_HOME


@pytest.mark.parametrize("value", [True, "600", None, [600]], ids=repr)
async def test_unusable_stored_delay_falls_back_to_the_default(harness: Harness, value: Any) -> None:
    """A stored delay that is not a number gives the default threshold instead of an error."""
    harness.make_entry(**{CONF_DEVICE_TRACKER_CONSIDER_HOME: value})
    harness.devices = [_device("A", 239), _device("B", 300)]

    await harness.setup()

    assert harness.state("A") == STATE_HOME
    assert harness.state("B") == STATE_NOT_HOME


@pytest.mark.parametrize("missing", ["absent", "zero", "none"])
async def test_missing_last_query_is_not_home_without_error(harness: Harness, missing: str) -> None:
    """A device without a usable last query is away, the state is still written and nothing raises."""
    harness.make_entry()
    device = _device("B", None)
    if missing == "zero":
        device["lastQuery"] = 0
    elif missing == "none":
        device["lastQuery"] = None
    harness.devices = [device, _device("A", FRESH)]

    await harness.setup()

    assert harness.state("B") == STATE_NOT_HOME
    assert harness.state("A") == STATE_HOME
    state = harness.hass.states.get(harness.entity_id("B") or "")
    assert state is not None
    assert "last_query" not in state.attributes


async def test_changing_the_delay_applies_without_a_reload(harness: Harness) -> None:
    """A new value is read at the next evaluation of the state, with the entry kept loaded."""
    entry = harness.make_entry()
    harness.devices = [_device("B", 300)]
    await harness.setup()
    assert harness.state("B") == STATE_NOT_HOME

    harness.hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_DEVICE_TRACKER_CONSIDER_HOME: 600})
    entry.runtime_data.coordinator.async_update_listeners()
    await harness.hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert harness.state("B") == STATE_HOME

    harness.hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_DEVICE_TRACKER_CONSIDER_HOME: 100})
    entry.runtime_data.coordinator.async_update_listeners()
    await harness.hass.async_block_till_done()

    assert harness.state("B") == STATE_NOT_HOME


async def test_device_going_quiet_becomes_not_home_when_time_passes(harness: Harness) -> None:
    """With an unchanged last query, the state follows the clock at the next refresh."""
    harness.make_entry()
    harness.devices = [_device("B", 10)]
    await harness.setup()
    assert harness.state("B") == STATE_HOME

    harness.advance(300)
    await harness.refresh()

    assert harness.state("B") == STATE_NOT_HOME


async def test_entity_without_a_config_entry_uses_the_default_delay() -> None:
    """An entity whose coordinator carries no config entry falls back to the default threshold."""
    coordinator = MagicMock()
    coordinator.name = "Pihole"
    coordinator.config_entry = None
    api = MagicMock()
    device = _device("B", 100, at=datetime.now(UTC))
    api.cache_network_devices = [device]
    entity = PiHoleV6DeviceTracker(api, coordinator, "server", device)

    assert entity.is_connected is True

    api.cache_network_devices = [{**device, "lastQuery": int(datetime.now(UTC).timestamp()) - 1000}]
    assert entity.is_connected is False

    api.cache_network_devices = []
    assert entity.is_connected is False


# --------------------------------------------------------------------------------------------------
# Restart with registries already filled
# --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("stale_days", [30, 0])
async def test_restart_keeps_every_entity_and_device(harness: Harness, stale_days: int) -> None:
    """Nothing is removed at setup: a stale tracked device is attached again and stays away, an absent one stays."""
    harness.make_entry(**{CONF_DEVICE_TRACKER_STALE_DAYS: stale_days})
    for label in "ABC":
        harness.prefill(label)
    harness.devices = [_device("A", STALE), _device("B", FRESH)]

    await harness.setup()

    for label in "ABC":
        assert harness.entity_id(label) is not None, label
        assert harness.has_device(label), label
    assert harness.state("A") == STATE_NOT_HOME
    assert harness.state("B") == STATE_HOME
    assert harness.state("C") != STATE_HOME


async def test_restart_keeps_a_stale_device_that_never_queried(harness: Harness) -> None:
    """A registered device without last query is attached again, not dropped, and reports away."""
    harness.make_entry(**{CONF_DEVICE_TRACKER_STALE_DAYS: 30})
    harness.prefill("A")
    harness.devices = [_device("A", None)]

    await harness.setup()

    assert harness.state("A") == STATE_NOT_HOME
    assert harness.has_device("A")


async def test_empty_registries_only_get_the_active_device(harness: Harness) -> None:
    """A stale device without entity is not created; an active one is."""
    harness.make_entry(**{CONF_DEVICE_TRACKER_STALE_DAYS: 30})
    harness.devices = [_device("D", STALE), _device("E", FRESH)]

    await harness.setup()

    assert harness.state("E") == STATE_HOME
    assert harness.has_device("E")
    assert harness.entity_id("D") is None
    assert not harness.has_device("D")
    entity_registry = er.async_get(harness.hass)
    assert len(er.async_entries_for_config_entry(entity_registry, harness.entry.entry_id)) == 1  # type: ignore[union-attr]


async def test_empty_registries_without_the_setting_create_everything(harness: Harness) -> None:
    """With the setting at 0 (default), the stale device gets its entity, as before."""
    harness.make_entry()
    harness.devices = [_device("D", STALE), _device("E", FRESH)]

    await harness.setup()

    assert harness.state("D") == STATE_NOT_HOME
    assert harness.state("E") == STATE_HOME


# --------------------------------------------------------------------------------------------------
# While running
# --------------------------------------------------------------------------------------------------


async def test_tracked_device_that_becomes_stale_keeps_its_entity(harness: Harness) -> None:
    """A device that ages beyond the limit while tracked is neither removed nor made unavailable."""
    harness.make_entry(**{CONF_DEVICE_TRACKER_STALE_DAYS: 30})
    harness.devices = [_device("B", FRESH)]
    await harness.setup()
    assert harness.state("B") == STATE_HOME
    entity_id = harness.entity_id("B")

    harness.advance(60 * DAY)
    with patch.object(PiHoleV6DeviceTracker, "async_remove", AsyncMock()) as remove:
        await harness.refresh()

    remove.assert_not_called()
    assert harness.entity_id("B") == entity_id
    assert harness.state("B") == STATE_NOT_HOME
    assert harness.has_device("B")


async def test_stale_device_that_comes_back_is_created(harness: Harness) -> None:
    """A device ignored for being stale gets its entity as soon as it queries again."""
    harness.make_entry(**{CONF_DEVICE_TRACKER_STALE_DAYS: 30})
    harness.devices = [_device("D", STALE)]
    await harness.setup()
    assert harness.entity_id("D") is None

    harness.advance(120)
    await harness.refresh()
    assert harness.entity_id("D") is None

    harness.devices = [_device("D", 5, at=NOW + timedelta(seconds=240))]
    harness.advance(120)
    await harness.refresh()

    assert harness.state("D") == STATE_HOME
    assert harness.has_device("D")


async def test_new_stale_device_appearing_while_running_is_not_created(harness: Harness) -> None:
    """The filter applies to devices appearing in later refreshes too."""
    harness.make_entry(**{CONF_DEVICE_TRACKER_STALE_DAYS: 30})
    harness.devices = [_device("E", FRESH)]
    await harness.setup()

    harness.devices = [_device("E", FRESH), _device("D", STALE), _device("C", None)]
    harness.advance(120)
    await harness.refresh()

    assert harness.entity_id("D") is None
    assert harness.entity_id("C") is None
    assert harness.entity_id("E") is not None


async def test_device_absent_from_the_response_keeps_its_entity(harness: Harness) -> None:
    """A tracked device Pi-hole stops reporting stays, away, whatever the setting."""
    harness.make_entry(**{CONF_DEVICE_TRACKER_STALE_DAYS: 30})
    harness.devices = [_device("B", FRESH), _device("E", FRESH)]
    await harness.setup()

    harness.devices = [_device("E", FRESH)]
    harness.advance(120)
    await harness.refresh()

    assert harness.entity_id("B") is not None
    assert harness.state("B") == STATE_NOT_HOME


@pytest.mark.parametrize(
    ("stale_days", "created"),
    [(30, False), (0, True)],
)
async def test_failed_refresh_creates_no_device_when_the_setting_is_on(
    harness: Harness, stale_days: int, created: bool
) -> None:
    """After a failed refresh the cache is not trusted: no unknown device is created, none is removed."""
    harness.make_entry(**{CONF_DEVICE_TRACKER_STALE_DAYS: stale_days})
    harness.devices = [_device("B", FRESH)]
    entry = await harness.setup()

    # The cache holds a new device that looks active when the refresh fails.
    entry.runtime_data.api.cache_network_devices = [_device("B", FRESH), _device("D", FRESH)]
    harness.failing = True
    harness.advance(120)
    with patch.object(PiHoleV6DeviceTracker, "async_remove", AsyncMock()) as remove:
        await harness.refresh()

    remove.assert_not_called()
    assert entry.runtime_data.coordinator.last_update_success is False
    assert harness.entity_id("B") is not None
    assert (harness.entity_id("D") is not None) is created
    assert harness.has_device("D") is created


async def test_failed_refresh_still_attaches_a_registered_device(harness: Harness) -> None:
    """A device already in the entity registry is attached even when the refresh failed, then unavailable."""
    harness.make_entry(**{CONF_DEVICE_TRACKER_STALE_DAYS: 30})
    harness.devices = [_device("E", FRESH)]
    entry = await harness.setup()
    harness.prefill("A")

    entry.runtime_data.api.cache_network_devices = [_device("E", FRESH), _device("A", STALE)]
    harness.failing = True
    harness.advance(120)
    await harness.refresh()

    # A failed refresh makes every coordinator entity unavailable, the reattached one included.
    assert harness.entity_id("A") is not None
    assert harness.state("A") == STATE_UNAVAILABLE


async def test_recovery_after_a_failed_refresh_creates_the_active_device(harness: Harness) -> None:
    """Once the source answers again, the device skipped during the failure is created."""
    harness.make_entry(**{CONF_DEVICE_TRACKER_STALE_DAYS: 30})
    harness.devices = [_device("B", FRESH)]
    entry = await harness.setup()

    entry.runtime_data.api.cache_network_devices = [_device("B", FRESH), _device("D", FRESH)]
    harness.failing = True
    harness.advance(120)
    await harness.refresh()
    assert harness.entity_id("D") is None

    harness.failing = False
    harness.devices = [_device("B", FRESH, at=NOW + timedelta(seconds=240)), _device("D", FRESH)]
    harness.advance(120)
    await harness.refresh()

    assert harness.entity_id("D") is not None


# --------------------------------------------------------------------------------------------------
# Whitelist, blacklist, last query of 0
# --------------------------------------------------------------------------------------------------


async def test_stale_device_of_the_whitelist_is_kept(harness: Harness) -> None:
    """The listed device is created however old it is, and the unlisted one is still left out."""
    harness.make_entry(
        **{
            CONF_DEVICE_TRACKER_STALE_DAYS: 30,
            CONF_DEVICE_TRACKER_WHITELIST: True,
            CONF_DEVICE_TRACKER_MAC_LIST: _mac("A"),
        }
    )
    harness.devices = [_device("A", STALE), _device("B", FRESH)]

    await harness.setup()

    assert harness.state("A") == STATE_NOT_HOME
    assert harness.entity_id("B") is None


async def test_whitelist_device_without_last_query_is_kept(harness: Harness) -> None:
    """A listed device that never queried still gets its entity."""
    harness.make_entry(
        **{
            CONF_DEVICE_TRACKER_STALE_DAYS: 30,
            CONF_DEVICE_TRACKER_WHITELIST: True,
            CONF_DEVICE_TRACKER_MAC_LIST: _mac("A"),
        }
    )
    harness.devices = [_device("A", None)]

    await harness.setup()

    assert harness.state("A") == STATE_NOT_HOME


async def test_whitelist_mode_with_an_empty_list_filters_stale_devices(harness: Harness) -> None:
    """In whitelist mode an empty list names nobody: the stale filter applies."""
    harness.make_entry(
        **{CONF_DEVICE_TRACKER_STALE_DAYS: 30, CONF_DEVICE_TRACKER_WHITELIST: True, CONF_DEVICE_TRACKER_MAC_LIST: ""}
    )
    harness.devices = [_device("A", STALE), _device("B", FRESH)]

    await harness.setup()

    assert harness.entity_id("A") is None
    assert harness.state("B") == STATE_HOME


async def test_blacklist_filters_stale_devices_and_excludes_the_listed_one(harness: Harness) -> None:
    """In blacklist mode the listed device stays excluded and the stale filter applies to the others."""
    harness.make_entry(
        **{
            CONF_DEVICE_TRACKER_STALE_DAYS: 30,
            CONF_DEVICE_TRACKER_WHITELIST: False,
            CONF_DEVICE_TRACKER_MAC_LIST: _mac("C"),
        }
    )
    harness.devices = [_device("A", STALE), _device("B", FRESH), _device("C", FRESH)]

    await harness.setup()

    assert harness.entity_id("A") is None
    assert harness.state("B") == STATE_HOME
    assert harness.entity_id("C") is None


async def test_listed_blacklist_device_is_still_removed_while_running(harness: Harness) -> None:
    """The address filter keeps removing a tracked device it rejects, stale setting or not."""
    entry = harness.make_entry(**{CONF_DEVICE_TRACKER_STALE_DAYS: 30})
    harness.devices = [_device("B", FRESH), _device("E", FRESH)]
    await harness.setup()
    assert harness.state("B") == STATE_HOME

    harness.hass.config_entries.async_update_entry(
        entry,
        data={**entry.data, CONF_DEVICE_TRACKER_WHITELIST: False, CONF_DEVICE_TRACKER_MAC_LIST: _mac("B")},
    )
    harness.advance(120)
    await harness.refresh()

    # The entity left the state machine: only the placeholder of its registry entry remains.
    assert harness.state("B") in (None, STATE_UNAVAILABLE)
    assert harness.state("E") == STATE_HOME


@pytest.mark.parametrize("variant", ["zero", "absent", "none"])
@pytest.mark.parametrize(
    ("stale_days", "has_entity"),
    [(30, False), (0, True)],
)
async def test_zero_last_query(harness: Harness, variant: str, stale_days: int, has_entity: bool) -> None:
    """Without usable last query: no entity when the filter is on, an away entity when it is off."""
    harness.make_entry(**{CONF_DEVICE_TRACKER_STALE_DAYS: stale_days})
    device = _device("A", None)
    if variant == "zero":
        device["lastQuery"] = 0
    elif variant == "none":
        device["lastQuery"] = None
    harness.devices = [device]

    await harness.setup()

    assert (harness.entity_id("A") is not None) is has_entity
    assert harness.state("A") == (STATE_NOT_HOME if has_entity else None)


async def test_tracking_disabled_removes_the_registries_as_before(harness: Harness) -> None:
    """Switching the tracking off still purges the network devices: the stale setting changes nothing there."""
    harness.make_entry(**{CONF_ENABLE_DEVICE_TRACKER: False, CONF_DEVICE_TRACKER_STALE_DAYS: 30})
    harness.prefill("A")

    await harness.setup()

    assert harness.entity_id("A") is None
    assert not harness.has_device("A")


# --------------------------------------------------------------------------------------------------
# Registry lookup
# --------------------------------------------------------------------------------------------------


def _register(hass: HomeAssistant, entry: MockConfigEntry, unique_id: str) -> None:
    """Register a device_tracker entity of an entry under the given unique id."""
    er.async_get(hass).async_get_or_create(Platform.DEVICE_TRACKER, DOMAIN, unique_id, config_entry=entry)


def _other_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Add a second entry of the integration."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="https://other.example/api", data={CONF_URL: "x"})
    entry.add_to_hass(hass)
    return entry


@pytest.mark.parametrize("legacy", [False, True], ids=["bare-mac", "entry-id-prefixed"])
async def test_registered_entity_is_found(hass: HomeAssistant, legacy: bool) -> None:
    """An entity of the entry is found under the bare MAC, or under the older '{entry_id}/{mac}' form."""
    entry = _other_entry(hass)
    mac = _mac("A")
    _register(hass, entry, f"{entry.entry_id}/{mac}" if legacy else mac)

    assert _has_registered_entity(er.async_get(hass), entry.entry_id, mac) is True


async def test_entity_of_another_entry_is_not_retained(hass: HomeAssistant) -> None:
    """The same MAC tracked by another entry does not count, in either form."""
    entry = _other_entry(hass)
    other = MockConfigEntry(domain=DOMAIN, unique_id="https://third.example/api", data={CONF_URL: "y"})
    other.add_to_hass(hass)
    _register(hass, other, _mac("A"))
    _register(hass, other, f"{entry.entry_id}/{_mac('B')}")

    registry = er.async_get(hass)
    assert _has_registered_entity(registry, entry.entry_id, _mac("A")) is False
    assert _has_registered_entity(registry, entry.entry_id, _mac("B")) is False


async def test_unregistered_mac_is_not_found(hass: HomeAssistant) -> None:
    """A MAC without any entity gives False, even when other devices are registered."""
    entry = _other_entry(hass)
    _register(hass, entry, _mac("A"))

    assert _has_registered_entity(er.async_get(hass), entry.entry_id, _mac("B")) is False
