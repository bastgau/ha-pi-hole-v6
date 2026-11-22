"""Check the pure logic of the network device options: the last query, the whitelist and the stale filter.

The entry is replaced by an object holding only `data`, like tests/test_verify_ssl.py: nothing here needs Home Assistant.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

from custom_components.pi_hole_v6.const import (
    CONF_DEVICE_TRACKER_MAC_LIST,
    CONF_DEVICE_TRACKER_STALE_DAYS,
    CONF_DEVICE_TRACKER_WHITELIST,
)
from custom_components.pi_hole_v6.device_tracker import (
    _build_stale_filter,
    _is_whitelist_active,
    _last_query,
    is_stale_filter_enabled,
)
import pytest

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
DAY = 86400
LISTED = "aa:bb:cc:dd:ee:ff"


def _entry(**data: Any) -> Any:
    """Return a stand-in for a config entry holding the given data."""
    return cast("Any", SimpleNamespace(data=data))


def _aged(days: float | None) -> dict[str, Any]:
    """Return a network device whose last query is the given number of days old, or without one."""
    device: dict[str, Any] = {"hwaddr": LISTED, "ips": []}
    if days is not None:
        device["lastQuery"] = int(NOW.timestamp() - days * DAY)
    return device


@pytest.mark.parametrize(
    ("device", "expected"),
    [
        ({}, None),
        ({"lastQuery": None}, None),
        ({"lastQuery": 0}, None),
        ({"lastQuery": True}, None),
        ({"lastQuery": False}, None),
        ({"lastQuery": -5}, None),
        ({"lastQuery": "123"}, None),
        ({"lastQuery": 1.5}, None),
        ({"lastQuery": [1]}, None),
        ({"lastQuery": 1}, 1),
        ({"lastQuery": 1700000000}, 1700000000),
    ],
    ids=repr,
)
def test_last_query(device: dict[str, Any], expected: int | None) -> None:
    """Only an integer above zero is a usable last query."""
    assert _last_query(device) == expected


@pytest.mark.parametrize("data", [{}, {CONF_DEVICE_TRACKER_STALE_DAYS: 0}], ids=["not-stored", "zero"])
@pytest.mark.parametrize("age_days", [None, 0, 1, 30, 3650])
def test_nothing_is_stale_when_the_setting_is_off(data: dict[str, Any], age_days: int | None) -> None:
    """With 0 days, or no value at all, no device is stale, whatever its last query."""
    entry = _entry(**data)
    is_stale = _build_stale_filter(entry, NOW)

    assert not is_stale(_aged(age_days))
    assert not is_stale({"hwaddr": LISTED, "ips": [], "lastQuery": 0})
    assert not is_stale_filter_enabled(entry)


@pytest.mark.parametrize(
    ("age_days", "expected"),
    [
        (0, False),
        (29, False),
        (30, False),
        (30.01, True),
        (31, True),
        (400, True),
        (None, True),
    ],
)
def test_stale_after_the_configured_number_of_days(age_days: float | None, expected: bool) -> None:
    """With 30 days, a device is stale beyond 30 days or without any last query."""
    entry = _entry(**{CONF_DEVICE_TRACKER_STALE_DAYS: 30})

    assert _build_stale_filter(entry, NOW)(_aged(age_days)) is expected
    assert is_stale_filter_enabled(entry)


@pytest.mark.parametrize("last_query", [0, None, True, -5, "123"])
def test_unusable_last_query_is_stale(last_query: Any) -> None:
    """A last query that is not a positive integer makes the device stale when the setting is on."""
    entry = _entry(**{CONF_DEVICE_TRACKER_STALE_DAYS: 30})
    device = {"hwaddr": LISTED, "ips": [], "lastQuery": last_query}

    assert _build_stale_filter(entry, NOW)(device) is True


@pytest.mark.parametrize("days", [True, False, "30", None, -1, 2.5, [30]], ids=repr)
def test_unusable_stale_days_disable_the_filter(days: Any) -> None:
    """A stored value that is not a positive integer never marks a device stale."""
    entry = _entry(**{CONF_DEVICE_TRACKER_STALE_DAYS: days})

    assert not is_stale_filter_enabled(entry)
    assert not _build_stale_filter(entry, NOW)(_aged(None))


@pytest.mark.parametrize(
    ("data", "active"),
    [
        ({CONF_DEVICE_TRACKER_WHITELIST: True, CONF_DEVICE_TRACKER_MAC_LIST: LISTED}, True),
        ({CONF_DEVICE_TRACKER_WHITELIST: True, CONF_DEVICE_TRACKER_MAC_LIST: f"{LISTED}, 11:22:33:44:55:66"}, True),
        ({CONF_DEVICE_TRACKER_MAC_LIST: LISTED}, True),
        ({CONF_DEVICE_TRACKER_WHITELIST: True, CONF_DEVICE_TRACKER_MAC_LIST: ""}, False),
        ({CONF_DEVICE_TRACKER_WHITELIST: True, CONF_DEVICE_TRACKER_MAC_LIST: " ,\n "}, False),
        ({CONF_DEVICE_TRACKER_WHITELIST: False, CONF_DEVICE_TRACKER_MAC_LIST: LISTED}, False),
        ({CONF_DEVICE_TRACKER_WHITELIST: False, CONF_DEVICE_TRACKER_MAC_LIST: ""}, False),
        ({}, False),
    ],
)
def test_whitelist_is_active_only_with_a_listed_address(data: dict[str, Any], active: bool) -> None:
    """The whitelist is active in whitelist mode with a non-empty list, and the mode defaults to whitelist."""
    assert _is_whitelist_active(_entry(**data)) is active


@pytest.mark.parametrize("age_days", [None, 0, 60, 4000])
def test_active_whitelist_never_marks_a_device_stale(age_days: int | None) -> None:
    """The user named the devices to follow: an absent one keeps its entity, however old."""
    entry = _entry(
        **{
            CONF_DEVICE_TRACKER_STALE_DAYS: 30,
            CONF_DEVICE_TRACKER_WHITELIST: True,
            CONF_DEVICE_TRACKER_MAC_LIST: LISTED,
        }
    )

    assert not is_stale_filter_enabled(entry)
    assert not _build_stale_filter(entry, NOW)(_aged(age_days))


@pytest.mark.parametrize(
    "data",
    [
        {CONF_DEVICE_TRACKER_WHITELIST: True, CONF_DEVICE_TRACKER_MAC_LIST: ""},
        {CONF_DEVICE_TRACKER_WHITELIST: True},
        {CONF_DEVICE_TRACKER_WHITELIST: False, CONF_DEVICE_TRACKER_MAC_LIST: LISTED},
        {CONF_DEVICE_TRACKER_WHITELIST: False, CONF_DEVICE_TRACKER_MAC_LIST: ""},
    ],
    ids=["whitelist-empty-list", "whitelist-no-list", "blacklist", "blacklist-empty-list"],
)
def test_filter_applies_without_active_whitelist(data: dict[str, Any]) -> None:
    """An empty list in whitelist mode, or a blacklist, leaves the stale filter in force."""
    entry = _entry(**{CONF_DEVICE_TRACKER_STALE_DAYS: 30}, **data)
    is_stale = _build_stale_filter(entry, NOW)

    assert is_stale_filter_enabled(entry)
    assert is_stale(_aged(60))
    assert is_stale(_aged(None))
    assert not is_stale(_aged(1))


def test_now_is_taken_from_the_argument() -> None:
    """The limit depends on the time given, not on the clock."""
    entry = _entry(**{CONF_DEVICE_TRACKER_STALE_DAYS: 1})
    device = _aged(0)

    assert not _build_stale_filter(entry, NOW)(device)
    assert _build_stale_filter(entry, datetime.fromtimestamp(NOW.timestamp() + 2 * DAY, tz=UTC))(device)
