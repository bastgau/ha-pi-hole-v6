"""Check the CPU temperature: its reading by the client, and the sensor built on it.

The client part is a pure function of the padd cache. The sensor part loads an entry whose data fetches
are replaced by fake ones filling the caches from a fixture, so nothing reaches the network.
"""

from __future__ import annotations

from contextlib import contextmanager
import copy
import json
import math
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.pi_hole_v6.api import Api
from custom_components.pi_hole_v6.const import CONF_UPDATE_INTERVAL_STATS, DOMAIN
from custom_components.pi_hole_v6.sensor import SENSOR_TYPES, UNRECORDED_ATTRIBUTES_KEYS
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_URL, STATE_UNKNOWN, EntityCategory, Platform
from homeassistant.helpers import entity_registry as er

if TYPE_CHECKING:
    from collections.abc import Iterator

    from custom_components.pi_hole_v6 import PiHoleV6ConfigEntry

    from homeassistant.core import HomeAssistant

INTEGRATION = "custom_components.pi_hole_v6"
FIXTURES = Path(__file__).parent / "fixtures"
UNIQUE_SUFFIX = "cpu_temperature"
ENTITY_ID = "sensor.pihole_cpu_temperature"
COMPONENTS_DIR = Path(__file__).parent.parent / "custom_components" / "pi_hole_v6"


def _padd() -> dict[str, Any]:
    """Return a fresh copy of the padd fixture."""
    return json.loads((FIXTURES / "padd_sensors.json").read_text(encoding="utf-8"))


def _api(padd: Any) -> Api:
    """Return a client whose padd cache holds the given value."""
    api = Api(MagicMock())
    api.cache_padd = padd
    return api


def _with_sensors(sensors: Any) -> dict[str, Any]:
    """Return the padd fixture with its sensors object replaced."""
    padd = _padd()
    padd["sensors"] = sensors
    return padd


# --------------------------------------------------------------------------------------------------
# Client
# --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sensors", "expected"),
    [
        ({"cpu_temp": 48.3, "unit": "C"}, 48.3),
        ({"cpu_temp": 48, "unit": "C"}, 48.0),
        ({"cpu_temp": 0, "unit": "C"}, 0.0),
        ({"cpu_temp": -5.5, "unit": "C"}, -5.5),
        ({"cpu_temp": 48.3}, 48.3),
        ({"cpu_temp": 118.94, "unit": "F"}, 48.3),
        ({"cpu_temp": 118.94, "unit": "f"}, 48.3),
        ({"cpu_temp": 32, "unit": "F"}, 0.0),
        ({"cpu_temp": 321.45, "unit": "K"}, 48.3),
        ({"cpu_temp": 321.45, "unit": "k"}, 48.3),
        ({"cpu_temp": 273.15, "unit": "K"}, 0.0),
    ],
)
def test_temperature_is_converted_to_celsius(sensors: dict[str, Any], expected: float) -> None:
    """A finite number is returned in degrees Celsius, whatever the unit Pi-hole reports."""
    result = _api(_with_sensors(sensors)).cpu_temperature_celsius()

    assert isinstance(result, float)
    assert result == pytest.approx(expected, abs=1e-6)


def test_celsius_is_passed_through_untouched() -> None:
    """A value already in degrees Celsius is neither rounded nor converted."""
    assert _api(_padd()).cpu_temperature_celsius() == 48.3


@pytest.mark.parametrize(
    "value",
    [None, "48", "48.3", "", True, False, [48.3], {"v": 1}, math.nan, math.inf, -math.inf],
    ids=repr,
)
def test_invalid_value_gives_none(value: Any) -> None:
    """A value that is not a finite number is reported as not available."""
    assert _api(_with_sensors({"cpu_temp": value, "unit": "C"})).cpu_temperature_celsius() is None


def test_missing_value_gives_none() -> None:
    """A sensors object without cpu_temp is reported as not available."""
    assert _api(_with_sensors({"unit": "C"})).cpu_temperature_celsius() is None


@pytest.mark.parametrize("unit", ["X", "", "celsius", "CF", None, 5])
def test_unknown_unit_gives_none(unit: Any) -> None:
    """An unit other than C, F or K is not guessed."""
    assert _api(_with_sensors({"cpu_temp": 48.3, "unit": unit})).cpu_temperature_celsius() is None


@pytest.mark.parametrize("sensors", [None, [], [48.3], "sensors", 48.3, True])
def test_unexpected_sensors_shape_gives_none(sensors: Any) -> None:
    """A sensors value that is not an object gives None, without raising."""
    assert _api(_with_sensors(sensors)).cpu_temperature_celsius() is None


def test_missing_sensors_gives_none() -> None:
    """A padd response without sensors gives None."""
    padd = _padd()
    del padd["sensors"]

    assert _api(padd).cpu_temperature_celsius() is None


@pytest.mark.parametrize("padd", [{}, [], [{"sensors": {"cpu_temp": 1}}], None, "padd", 42, 4.2, True])
def test_unexpected_padd_shape_gives_none(padd: Any) -> None:
    """A padd cache that is not an object gives None, without raising."""
    assert _api(padd).cpu_temperature_celsius() is None


def test_fresh_client_has_no_temperature() -> None:
    """A client that has fetched nothing yet reports no temperature."""
    assert Api(MagicMock()).cpu_temperature_celsius() is None


@pytest.mark.parametrize("unit", ["C", "F", "K", "X"])
def test_cache_is_not_modified(unit: str) -> None:
    """Reading the temperature leaves the cache exactly as it was."""
    padd = _with_sensors({"cpu_temp": 120.0, "unit": unit, "hot_limit": 60.0})
    before = copy.deepcopy(padd)

    _api(padd).cpu_temperature_celsius()

    assert padd == before


@pytest.mark.parametrize(
    ("padd", "expected"),
    [
        ({"sensors": {"cpu_temp": 48.3, "hot_limit": 60.0, "unit": "C"}}, {"hot_limit": 60.0, "unit": "C"}),
        ({"sensors": {"cpu_temp": 118.94, "unit": "F"}}, {"unit": "F"}),
        ({"sensors": {"cpu_temp": 48.3, "hot_limit": None, "unit": "C"}}, {"hot_limit": None, "unit": "C"}),
        ({"sensors": {"cpu_temp": 48.3, "list": [{"name": "probe"}], "other": 1}}, None),
        ({"sensors": {"cpu_temp": 48.3}}, None),
        ({"sensors": {}}, None),
        ({"sensors": None}, None),
        ({"sensors": []}, None),
        ({}, None),
        ([], None),
    ],
    ids=repr,
)
def test_report_keeps_only_the_hot_limit_and_the_unit(padd: Any, expected: dict[str, Any] | None) -> None:
    """The temperature is the state, the probe list and anything else stay out of the attributes."""
    assert _api(padd).cpu_temperature_report() == expected


def test_report_is_empty_before_any_fetch() -> None:
    """A new client has no padd data."""
    assert Api(MagicMock()).cpu_temperature_report() is None


# --------------------------------------------------------------------------------------------------
# Sensor
# --------------------------------------------------------------------------------------------------


@pytest.fixture(name="expected_lingering_timers")
def expected_lingering_timers_fixture() -> bool:
    """Accept the one second timer the sensor platform starts and never cancels when the entry unloads."""
    return True


def _fill(api: Api, padd: dict[str, Any]) -> None:
    """Put a padd response in the cache of the client, as the data fetch would."""
    api.cache_padd = padd


@contextmanager
def _fetches(holder: dict[str, dict[str, Any]]) -> Iterator[None]:
    """Replace every fetch so that nothing reaches the network, the live one filling the padd cache."""

    async def fake_live(api_client: Api, **_: Any) -> None:
        """Fill the padd cache like the live fetch does."""
        _fill(api_client, holder["padd"])

    only_cpu = tuple(description for description in SENSOR_TYPES if description.key == UNIQUE_SUFFIX)

    with (
        patch(f"{INTEGRATION}.PLATFORMS", [Platform.SENSOR]),
        patch(f"{INTEGRATION}.sensor.SENSOR_TYPES", only_cpu),
        patch(f"{INTEGRATION}.async_get_live_data", AsyncMock(side_effect=fake_live)),
        patch(f"{INTEGRATION}.async_get_stats_data", AsyncMock()),
        patch.object(Api, "call_get_ftl_info_messages", AsyncMock(return_value={})),
        patch.object(Api, "call_logout", AsyncMock()),
    ):
        yield


async def _setup(
    hass: HomeAssistant, padd: dict[str, Any], *, enabled: bool
) -> tuple[PiHoleV6ConfigEntry, dict[str, dict[str, Any]]]:
    """Load an entry with only the cpu_temperature sensor, enabled or left to its default.

    The fake fetches write the content of the returned holder into the padd cache, so a test changes
    what Pi-hole "reports" by replacing holder["padd"].
    """
    holder: dict[str, dict[str, Any]] = {"padd": padd}
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="https://pihole.example/api",
        data={
            CONF_NAME: "Pihole",
            CONF_URL: "https://pihole.example/api",
            CONF_PASSWORD: "pw",
            CONF_UPDATE_INTERVAL_STATS: 600,
        },
    )
    entry.add_to_hass(hass)

    if enabled:
        er.async_get(hass).async_get_or_create(
            Platform.SENSOR,
            DOMAIN,
            f"{entry.entry_id}/{UNIQUE_SUFFIX}",
            config_entry=entry,
            suggested_object_id="pihole_cpu_temperature",
            disabled_by=None,
        )

    with _fetches(holder):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    return entry, holder


async def _unload(hass: HomeAssistant, entry: PiHoleV6ConfigEntry) -> None:
    """Unload the entry to stop its timers."""
    with patch.object(Api, "call_logout", AsyncMock()):
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_sensor_is_disabled_by_default_and_diagnostic(hass: HomeAssistant) -> None:
    """The entity exists in the registry, disabled by the integration, in the diagnostic category."""
    entry, _ = await _setup(hass, _padd(), enabled=False)

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(Platform.SENSOR, DOMAIN, f"{entry.entry_id}/{UNIQUE_SUFFIX}")
    assert entity_id is not None
    registry_entry = registry.async_get(entity_id)
    assert registry_entry is not None
    assert registry_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert registry_entry.entity_category is EntityCategory.DIAGNOSTIC
    assert registry_entry.translation_key == UNIQUE_SUFFIX
    assert hass.states.get(entity_id) is None

    await _unload(hass, entry)


async def test_sensor_state_and_attributes(hass: HomeAssistant) -> None:
    """Once enabled, the sensor reports the temperature in degrees Celsius with its metadata."""
    entry, _ = await _setup(hass, _padd(), enabled=True)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "48.3"
    assert state.attributes["unit_of_measurement"] == "°C"
    assert state.attributes["device_class"] == SensorDeviceClass.TEMPERATURE
    assert state.attributes["state_class"] == SensorStateClass.MEASUREMENT
    assert state.attributes["friendly_name"].endswith("CPU temperature")
    assert "cpu_temp" not in state.attributes
    assert state.attributes["hot_limit"] == 60.0
    assert state.attributes["unit"] == "C"
    assert "list" not in state.attributes
    assert state.attributes["note"] == "CPU temperature of the machine hosting Pi-hole, in °C."

    registry_entry = er.async_get(hass).async_get(ENTITY_ID)
    assert registry_entry is not None
    assert registry_entry.entity_category is EntityCategory.DIAGNOSTIC

    await _unload(hass, entry)


@pytest.mark.parametrize(
    ("sensors", "expected"),
    [
        ({"cpu_temp": None, "unit": "C", "hot_limit": 60.0}, STATE_UNKNOWN),
        ({"unit": "C"}, STATE_UNKNOWN),
        ({"cpu_temp": 48.3, "unit": "X"}, STATE_UNKNOWN),
        (None, STATE_UNKNOWN),
        ({"cpu_temp": 118.94, "unit": "F"}, "48.3"),
        ({"cpu_temp": 321.45, "unit": "K"}, "48.3"),
    ],
)
async def test_sensor_state_follows_the_reported_value(hass: HomeAssistant, sensors: Any, expected: str) -> None:
    """No probe or an unusable value gives unknown, not unavailable; other units are converted."""
    entry, _ = await _setup(hass, _with_sensors(sensors), enabled=True)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == expected

    await _unload(hass, entry)


async def test_sensor_follows_the_stats_coordinator(hass: HomeAssistant) -> None:
    """The state changes when the stats coordinator refreshes, not when the cache changes."""
    entry, holder = await _setup(hass, _padd(), enabled=True)
    api = entry.runtime_data.api

    # The first scheduled refresh after setup is skipped by design: let the next ones do their job.
    api.just_initialized = {}

    hotter = copy.deepcopy(holder["padd"])
    hotter["sensors"]["cpu_temp"] = 55.5
    holder["padd"] = hotter

    # A live refresh updates the cache but does not write the state of a stats sensor.
    with _fetches(holder):
        await entry.runtime_data.coordinator.async_refresh()
        await hass.async_block_till_done()
    live_state = hass.states.get(ENTITY_ID)
    assert live_state is not None
    assert live_state.state == "48.3"

    # The cache is read again at the next refresh of the stats coordinator.
    with _fetches(holder):
        await entry.runtime_data.coordinator_stats.async_refresh()
        await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "55.5"

    await _unload(hass, entry)


def test_description_is_attached_to_the_stats_coordinator() -> None:
    """The description declares the stats coordinator and a fixed Celsius unit."""
    description = next(item for item in SENSOR_TYPES if item.key == UNIQUE_SUFFIX)

    assert description.coordinator_key == "stats"
    assert description.native_unit_of_measurement == "°C"
    assert description.entity_registry_enabled_default is False
    assert description.entity_category is EntityCategory.DIAGNOSTIC


# --------------------------------------------------------------------------------------------------
# Translations
# --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("strings.json", "CPU temperature"),
        ("translations/en.json", "CPU temperature"),
        ("translations/fr.json", "Température CPU"),
    ],
)
def test_translation_exists(path: str, expected: str) -> None:
    """The cpu_temperature name is translated where the integration ships it."""
    content = json.loads((COMPONENTS_DIR / path).read_text(encoding="utf-8"))

    assert content["entity"]["sensor"]["cpu_temperature"]["name"] == expected


def test_attributes_are_kept_out_of_the_recorder() -> None:
    """The attributes repeat the state: like the other system metrics they never reach the recorder."""
    assert UNIQUE_SUFFIX in UNRECORDED_ATTRIBUTES_KEYS
