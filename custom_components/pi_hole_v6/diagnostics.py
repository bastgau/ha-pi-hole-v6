"""Diagnostics support for Pi-hole V6.

The report is built field by field from an allow list: nothing is copied in bulk from the
config entry or from the caches of the client, so a field added later by Pi-hole can never leak.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import urlsplit

from homeassistant.components.diagnostics import async_redact_data  # pyright: ignore[reportUnknownVariableType]
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_URL, Platform
from homeassistant.helpers import entity_registry as er

from .const import (
    ACCESS_WITHOUT_SESSIONS,
    CONF_CERT_FINGERPRINT,
    CONF_DEVICE_TRACKER_CONSIDER_HOME,
    CONF_DEVICE_TRACKER_MAC_LIST,
    CONF_DEVICE_TRACKER_STALE_DAYS,
    CONF_DEVICE_TRACKER_WHITELIST,
    CONF_ENABLE_DEVICE_TRACKER,
    CONF_UPDATE_INTERVAL_LIVE,
    CONF_UPDATE_INTERVAL_PRESENCE,
    CONF_UPDATE_INTERVAL_STATS,
    CONF_VERIFY_SSL,
    COORDINATOR_LIVE,
    COORDINATOR_STATS,
    DEFAULT_DEVICE_TRACKER_CONSIDER_HOME,
    DEFAULT_DEVICE_TRACKER_MAC_LIST,
    DEFAULT_DEVICE_TRACKER_STALE_DAYS,
    DEFAULT_DEVICE_TRACKER_WHITELIST,
    DEFAULT_ENABLE_DEVICE_TRACKER,
    DEFAULT_UPDATE_INTERVAL_PRESENCE,
    LEGACY_VERIFY_SSL,
    MAX_NETWORK_DEVICES,
)
from .device_tracker import _build_stale_filter  # pyright: ignore[reportPrivateUsage]
from .helper import parse_mac_list

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

    from . import PiHoleV6ConfigEntry
    from .api import Api
    from .presence import PiHoleV6PresenceCoordinator, PresenceSnapshot

# Safety net only: the report is built from an allow list and holds none of these values.
TO_REDACT: set[str] = {CONF_URL, CONF_PASSWORD, CONF_CERT_FINGERPRINT, CONF_NAME, CONF_DEVICE_TRACKER_MAC_LIST}

# The longest free text taken from the Pi-hole that a report keeps.
_MAX_TEXT_LENGTH = 64

# The longest temperature unit kept ("C", "F" or "K" are expected).
_MAX_UNIT_LENGTH = 8

# The components of the Pi-hole whose versions are reported, as named in the padd response.
_VERSION_COMPONENTS: tuple[str, ...] = ("core", "web", "ftl", "docker")

# The counters of the summary that are reported, as (name in the report, section, key in the summary).
_SUMMARY_COUNTERS: tuple[tuple[str, str, str], ...] = (
    ("queries_total", "queries", "total"),
    ("queries_blocked", "queries", "blocked"),
    ("percent_blocked", "queries", "percent_blocked"),
    ("queries_cached", "queries", "cached"),
    ("queries_forwarded", "queries", "forwarded"),
    ("unique_domains", "queries", "unique_domains"),
    ("clients_active", "clients", "active"),
    ("clients_total", "clients", "total"),
    ("domains_being_blocked", "gravity", "domains_being_blocked"),
)


def _dict(value: Any) -> dict[str, Any]:
    """Return the value when it is a dictionary, an empty one otherwise.

    Args:
        value (Any): The value read from a cache, of any shape.

    Returns:
        dict[str, Any]: The value itself, or an empty dictionary.

    """
    return cast("dict[str, Any]", value) if isinstance(value, dict) else {}


def _number(value: Any) -> int | float | None:
    """Return the value when it is a number, None otherwise.

    Args:
        value (Any): The value read from a cache, of any shape.

    Returns:
        int | float | None: The number, or None for anything else (a boolean is not a number here).

    """
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _text(value: Any) -> str | None:
    """Return the value when it is a string, None otherwise.

    Args:
        value (Any): The value read from a cache, of any shape.

    Returns:
        str | None: The string, or None for anything else.

    """
    return value if isinstance(value, str) else None


def _truncate(value: str | None, limit: int = _MAX_TEXT_LENGTH) -> str | None:
    """Bound a text that comes from the Pi-hole, so a report cannot carry an unexpectedly long value.

    Args:
        value (str | None): The text, or None.
        limit (int): The maximum number of characters kept.

    Returns:
        str | None: The text cut to the limit, or None.

    """
    return value[:limit] if value is not None else None


def _length(value: Any, kinds: tuple[type, ...] = (list, dict)) -> int:
    """Return the number of items of a list or a dictionary, 0 for any other shape.

    Args:
        value (Any): The value read from a cache, of any shape.
        kinds (tuple[type, ...]): The shapes that are counted, a list or a dictionary by default.

    Returns:
        int: The number of items.

    """
    return len(cast("list[Any]", value)) if isinstance(value, kinds) else 0


def _is_loaded(entry: PiHoleV6ConfigEntry) -> bool:
    """Tell whether the entry is set up and holds its runtime data.

    Args:
        entry (PiHoleV6ConfigEntry): The config entry.

    Returns:
        bool: True when the entry is loaded and its runtime data exists.

    """
    return entry.state is ConfigEntryState.LOADED and getattr(entry, "runtime_data", None) is not None


def _entry(entry: PiHoleV6ConfigEntry) -> dict[str, Any]:
    """Describe the config entry itself, without its data.

    Args:
        entry (PiHoleV6ConfigEntry): The config entry.

    Returns:
        dict[str, Any]: The version, source and state of the entry, and whether its unique id still matches its URL.

    """
    url: Any = entry.data.get(CONF_URL)

    return {
        "version": entry.version,
        "minor_version": entry.minor_version,
        "source": entry.source,
        "state": entry.state.value,
        "unique_id_matches_url": isinstance(url, str) and entry.unique_id == url.lower(),
    }


def _settings(entry: PiHoleV6ConfigEntry) -> dict[str, Any]:
    """Describe the settings of the entry, never the URL, the password or the fingerprint.

    Args:
        entry (PiHoleV6ConfigEntry): The config entry.

    Returns:
        dict[str, Any]: The settings that matter to a diagnosis, as booleans, counts and intervals. The URL scheme falls back to "http" when the URL is missing or unreadable.

    """
    data: dict[str, Any] = dict(entry.data)
    url: Any = data.get(CONF_URL)
    parts = urlsplit(url) if isinstance(url, str) else None
    mac_list: Any = data.get(CONF_DEVICE_TRACKER_MAC_LIST, DEFAULT_DEVICE_TRACKER_MAC_LIST)

    return {
        "update_interval_live": _number(data.get(CONF_UPDATE_INTERVAL_LIVE)),
        "update_interval_stats": _number(data.get(CONF_UPDATE_INTERVAL_STATS)),
        "update_interval_presence": _number(data.get(CONF_UPDATE_INTERVAL_PRESENCE, DEFAULT_UPDATE_INTERVAL_PRESENCE)),
        "url_scheme": "https" if parts is not None and parts.scheme.lower() == "https" else "http",
        "url_path_ends_with_api": parts is not None and parts.path.rstrip("/").endswith("/api"),
        "verify_ssl": bool(data.get(CONF_VERIFY_SSL, LEGACY_VERIFY_SSL)),
        "certificate_pinned": bool(data.get(CONF_CERT_FINGERPRINT)),
        "password_set": bool(data.get(CONF_PASSWORD)),
        "enable_device_tracker": bool(data.get(CONF_ENABLE_DEVICE_TRACKER, DEFAULT_ENABLE_DEVICE_TRACKER)),
        "device_tracker_whitelist": bool(data.get(CONF_DEVICE_TRACKER_WHITELIST, DEFAULT_DEVICE_TRACKER_WHITELIST)),
        "device_tracker_address_count": len(parse_mac_list(mac_list)) if isinstance(mac_list, str) else 0,
        "device_tracker_stale_days": _number(
            data.get(CONF_DEVICE_TRACKER_STALE_DAYS, DEFAULT_DEVICE_TRACKER_STALE_DAYS)
        ),
        "device_tracker_consider_home": _number(
            data.get(CONF_DEVICE_TRACKER_CONSIDER_HOME, DEFAULT_DEVICE_TRACKER_CONSIDER_HOME)
        ),
    }


def _coordinator(coordinator: DataUpdateCoordinator[Any], api: Api, coordinator_key: str) -> dict[str, Any]:
    """Describe a coordinator. The exception is reported by its class name only: its message may hold the host.

    Args:
        coordinator (DataUpdateCoordinator[Any]): The coordinator.
        api (Api): The API client, which keeps the time of the last refresh.
        coordinator_key (str): The identifier of the coordinator in the client (COORDINATOR_LIVE or COORDINATOR_STATS).

    Returns:
        dict[str, Any]: The interval, the outcome and the time of the last refresh.

    """
    interval = coordinator.update_interval
    last_exception = coordinator.last_exception
    last_refresh: datetime | None = api.last_refresh.get(coordinator_key)

    return {
        "update_interval": interval.total_seconds() if interval is not None else None,
        "last_update_success": coordinator.last_update_success,
        "last_exception": type(last_exception).__name__ if last_exception is not None else None,
        "last_refresh": last_refresh.isoformat() if last_refresh is not None else None,
    }


def _versions(padd: dict[str, Any]) -> tuple[dict[str, Any], dict[str, bool | None]]:
    """Read the installed and the latest versions of each component from the padd cache.

    Args:
        padd (dict[str, Any]): The padd cache of the client.

    Returns:
        tuple[dict[str, Any], dict[str, bool | None]]: The versions, and whether an update is available (None when it cannot be told).

    """
    raw: dict[str, Any] = _dict(padd.get("version"))
    versions: dict[str, Any] = {}
    updates: dict[str, bool | None] = {}

    for component in _VERSION_COMPONENTS:
        info: dict[str, Any] = _dict(raw.get(component))
        local: Any = info.get("local")
        remote: Any = info.get("remote")

        # Core, web and FTL give a dictionary holding the version, Docker gives the version itself.
        local_version: str | None = _text(_dict(local).get("version")) if isinstance(local, dict) else _text(local)
        remote_version: str | None = _text(_dict(remote).get("version")) if isinstance(remote, dict) else _text(remote)

        versions[component] = {"local": local_version, "remote": remote_version}
        updates[component] = (
            local_version != remote_version if local_version is not None and remote_version is not None else None
        )

    return versions, updates


def _pihole(api: Api) -> dict[str, Any]:
    """Describe what the Pi-hole reported, as versions, counters and sizes, never as the data itself.

    Args:
        api (Api): The API client.

    Returns:
        dict[str, Any]: The versions, the counters and the sizes of the lists.

    """
    padd: dict[str, Any] = _dict(api.cache_padd)
    summary: dict[str, Any] = _dict(api.cache_summary)
    ftl_info: dict[str, Any] = _dict(api.cache_ftl_info)
    versions, updates = _versions(padd)

    messages: Any = ftl_info.get("message_list")
    types: list[str] = sorted(
        message_type
        for message in (cast("list[Any]", messages) if isinstance(messages, list) else [])
        if (message_type := _text(_dict(message).get("type"))) is not None
    )

    sessions_listed: bool = api.account_access not in ACCESS_WITHOUT_SESSIONS

    return {
        "account_access": _text(api.account_access),
        "versions": versions,
        "updates_available": updates,
        "blocking": _text(_dict(api.cache_blocking).get("blocking")),
        "host_model": _truncate(_text(padd.get("host_model"))),
        "cpu_temperature_available": api.cpu_temperature_celsius() is not None,
        "temperature_unit": _truncate(_text(_dict(padd.get("sensors")).get("unit")), _MAX_UNIT_LENGTH),
        "counters": {name: _number(_dict(summary.get(section)).get(key)) for name, section, key in _SUMMARY_COUNTERS},
        "sizes": {
            "groups": _length(api.cache_groups),
            "configured_clients": _length(api.cache_configured_clients),
            "dhcp_leases": _length(api.cache_dhcp_leases),
            "auth_sessions": _length(api.cache_auth_sessions) if sessions_listed else None,
            "network_devices": _length(api.cache_network_devices, kinds=(list,)),
        },
        "ftl_messages": {
            "count": _number(ftl_info.get("message_count")),
            "status": _text(ftl_info.get("status")),
            "types": types,
        },
    }


def _device_tracker(hass: HomeAssistant, entry: PiHoleV6ConfigEntry) -> dict[str, Any]:
    """Describe the network devices known to the device tracker, as counters only.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        entry (PiHoleV6ConfigEntry): The config entry.

    Returns:
        dict[str, Any]: The number of tracked entities and of network devices reported by the Pi-hole.

    """
    registry = er.async_get(hass)
    tracked: int = sum(
        1
        for entity in er.async_entries_for_config_entry(registry, entry.entry_id)
        if entity.domain == Platform.DEVICE_TRACKER
    )

    devices: Any = entry.runtime_data.api.cache_network_devices
    rows: list[Any] = cast("list[Any]", devices) if isinstance(devices, list) else []
    without_last_query: int = sum(1 for device in rows if not _dict(device).get("lastQuery"))

    # Zero when the setting is off or a whitelist is active.
    is_stale = _build_stale_filter(entry, datetime.now(UTC))
    stale: int = sum(1 for device in rows if is_stale(_dict(device)))

    return {
        "tracked_entities": tracked,
        "network_devices_reported": len(rows),
        "max_network_devices": MAX_NETWORK_DEVICES,
        "cap_reached": len(rows) >= MAX_NETWORK_DEVICES,
        "without_last_query": without_last_query,
        "stale": stale,
    }


def _presence(coordinator: PiHoleV6PresenceCoordinator | None) -> dict[str, Any]:
    """Describe the presence coordinator, as counters only.

    Never an IP address, a MAC address, a client name, a domain, a cursor or the start of the window: the exception is reported by its class name.

    Args:
        coordinator (PiHoleV6PresenceCoordinator | None): The presence coordinator, None when the presence refresh is disabled.

    Returns:
        dict[str, Any]: Whether the coordinator exists and listens, its interval and outcome, and the statistics of its last successful read (None until there is one).

    """
    if coordinator is None:
        return {
            "enabled": False,
            "listening": False,
            "update_interval": None,
            "last_update_success": None,
            "last_exception": None,
            "last_read": None,
        }

    interval = coordinator.update_interval
    snapshot = cast("PresenceSnapshot | None", coordinator.data)
    last_read: dict[str, Any] | None = None

    if snapshot is not None:
        last_read = {
            "fetched_at": snapshot.fetched_at.isoformat(),
            "complete": snapshot.complete,
            "pages": snapshot.pages,
            "queries_read": snapshot.queries_read,
            "duration_seconds": round(snapshot.duration, 3),
            "clients_seen": snapshot.clients_seen,
            "clients_matched": snapshot.clients_matched,
        }

    return {
        "enabled": True,
        "listening": coordinator.listening,
        "update_interval": interval.total_seconds() if interval is not None else None,
        # None until a read has been attempted: Home Assistant starts the flag at True.
        "last_update_success": (
            coordinator.last_update_success if snapshot is not None or coordinator.last_read_error is not None else None
        ),
        "last_exception": coordinator.last_read_error,
        "last_read": last_read,
    }


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: PiHoleV6ConfigEntry) -> dict[str, Any]:
    """Return the diagnostics of a config entry, without any personal or network data.

    The state held in memory is read as it is: no refresh is forced and no exception is raised, so
    the report can be produced for the very failure it is meant to diagnose.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        entry (PiHoleV6ConfigEntry): The config entry to report on.

    Returns:
        dict[str, Any]: The report. An entry that is not loaded only gets "entry", "settings" and "loaded".

    """
    loaded: bool = _is_loaded(entry)

    result: dict[str, Any] = {
        "entry": _entry(entry),
        "settings": _settings(entry),
        "loaded": loaded,
    }

    if loaded:
        runtime = entry.runtime_data
        result["coordinators"] = {
            COORDINATOR_LIVE: _coordinator(runtime.coordinator, runtime.api, COORDINATOR_LIVE),
            COORDINATOR_STATS: _coordinator(runtime.coordinator_stats, runtime.api, COORDINATOR_STATS),
        }
        result["pihole"] = _pihole(runtime.api)
        result["device_tracker"] = _device_tracker(hass, entry)
        result["presence"] = _presence(runtime.coordinator_presence)

    return cast("dict[str, Any]", async_redact_data(result, TO_REDACT))
