"""Check the privacy level: its reading by the client, the stats fetch and the sensor built on it.

The client part patches the underlying call, so nothing reaches the network. The sensor part loads an
entry whose data fetches are replaced by fake ones filling the cache of the client.
"""

from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.pi_hole_v6 import async_get_stats_data
from custom_components.pi_hole_v6.api import Api
from custom_components.pi_hole_v6.const import CONF_UPDATE_INTERVAL_STATS, DOMAIN, PRIVACY_LEVELS
from custom_components.pi_hole_v6.exceptions import ForbiddenError, NotFoundError, ServerError, UnauthorizedError
from custom_components.pi_hole_v6.sensor import SENSOR_TYPES
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_URL, STATE_UNKNOWN, EntityCategory, Platform
from homeassistant.helpers import entity_registry as er

if TYPE_CHECKING:
    from collections.abc import Iterator

    from custom_components.pi_hole_v6 import PiHoleV6ConfigEntry

    from homeassistant.core import HomeAssistant

INTEGRATION = "custom_components.pi_hole_v6"
UNIQUE_SUFFIX = "privacy_level"
ENTITY_ID = "sensor.pihole_privacy_level"
COMPONENTS_DIR = Path(__file__).parent.parent / "custom_components" / "pi_hole_v6"


def _body(level: Any) -> dict[str, Any]:
    """Return the body of GET /config/misc/privacylevel for a level."""
    return {"config": {"misc": {"privacylevel": level}}, "took": 0.001}


def _answer(level: Any) -> dict[str, Any]:
    """Return what the underlying call gives for a level."""
    return {"code": 200, "reason": "OK", "data": _body(level)}


# --------------------------------------------------------------------------------------------------
# Client
# --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("level", "expected"), list(enumerate(PRIVACY_LEVELS)))
async def test_each_level_gives_its_state(level: int, expected: str) -> None:
    """The levels 0 to 3 are read from the body and named."""
    api = Api(MagicMock())

    with patch.object(Api, "_call", AsyncMock(return_value=_answer(level))) as call:
        result = await api.call_get_privacy_level()

    assert api.cache_privacy_level == level
    assert api.privacy_level == expected
    assert result["code"] == 200
    assert call.await_args.args[0] == "/config/misc/privacylevel"
    assert call.await_args.kwargs["method"] == "GET"


def test_the_levels_are_the_four_of_pihole() -> None:
    """The state list follows the numbering of Pi-hole."""
    assert PRIVACY_LEVELS == ["show_everything", "hide_domains", "hide_domains_and_clients", "anonymous"]


def test_the_level_is_unknown_before_any_fetch() -> None:
    """A new client has no level."""
    api = Api(MagicMock())

    assert api.cache_privacy_level is None
    assert api.privacy_level is None


@pytest.mark.parametrize(
    "data",
    [
        None,
        [],
        "3",
        {},
        {"config": None},
        {"config": {"misc": None}},
        {"config": {"misc": {}}},
        {"config": {"misc": {"privacylevel": "2"}}},
        {"config": {"misc": {"privacylevel": 2.0}}},
        {"config": {"misc": {"privacylevel": True}}},
        {"config": {"misc": {"privacylevel": -1}}},
        {"config": {"misc": {"privacylevel": 4}}},
        {"config": {"misc": {"privacylevel": None}}},
    ],
    ids=repr,
)
async def test_a_body_without_a_level_from_0_to_3_gives_an_unknown_level(data: Any) -> None:
    """Whatever Pi-hole sends back, the level is unknown rather than an error or a wrong state."""
    api = Api(MagicMock())
    api.cache_privacy_level = 2

    with patch.object(Api, "_call", AsyncMock(return_value={"code": 200, "reason": "OK", "data": data})):
        await api.call_get_privacy_level()

    assert api.cache_privacy_level is None
    assert api.privacy_level is None


@pytest.mark.parametrize("error", [ForbiddenError(), NotFoundError()], ids=["forbidden", "not_found"])
async def test_a_refusal_is_not_an_error(error: Exception) -> None:
    """An account that cannot read the configuration, or an older Pi-hole, gives an unknown level."""
    api = Api(MagicMock())
    api.cache_privacy_level = 1

    with patch.object(Api, "_call", AsyncMock(side_effect=error)) as call:
        result = await api.call_get_privacy_level()

    assert api.cache_privacy_level is None
    assert result["data"] == {}
    assert call.await_args.kwargs["expected_errors"] == (ForbiddenError, NotFoundError)


@pytest.mark.parametrize("error", [UnauthorizedError(), ServerError()], ids=["unauthorized", "server"])
async def test_the_other_errors_propagate_like_the_other_calls(error: Exception) -> None:
    """Only the two refusals are absorbed: the other failures keep their usual handling."""
    api = Api(MagicMock())

    with (
        patch.object(Api, "_call", AsyncMock(side_effect=error)),
        pytest.raises(type(error)),
    ):
        await api.call_get_privacy_level()


async def test_the_stats_fetch_reads_the_privacy_level() -> None:
    """The level is requested with the stats coordinator, together with the message count."""
    client = MagicMock()
    client.call_get_ftl_info_messages_count = AsyncMock(return_value={})
    client.call_get_privacy_level = AsyncMock(return_value={})

    await async_get_stats_data(client)

    client.call_get_ftl_info_messages_count.assert_awaited_once()
    client.call_get_privacy_level.assert_awaited_once()


# --------------------------------------------------------------------------------------------------
# Sensor
# --------------------------------------------------------------------------------------------------


@pytest.fixture(name="expected_lingering_timers")
def expected_lingering_timers_fixture() -> bool:
    """Accept the one second timer the sensor platform starts and never cancels when the entry unloads."""
    return True


@contextmanager
def _fetches(holder: dict[str, int | None]) -> Iterator[None]:
    """Replace every fetch so that nothing reaches the network, the stats one filling the level cache."""

    async def fake_stats(api_client: Api) -> None:
        """Fill the level cache like the stats fetch does."""
        api_client.cache_privacy_level = holder["level"]

    only_level = tuple(description for description in SENSOR_TYPES if description.key == UNIQUE_SUFFIX)

    with (
        patch(f"{INTEGRATION}.PLATFORMS", [Platform.SENSOR]),
        patch(f"{INTEGRATION}.sensor.SENSOR_TYPES", only_level),
        patch(f"{INTEGRATION}.async_get_live_data", AsyncMock()),
        patch(f"{INTEGRATION}.async_get_stats_data", AsyncMock(side_effect=fake_stats)),
        patch.object(Api, "call_get_ftl_info_messages", AsyncMock(return_value={})),
        patch.object(Api, "call_logout", AsyncMock()),
    ):
        yield


async def _setup(
    hass: HomeAssistant, level: int | None, *, enabled: bool
) -> tuple[PiHoleV6ConfigEntry, dict[str, int | None]]:
    """Load an entry with only the privacy level sensor, enabled or left to its default.

    The fake stats fetch writes holder["level"] into the cache, so a test changes what Pi-hole "reports".
    """
    holder: dict[str, int | None] = {"level": level}
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
            suggested_object_id="pihole_privacy_level",
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
    entry, _ = await _setup(hass, 0, enabled=False)

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


@pytest.mark.parametrize(("level", "expected"), [*enumerate(PRIVACY_LEVELS), (None, STATE_UNKNOWN)])
async def test_sensor_state_follows_the_level(hass: HomeAssistant, level: int | None, expected: str) -> None:
    """Once enabled, the sensor names the level, and is unknown, not unavailable, when it cannot be read."""
    entry, _ = await _setup(hass, level, enabled=True)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == expected
    assert state.attributes["device_class"] == SensorDeviceClass.ENUM
    assert state.attributes["options"] == PRIVACY_LEVELS

    await _unload(hass, entry)


async def test_sensor_follows_the_stats_coordinator(hass: HomeAssistant) -> None:
    """The state changes when the stats coordinator refreshes, not when the live one does."""
    entry, holder = await _setup(hass, 0, enabled=True)
    entry.runtime_data.api.just_initialized = {}

    holder["level"] = 3
    with _fetches(holder):
        await entry.runtime_data.coordinator.async_refresh()
        await hass.async_block_till_done()
    live_state = hass.states.get(ENTITY_ID)
    assert live_state is not None
    assert live_state.state == "show_everything"

    with _fetches(holder):
        await entry.runtime_data.coordinator_stats.async_refresh()
        await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "anonymous"

    await _unload(hass, entry)


def test_description_is_attached_to_the_stats_coordinator() -> None:
    """The description declares the stats coordinator, the enum options and a disabled default."""
    description = next(item for item in SENSOR_TYPES if item.key == UNIQUE_SUFFIX)

    assert description.coordinator_key == "stats"
    assert description.options == PRIVACY_LEVELS
    assert description.entity_registry_enabled_default is False
    assert description.entity_category is EntityCategory.DIAGNOSTIC


# --------------------------------------------------------------------------------------------------
# Translations
# --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "name", "anonymous"),
    [
        ("strings.json", "Privacy level", "Anonymous mode"),
        ("translations/en.json", "Privacy level", "Anonymous mode"),
        ("translations/fr.json", "Niveau de confidentialité", "Mode anonyme"),
    ],
)
def test_translation_exists(path: str, name: str, anonymous: str) -> None:
    """The name and every state are translated where the integration ships them."""
    content = json.loads((COMPONENTS_DIR / path).read_text(encoding="utf-8"))
    entity = content["entity"]["sensor"][UNIQUE_SUFFIX]

    assert entity["name"] == name
    assert set(entity["state"]) == set(PRIVACY_LEVELS)
    assert entity["state"]["anonymous"] == anonymous
