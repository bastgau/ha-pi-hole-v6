"""Check the diagnostics report: its content, its shape on odd caches, and that it never leaks a marker.

The data fetch functions and the logout call are replaced; the caches of the client are then filled with
fake data holding recognizable markers, which must never appear in the report.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

from custom_components.pi_hole_v6.api import Api
from custom_components.pi_hole_v6.const import (
    ACCESS_APP_NO_SUDO,
    ACCESS_APP_SUDO,
    ACCESS_RESTRICTED,
    CONF_CERT_FINGERPRINT,
    CONF_DEVICE_TRACKER_CONSIDER_HOME,
    CONF_DEVICE_TRACKER_MAC_LIST,
    CONF_DEVICE_TRACKER_STALE_DAYS,
    CONF_DEVICE_TRACKER_WHITELIST,
    CONF_UPDATE_INTERVAL_LIVE,
    CONF_UPDATE_INTERVAL_STATS,
    CONF_VERIFY_SSL,
    DOMAIN,
    MAX_NETWORK_DEVICES,
)
from custom_components.pi_hole_v6.diagnostics import async_get_config_entry_diagnostics
from custom_components.pi_hole_v6.exceptions import APIError
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_URL
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from custom_components.pi_hole_v6 import PiHoleV6ConfigEntry
    from freezegun.api import FrozenDateTimeFactory
    from pytest_homeassistant.typing import ClientSessionGenerator

    from homeassistant.core import HomeAssistant

INTEGRATION = "custom_components.pi_hole_v6"
URL = "https://pihole.example:8443/api"
PASSWORD = "s3cret-passw0rd"
FINGERPRINT = "ab12cd34ef56ab12cd34ef56ab12cd34ef56ab12cd34ef56ab12cd34ef56ab12"
MAC = "aa:bb:cc:dd:ee:ff"
IP = "192.168.1.42"
HOST = "secret-host"
GROUP = "my-group"
DOMAIN_NAME = "ads.tracker.example"
MESSAGE_TEXT = "FTL says something about secret-host"
NODE_NAME = "node-marker-name"
IFACE = "eth-marker0"
PID = "pid-marker-31337"
HASH = "hash-marker-deadbeef"
EXTRA = "unexpected-marker-value"
TOP_DOMAIN = "top.domain.marker.example"

MARKERS = [
    URL,
    "pihole.example",
    "8443",
    PASSWORD,
    FINGERPRINT,
    MAC,
    IP,
    HOST,
    GROUP,
    DOMAIN_NAME,
    MESSAGE_TEXT,
    "Pi-hole marker name",
    "11:22:33:44:55:66",
    "77:88:99:aa:bb:cc",
    NODE_NAME,
    IFACE,
    PID,
    HASH,
    EXTRA,
    TOP_DOMAIN,
]


def _entry(**overrides: Any) -> MockConfigEntry:
    """Build a config entry whose data holds every marker."""
    data: dict[str, Any] = {
        CONF_NAME: "Pi-hole marker name",
        CONF_URL: URL,
        CONF_PASSWORD: PASSWORD,
        CONF_VERIFY_SSL: True,
        CONF_CERT_FINGERPRINT: FINGERPRINT,
        CONF_DEVICE_TRACKER_MAC_LIST: f"{MAC}, 11:22:33:44:55:66\n77:88:99:aa:bb:cc",
        CONF_UPDATE_INTERVAL_LIVE: 30,
        CONF_UPDATE_INTERVAL_STATS: 600,
    }
    for key, value in overrides.items():
        if value is None:
            data.pop(key, None)
        else:
            data[key] = value
    return MockConfigEntry(domain=DOMAIN, unique_id=URL, data=data)


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> PiHoleV6ConfigEntry:
    """Set the entry up with the data fetches replaced, so nothing reaches the network."""
    entry.add_to_hass(hass)

    with (
        patch(f"{INTEGRATION}.async_get_live_data", AsyncMock()),
        patch(f"{INTEGRATION}.async_get_stats_data", AsyncMock()),
        patch.object(Api, "call_get_ftl_info_messages", AsyncMock(return_value={})),
        patch.object(Api, "call_logout", AsyncMock()),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    return entry


def _fill_caches(api: Api) -> None:
    """Fill the caches of the client with realistic data holding the markers."""
    api.account_access = ACCESS_APP_SUDO
    api.cache_padd = {
        "host_model": "Raspberry Pi 4",
        "node_name": NODE_NAME,
        "iface": {"v4": {"name": IFACE, "addr": IP}},
        "pid": PID,
        "sensors": {"cpu_temp": 48.3, "unit": "C", "hot_limit": 60.0, "list": [{"name": EXTRA}]},
        "version": {
            "core": {"local": {"version": "v6.0", "hash": HASH}, "remote": {"version": "v6.1", "hash": HASH}},
            "web": {"local": {"version": "v6.0"}, "remote": {"version": "v6.0"}},
            "ftl": {"local": {"version": "v6.0"}, "remote": {"version": "v6.2"}},
            "docker": {"local": "2025.01.0", "remote": "2025.01.0"},
        },
    }
    api.cache_summary = {
        "queries": {
            "total": 1000,
            "blocked": 250,
            "percent_blocked": 25.0,
            "cached": 300,
            "forwarded": 450,
            "unique_domains": 80,
        },
        "clients": {"active": 5, "total": 9},
        "gravity": {"domains_being_blocked": 123456},
        "top_domain": TOP_DOMAIN,
        "recent_blocked": [TOP_DOMAIN, DOMAIN_NAME],
    }
    api.cache_blocking = {"blocking": "enabled", "timer": None}
    api.cache_groups = {GROUP: {"id": 1, "comment": DOMAIN_NAME}}
    api.cache_configured_clients = [{"client": IP, "groups": [0]}, {"client": MAC}]
    api.cache_dhcp_leases = [{"ip": IP, "name": HOST, "hwaddr": MAC}]
    api.cache_auth_sessions = [{"id": 1, "remote_addr": IP}, {"id": 2, "remote_addr": IP}]
    api.cache_network_devices = [
        {"hwaddr": MAC, "lastQuery": 1700000000, "ips": [{"ip": IP, "name": HOST}]},
        {"hwaddr": "11:22:33:44:55:66", "lastQuery": 0, "ips": []},
        {"hwaddr": "77:88:99:aa:bb:cc"},
    ]
    api.cache_ftl_info = {
        "message_count": 2,
        "status": "OK: Messages fetched successfully",
        "unexpected_key": EXTRA,
        "message_list": [
            {"type": "DNSMASQ_WARN", "plain": MESSAGE_TEXT, "html": DOMAIN_NAME},
            {"type": "CERTIFICATE", "plain": MESSAGE_TEXT},
            {"plain": "no type"},
        ],
    }


@pytest.fixture(name="loaded")
async def loaded_fixture(hass: HomeAssistant) -> AsyncGenerator[PiHoleV6ConfigEntry]:
    """Return a loaded entry whose caches hold the markers, unloaded afterwards to stop its timers."""
    # No platform: the entities are not under test and would read the half filled caches.
    with patch(f"{INTEGRATION}.PLATFORMS", []), patch.object(Api, "call_logout", AsyncMock()):
        entry = await _setup(hass, _entry())
        _fill_caches(entry.runtime_data.api)
        yield entry
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_full_report(hass: HomeAssistant, loaded: PiHoleV6ConfigEntry) -> None:
    """A loaded entry gives the expected keys, types and values."""
    result = await async_get_config_entry_diagnostics(hass, loaded)

    assert set(result) == {"entry", "settings", "loaded", "coordinators", "pihole", "device_tracker", "presence"}
    assert result["loaded"] is True
    assert result["entry"] == {
        "version": loaded.version,
        "minor_version": loaded.minor_version,
        "source": "user",
        "state": "loaded",
        "unique_id_matches_url": True,
    }
    assert result["settings"]["update_interval_live"] == 30
    assert result["settings"]["update_interval_stats"] == 600
    assert set(result["coordinators"]) == {"live", "stats"}
    assert result["coordinators"]["live"]["update_interval"] == 30.0
    assert result["coordinators"]["stats"]["update_interval"] == 600.0
    assert result["coordinators"]["live"]["last_update_success"] is True
    assert result["coordinators"]["live"]["last_exception"] is None
    assert isinstance(result["coordinators"]["live"]["last_refresh"], str)

    pihole = result["pihole"]
    assert pihole["account_access"] == ACCESS_APP_SUDO
    assert pihole["blocking"] == "enabled"
    assert pihole["host_model"] == "Raspberry Pi 4"
    assert pihole["counters"] == {
        "queries_total": 1000,
        "queries_blocked": 250,
        "percent_blocked": 25.0,
        "queries_cached": 300,
        "queries_forwarded": 450,
        "unique_domains": 80,
        "clients_active": 5,
        "clients_total": 9,
        "domains_being_blocked": 123456,
    }
    assert pihole["sizes"] == {
        "groups": 1,
        "configured_clients": 2,
        "dhcp_leases": 1,
        "auth_sessions": 2,
        "network_devices": 3,
    }
    assert pihole["ftl_messages"] == {
        "count": 2,
        "status": "OK: Messages fetched successfully",
        "types": ["CERTIFICATE", "DNSMASQ_WARN"],
    }


async def test_no_marker_in_report(hass: HomeAssistant, loaded: PiHoleV6ConfigEntry) -> None:
    """Nothing personal or network related, nor any secret, reaches the serialized report."""
    dumped = json.dumps(await async_get_config_entry_diagnostics(hass, loaded))

    for marker in MARKERS:
        assert marker not in dumped


async def test_no_marker_through_the_http_view(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, loaded: PiHoleV6ConfigEntry
) -> None:
    """The report served by the official diagnostics view holds the same data and no marker."""
    data = await get_diagnostics_for_config_entry(hass, hass_client, loaded)
    dumped = json.dumps(data)

    assert data["loaded"] is True
    assert data["pihole"]["counters"]["queries_total"] == 1000  # type: ignore[index]
    for marker in MARKERS:
        assert marker not in dumped


async def test_last_exception_is_the_class_name_only(hass: HomeAssistant, loaded: PiHoleV6ConfigEntry) -> None:
    """An UpdateFailed whose message holds the host is reported by its class name."""
    # The first scheduled refresh is skipped on purpose after the setup.
    loaded.runtime_data.api.just_initialized = {}
    with (
        patch(f"{INTEGRATION}.async_get_live_data", AsyncMock(side_effect=APIError(f"cannot reach {HOST} at {IP}"))),
        patch.object(Api, "call_logout", AsyncMock()),
    ):
        await loaded.runtime_data.coordinator.async_refresh()

    result = await async_get_config_entry_diagnostics(hass, loaded)

    assert isinstance(loaded.runtime_data.coordinator.last_exception, UpdateFailed)
    assert HOST in str(loaded.runtime_data.coordinator.last_exception)
    assert result["coordinators"]["live"]["last_update_success"] is False
    assert result["coordinators"]["live"]["last_exception"] == "UpdateFailed"
    assert result["coordinators"]["stats"]["last_exception"] is None
    assert HOST not in json.dumps(result)


async def test_not_loaded_entry(hass: HomeAssistant) -> None:
    """An entry that fails its first refresh (SETUP_RETRY) is reported without runtime sections."""
    entry = _entry()
    entry.add_to_hass(hass)

    with (
        patch(f"{INTEGRATION}.PLATFORMS", []),
        patch(f"{INTEGRATION}.async_get_live_data", AsyncMock(side_effect=APIError(f"down {HOST}"))),
        patch(f"{INTEGRATION}.async_get_stats_data", AsyncMock()),
        patch.object(Api, "call_logout", AsyncMock()),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["loaded"] is False
    assert result["entry"]["state"] == "setup_retry"
    assert set(result) == {"entry", "settings", "loaded"}
    assert not {"coordinators", "pihole", "device_tracker", "presence"} & set(result)
    dumped = json.dumps(result)
    for marker in (HOST, URL, "pihole.example", PASSWORD, FINGERPRINT):
        assert marker not in dumped


async def test_entry_never_set_up(hass: HomeAssistant) -> None:
    """An entry that was never set up has no runtime data and is reported as not loaded."""
    entry = _entry()
    entry.add_to_hass(hass)

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["loaded"] is False
    assert result["entry"]["state"] == "not_loaded"


@pytest.mark.parametrize(
    "cache_name",
    ["cache_padd", "cache_summary", "cache_ftl_info", "cache_blocking", "cache_groups", "cache_network_devices"],
)
@pytest.mark.parametrize("value", [{}, [], None, "text", 42])
async def test_unexpected_cache_shapes(
    hass: HomeAssistant, loaded: PiHoleV6ConfigEntry, cache_name: str, value: Any
) -> None:
    """Empty or wrongly shaped caches give null, zero or empty values, never an exception."""
    setattr(loaded.runtime_data.api, cache_name, value)

    result = await async_get_config_entry_diagnostics(hass, loaded)

    pihole = result["pihole"]
    json.dumps(result)
    assert result["loaded"] is True
    neutral_by_cache: dict[str, bool] = {
        "cache_padd": pihole["host_model"] is None
        and all(info == {"local": None, "remote": None} for info in pihole["versions"].values())
        and all(flag is None for flag in pihole["updates_available"].values()),
        "cache_summary": all(counter is None for counter in pihole["counters"].values()),
        "cache_ftl_info": pihole["ftl_messages"] == {"count": None, "status": None, "types": []},
        "cache_blocking": pihole["blocking"] is None,
        "cache_groups": pihole["sizes"]["groups"] == 0,
        "cache_network_devices": pihole["sizes"]["network_devices"] == 0
        and result["device_tracker"]["network_devices_reported"] == 0
        and result["device_tracker"]["without_last_query"] == 0
        and result["device_tracker"]["cap_reached"] is False,
    }
    assert neutral_by_cache[cache_name]


async def test_empty_caches(hass: HomeAssistant, loaded: PiHoleV6ConfigEntry) -> None:
    """Every cache empty (padd = {}) gives null counters and versions, zero sizes."""
    api = loaded.runtime_data.api
    api.account_access = None
    api.cache_padd = {}
    api.cache_summary = {}
    api.cache_ftl_info = {}
    api.cache_blocking = {}
    api.cache_groups = {}
    api.cache_configured_clients = []
    api.cache_dhcp_leases = []
    api.cache_auth_sessions = []
    api.cache_network_devices = []

    pihole = (await async_get_config_entry_diagnostics(hass, loaded))["pihole"]

    assert pihole["account_access"] is None
    assert pihole["blocking"] is None
    assert pihole["host_model"] is None
    assert all(value is None for value in pihole["counters"].values())
    assert all(value is None for info in pihole["versions"].values() for value in info.values())
    assert all(value is None for value in pihole["updates_available"].values())
    assert pihole["sizes"] == {
        "groups": 0,
        "configured_clients": 0,
        "dhcp_leases": 0,
        "auth_sessions": 0,
        "network_devices": 0,
    }
    assert pihole["ftl_messages"] == {"count": None, "status": None, "types": []}


async def test_unexpected_shapes_give_neutral_values(hass: HomeAssistant, loaded: PiHoleV6ConfigEntry) -> None:
    """Non dict summary / FTL info and a non list of devices give null, 0 and []."""
    api = loaded.runtime_data.api
    api.cache_summary = "oops"  # type: ignore[assignment]
    api.cache_ftl_info = ["oops"]  # type: ignore[assignment]
    api.cache_network_devices = "not a list"  # type: ignore[assignment]

    result = await async_get_config_entry_diagnostics(hass, loaded)

    assert all(value is None for value in result["pihole"]["counters"].values())
    assert result["pihole"]["ftl_messages"] == {"count": None, "status": None, "types": []}
    assert result["pihole"]["sizes"]["network_devices"] == 0
    assert result["device_tracker"]["network_devices_reported"] == 0
    assert result["device_tracker"]["without_last_query"] == 0
    assert result["device_tracker"]["cap_reached"] is False


async def test_network_devices_dict_is_not_counted(hass: HomeAssistant, loaded: PiHoleV6ConfigEntry) -> None:
    """A network devices cache that is not a list gives 0 everywhere."""
    loaded.runtime_data.api.cache_network_devices = {"not": "a list"}  # type: ignore[assignment]

    result = await async_get_config_entry_diagnostics(hass, loaded)

    assert result["pihole"]["sizes"]["network_devices"] == 0
    assert result["device_tracker"]["network_devices_reported"] == 0


@pytest.mark.parametrize(("length", "expected"), [(10, 10), (64, 64), (65, 64), (500, 64)])
async def test_host_model_is_truncated(
    hass: HomeAssistant, loaded: PiHoleV6ConfigEntry, length: int, expected: int
) -> None:
    """A host model longer than 64 characters is cut to 64."""
    loaded.runtime_data.api.cache_padd = {"host_model": "m" * length}

    result = await async_get_config_entry_diagnostics(hass, loaded)

    assert result["pihole"]["host_model"] == "m" * expected


async def test_malformed_values_inside_caches(hass: HomeAssistant, loaded: PiHoleV6ConfigEntry) -> None:
    """Wrong types inside well shaped caches (bool counters, non list messages) are dropped."""
    api = loaded.runtime_data.api
    api.cache_summary = {"queries": {"total": True, "blocked": "12"}, "clients": "x"}
    api.cache_ftl_info = {"message_list": "not a list", "message_count": "2", "status": 3}
    api.cache_padd = {"host_model": 5, "version": {"core": "bad", "web": {"local": 1, "remote": {"version": 2}}}}
    api.cache_blocking = {"blocking": 1}

    pihole = (await async_get_config_entry_diagnostics(hass, loaded))["pihole"]

    assert pihole["counters"]["queries_total"] is None
    assert pihole["counters"]["queries_blocked"] is None
    assert pihole["ftl_messages"] == {"count": None, "status": None, "types": []}
    assert pihole["host_model"] is None
    assert pihole["blocking"] is None
    assert pihole["versions"]["web"] == {"local": None, "remote": None}


@pytest.mark.parametrize(
    ("overrides", "unique_id", "expected"),
    [
        ({}, URL, True),
        ({}, URL.upper(), False),
        ({}, "https://other.example/api", False),
        ({}, None, False),
        ({CONF_URL: None}, URL, False),
        ({CONF_URL: "HTTPS://PiHole.Example:8443/api"}, "https://pihole.example:8443/api", True),
    ],
)
async def test_unique_id_matches_url(
    hass: HomeAssistant,
    overrides: dict[str, Any],
    unique_id: str | None,
    expected: bool,
) -> None:
    """The flag is false when the unique id differs from the lowercased URL or the URL is missing."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=unique_id, data=_entry(**overrides).data)
    entry.add_to_hass(hass)

    result = await async_get_config_entry_diagnostics(hass, entry)  # type: ignore[arg-type]

    assert result["entry"]["unique_id_matches_url"] is expected


async def test_versions(hass: HomeAssistant, loaded: PiHoleV6ConfigEntry) -> None:
    """Docker gives a string, the others a dictionary; a missing version gives a null update flag."""
    api = loaded.runtime_data.api
    api.cache_padd = {
        "version": {
            "core": {"local": {"version": "v6.0"}, "remote": {"version": "v6.1"}},
            "web": {"local": {"version": "v6.0"}, "remote": {"version": "v6.0"}},
            "ftl": {"local": {"version": "v6.0"}, "remote": None},
            "docker": {"local": "2025.01.0", "remote": "2025.02.0"},
        }
    }

    pihole = (await async_get_config_entry_diagnostics(hass, loaded))["pihole"]

    assert pihole["versions"]["core"] == {"local": "v6.0", "remote": "v6.1"}
    assert pihole["versions"]["docker"] == {"local": "2025.01.0", "remote": "2025.02.0"}
    assert pihole["versions"]["ftl"] == {"local": "v6.0", "remote": None}
    assert pihole["updates_available"] == {"core": True, "web": False, "ftl": None, "docker": True}


@pytest.mark.parametrize(
    ("access", "expected"),
    [(ACCESS_APP_NO_SUDO, None), (ACCESS_RESTRICTED, None), (ACCESS_APP_SUDO, 2), ("main_password", 2), (None, 2)],
)
async def test_auth_sessions(
    hass: HomeAssistant, loaded: PiHoleV6ConfigEntry, access: str | None, expected: int | None
) -> None:
    """The sessions are counted only for an account that can list them."""
    loaded.runtime_data.api.account_access = access

    result = await async_get_config_entry_diagnostics(hass, loaded)

    assert result["pihole"]["sizes"]["auth_sessions"] == expected


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        (
            {CONF_URL: "http://pihole.local/api/"},
            {"url_scheme": "http", "url_path_ends_with_api": True},
        ),
        (
            {CONF_URL: "http://pihole.local/admin"},
            {"url_scheme": "http", "url_path_ends_with_api": False},
        ),
        (
            {CONF_URL: "HTTPS://pihole.local"},
            {"url_scheme": "https", "url_path_ends_with_api": False},
        ),
        (
            {CONF_URL: None},
            {"url_scheme": "http", "url_path_ends_with_api": False},
        ),
        (
            {
                CONF_CERT_FINGERPRINT: None,
                CONF_PASSWORD: None,
                CONF_DEVICE_TRACKER_MAC_LIST: None,
                CONF_VERIFY_SSL: False,
            },
            {
                "certificate_pinned": False,
                "password_set": False,
                "device_tracker_address_count": 0,
                "verify_ssl": False,
            },
        ),
        (
            {},
            {"certificate_pinned": True, "password_set": True, "device_tracker_address_count": 3, "verify_ssl": True},
        ),
        (
            {CONF_DEVICE_TRACKER_MAC_LIST: 5, CONF_UPDATE_INTERVAL_LIVE: None},
            {"device_tracker_address_count": 0, "update_interval_live": None},
        ),
    ],
)
async def test_settings(hass: HomeAssistant, overrides: dict[str, Any], expected: dict[str, Any]) -> None:
    """The settings are reported as flags, schemes and counts, without their values."""
    entry = _entry(**overrides)
    entry.add_to_hass(hass)

    settings = (await async_get_config_entry_diagnostics(hass, entry))["settings"]  # type: ignore[arg-type]

    for key, value in expected.items():
        assert settings[key] == value
    assert not {URL, PASSWORD, FINGERPRINT} & {value for value in settings.values() if isinstance(value, str)}


async def test_device_tracker(hass: HomeAssistant, loaded: PiHoleV6ConfigEntry) -> None:
    """Devices without lastQuery are counted, and the tracked entities come from the entity registry."""
    registry = er.async_get(hass)
    baseline = (await async_get_config_entry_diagnostics(hass, loaded))["device_tracker"]["tracked_entities"]
    for index in range(2):
        registry.async_get_or_create("device_tracker", DOMAIN, f"tracker-{index}", config_entry=loaded)
    registry.async_get_or_create("sensor", DOMAIN, "a-sensor", config_entry=loaded)

    tracker = (await async_get_config_entry_diagnostics(hass, loaded))["device_tracker"]

    assert tracker["tracked_entities"] == baseline + 2
    assert tracker["network_devices_reported"] == 3
    assert tracker["max_network_devices"] == MAX_NETWORK_DEVICES
    assert tracker["cap_reached"] is False
    assert tracker["without_last_query"] == 2


@pytest.mark.parametrize(
    ("count", "reached"),
    [(MAX_NETWORK_DEVICES - 1, False), (MAX_NETWORK_DEVICES, True), (MAX_NETWORK_DEVICES + 1, True)],
)
async def test_device_tracker_cap(hass: HomeAssistant, loaded: PiHoleV6ConfigEntry, count: int, reached: bool) -> None:
    """The cap is reached from 2048 rows on."""
    loaded.runtime_data.api.cache_network_devices = [
        {"hwaddr": f"00:00:00:00:{i >> 8:02x}:{i & 255:02x}", "lastQuery": 1} for i in range(count)
    ]

    tracker = (await async_get_config_entry_diagnostics(hass, loaded))["device_tracker"]

    assert MAX_NETWORK_DEVICES == 2048
    assert tracker["cap_reached"] is reached
    assert tracker["network_devices_reported"] == count
    assert tracker["without_last_query"] == 0


async def test_last_refresh_and_interval(hass: HomeAssistant, loaded: PiHoleV6ConfigEntry) -> None:
    """A coordinator without interval reports null, and a missing refresh time gives null."""
    loaded.runtime_data.coordinator_stats.update_interval = None
    loaded.runtime_data.api.last_refresh.pop("stats", None)
    loaded.runtime_data.coordinator.update_interval = timedelta(seconds=90)

    coordinators = (await async_get_config_entry_diagnostics(hass, loaded))["coordinators"]

    assert coordinators["stats"]["update_interval"] is None
    assert coordinators["stats"]["last_refresh"] is None
    assert coordinators["live"]["update_interval"] == 90.0


@pytest.mark.parametrize(
    ("sensors", "available", "unit"),
    [
        ({"cpu_temp": 48.3, "unit": "C"}, True, "C"),
        ({"cpu_temp": 118.94, "unit": "F"}, True, "F"),
        ({"cpu_temp": None, "unit": "C"}, False, "C"),
        ({"unit": "K"}, False, "K"),
        ({"cpu_temp": 48.3, "unit": "X"}, False, "X"),
        ({"cpu_temp": 48.3}, True, None),
        ({"cpu_temp": 48.3, "unit": "u" * 8}, False, "u" * 8),
        ({"cpu_temp": 48.3, "unit": "u" * 100}, False, "u" * 8),
        ({"cpu_temp": 48.3, "unit": 5}, False, None),
        (None, False, None),
        ([], False, None),
    ],
)
async def test_cpu_temperature_fields(
    hass: HomeAssistant, loaded: PiHoleV6ConfigEntry, sensors: Any, available: bool, unit: str | None
) -> None:
    """The report tells whether a temperature is read and in which unit, never the value itself."""
    loaded.runtime_data.api.cache_padd = {"sensors": sensors}

    result = await async_get_config_entry_diagnostics(hass, loaded)

    assert result["pihole"]["cpu_temperature_available"] is available
    assert result["pihole"]["temperature_unit"] == unit


async def test_cpu_temperature_fields_without_sensors(hass: HomeAssistant, loaded: PiHoleV6ConfigEntry) -> None:
    """A padd response without sensors gives an unavailable probe and no unit."""
    loaded.runtime_data.api.cache_padd = {"host_model": "Raspberry Pi 4"}

    result = await async_get_config_entry_diagnostics(hass, loaded)

    assert result["pihole"]["cpu_temperature_available"] is False
    assert result["pihole"]["temperature_unit"] is None


async def test_cpu_temperature_value_and_probes_are_not_reported(
    hass: HomeAssistant, loaded: PiHoleV6ConfigEntry
) -> None:
    """The reading, the hot limit and the probe list stay out of the report."""
    loaded.runtime_data.api.cache_padd = {
        "sensors": {"cpu_temp": 48.31337, "unit": "C", "hot_limit": 61.7, "list": [{"name": EXTRA}]},
    }

    dumped = json.dumps(await async_get_config_entry_diagnostics(hass, loaded))

    assert "48.31337" not in dumped
    assert "61.7" not in dumped
    assert EXTRA not in dumped


# --------------------------------------------------------------------------------------------------
# Network tracking options
# --------------------------------------------------------------------------------------------------

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
NOW_TS = int(NOW.timestamp())
DAY = 86400


def _network(*ages: int | None) -> list[dict[str, Any]]:
    """Return network devices whose last query is `age` seconds old, or missing for None."""
    devices: list[dict[str, Any]] = []
    for index, age in enumerate(ages):
        device: dict[str, Any] = {"hwaddr": f"00:00:00:00:00:{index:02x}", "ips": []}
        if age is not None:
            device["lastQuery"] = NOW_TS - age
        devices.append(device)
    return devices


@pytest.mark.parametrize(
    ("overrides", "stale_days", "consider_home"),
    [
        ({}, 30, 240),
        ({CONF_DEVICE_TRACKER_STALE_DAYS: 30, CONF_DEVICE_TRACKER_CONSIDER_HOME: 600}, 30, 600),
        ({CONF_DEVICE_TRACKER_STALE_DAYS: 0, CONF_DEVICE_TRACKER_CONSIDER_HOME: 60}, 0, 60),
        ({CONF_DEVICE_TRACKER_STALE_DAYS: "x", CONF_DEVICE_TRACKER_CONSIDER_HOME: [1]}, None, None),
    ],
)
async def test_settings_report_the_tracking_options(
    hass: HomeAssistant, overrides: dict[str, Any], stale_days: int | None, consider_home: int | None
) -> None:
    """The two options are reported as numbers, with the defaults for an entry that holds none."""
    entry = _entry(**overrides)
    entry.add_to_hass(hass)

    settings = (await async_get_config_entry_diagnostics(hass, entry))["settings"]  # type: ignore[arg-type]

    assert settings["device_tracker_stale_days"] == stale_days
    assert settings["device_tracker_consider_home"] == consider_home


@pytest.mark.parametrize(
    ("whitelist", "stale_days", "expected"),
    [
        (False, 0, 0),
        (False, 30, 2),
        (True, 30, 0),
    ],
    ids=["setting-off", "setting-on", "whitelist-active"],
)
async def test_stale_counter(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    loaded: PiHoleV6ConfigEntry,
    whitelist: bool,
    stale_days: int,
    expected: int,
) -> None:
    """Stale devices are counted when the setting is on, and none with it off or with an active whitelist."""
    freezer.move_to(NOW)
    loaded.runtime_data.api.cache_network_devices = _network(60, 31 * DAY, 0, None)
    # The entry holds an address list: in whitelist mode it is active, in blacklist mode it is not.
    hass.config_entries.async_update_entry(
        loaded,
        data={**loaded.data, CONF_DEVICE_TRACKER_WHITELIST: whitelist, CONF_DEVICE_TRACKER_STALE_DAYS: stale_days},
    )

    tracker = (await async_get_config_entry_diagnostics(hass, loaded))["device_tracker"]

    assert tracker["stale"] == expected
    assert tracker["network_devices_reported"] == 4
    assert tracker["without_last_query"] == 1


async def test_stale_counter_with_an_empty_whitelist(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, loaded: PiHoleV6ConfigEntry
) -> None:
    """A whitelist without any address is not active: the stale devices are counted."""
    freezer.move_to(NOW)
    loaded.runtime_data.api.cache_network_devices = _network(60, 31 * DAY)
    hass.config_entries.async_update_entry(
        loaded,
        data={
            **loaded.data,
            CONF_DEVICE_TRACKER_WHITELIST: True,
            CONF_DEVICE_TRACKER_MAC_LIST: "",
            CONF_DEVICE_TRACKER_STALE_DAYS: 30,
        },
    )

    assert (await async_get_config_entry_diagnostics(hass, loaded))["device_tracker"]["stale"] == 1


@pytest.mark.parametrize("devices", [None, "devices", {"hwaddr": "x"}, [], ["not a dict", 5, None]], ids=repr)
async def test_stale_counter_on_odd_caches(hass: HomeAssistant, loaded: PiHoleV6ConfigEntry, devices: Any) -> None:
    """A cache that is not a list of objects gives a counter of zero rows or counts the unusable ones, never an error."""
    hass.config_entries.async_update_entry(
        loaded, data={**loaded.data, CONF_DEVICE_TRACKER_WHITELIST: False, CONF_DEVICE_TRACKER_STALE_DAYS: 30}
    )
    loaded.runtime_data.api.cache_network_devices = devices

    tracker = (await async_get_config_entry_diagnostics(hass, loaded))["device_tracker"]

    assert tracker["stale"] == (3 if isinstance(devices, list) and devices else 0)


async def test_no_marker_with_the_options_set(hass: HomeAssistant, loaded: PiHoleV6ConfigEntry) -> None:
    """The report with the two options on holds the new keys and still no marker."""
    hass.config_entries.async_update_entry(
        loaded, data={**loaded.data, CONF_DEVICE_TRACKER_STALE_DAYS: 30, CONF_DEVICE_TRACKER_CONSIDER_HOME: 600}
    )

    result = await async_get_config_entry_diagnostics(hass, loaded)
    dumped = json.dumps(result)

    assert {"stale", "without_last_query"} <= set(result["device_tracker"])
    assert {"device_tracker_stale_days", "device_tracker_consider_home"} <= set(result["settings"])
    for marker in MARKERS:
        assert marker not in dumped


@pytest.mark.parametrize(
    ("level", "expected"),
    [(0, "show_everything"), (1, "hide_domains"), (2, "hide_domains_and_clients"), (3, "anonymous"), (None, None)],
)
async def test_privacy_level_field(
    hass: HomeAssistant, loaded: PiHoleV6ConfigEntry, level: int | None, expected: str | None
) -> None:
    """The report names the privacy level of Pi-hole, or nothing while it is unknown."""
    loaded.runtime_data.api.cache_privacy_level = level

    result = await async_get_config_entry_diagnostics(hass, loaded)

    assert result["pihole"]["privacy_level"] == expected
