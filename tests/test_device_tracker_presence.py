"""Check the faster arrival detection of the network device trackers, through a real setup.

The live fetch fills the network table of the client from a holder the tests edit, and the read of the query log is
replaced by a fake one that answers from another holder (client address -> time of its newest query). Nothing reaches
the network. Time is frozen: the presence refreshes are fired by moving the clock, like Home Assistant does.
"""

from __future__ import annotations

import asyncio
from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.pi_hole_v6.api import Api, QueryActivity
from custom_components.pi_hole_v6.const import (
    CONF_DEVICE_TRACKER_CONSIDER_HOME,
    CONF_DEVICE_TRACKER_MAC_LIST,
    CONF_DEVICE_TRACKER_STALE_DAYS,
    CONF_DEVICE_TRACKER_WHITELIST,
    CONF_ENABLE_DEVICE_TRACKER,
    CONF_UPDATE_INTERVAL_LIVE,
    CONF_UPDATE_INTERVAL_PRESENCE,
    CONF_UPDATE_INTERVAL_STATS,
    DOMAIN,
)
from custom_components.pi_hole_v6.device_tracker import PiHoleV6DeviceTracker
from custom_components.pi_hole_v6.exceptions import (
    BadRequestError,
    CertificateChangedError,
    CertificateError,
    ClientConnectorError,
    DataStructureError,
    ForbiddenError,
    MethodNotAllowedError,
    NotFoundError,
    PiHoleV6Error,
    QueryLogUnavailableError,
    ServerError,
    ServiceUnavailableError,
    TooManyRequestsError,
    UnauthorizedError,
)
from custom_components.pi_hole_v6.presence import get_presence_interval
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    STATE_HOME,
    STATE_NOT_HOME,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from .test_device_tracker import FRESH, INTEGRATION, NOW, STALE, Harness, _device, _mac

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Iterator

    from custom_components.pi_hole_v6 import PiHoleV6ConfigEntry
    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant

IP_A = "192.168.10.11"
IP_B = "192.168.10.12"
IP_C = "192.168.10.13"
IP_D = "192.168.10.14"
IP_E = "192.168.10.15"
OLD = 600
PRESENCE = 30
# Intervals of the other coordinators, far enough for the live and stats refreshes never to fire by themselves.
SLOW = {CONF_UPDATE_INTERVAL_LIVE: 1800, CONF_UPDATE_INTERVAL_STATS: 3600}


class PresenceHarness(Harness):  # pylint: disable=too-many-instance-attributes
    """The harness of the device trackers, with a fake query log and the clock moved by firing the timers."""

    def __init__(self, hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
        """Prepare an empty query log."""
        super().__init__(hass, freezer)
        self.queries: dict[str, float] = {}
        self.error: PiHoleV6Error | None = None
        self.since: list[float] = []
        self.live_options: list[dict[str, Any]] = []
        self.logouts = 0
        self.settled = 0
        self.t0 = NOW.timestamp()
        self.logout_error: PiHoleV6Error | None = None
        self.logout_hangs = False
        self.lock_held: list[bool] = []
        self.complete = True
        self.enable_entities = True
        self.platforms: list[Platform] = [Platform.DEVICE_TRACKER]

    def make_entry(self, **options: Any) -> MockConfigEntry:
        """Add an entry whose live and stats refreshes are slow, so only the presence one fires in the tests."""
        return super().make_entry(**{**SLOW, **options})

    async def setup(self) -> PiHoleV6ConfigEntry:
        """Set the entry up, then let the live refresh owed to the second tracker added run.

        Each tracker is added with an update before adding, whose refresh request the debouncer of the live coordinator
        answers once more ten seconds later when two or more trackers ask for it. That is not under test: it is run now,
        so that what follows starts from a quiet state, and `settled` is the number of live fetches at that point.
        """
        entry = await super().setup()
        await self.fire(11)
        self.settled = self.live_calls
        self.t0 = dt_util.utcnow().timestamp()
        return entry

    @property
    def next_cycle(self) -> float:
        """Return the time, Pi-hole clock, of the next presence cycle fired with `STEP`."""
        return dt_util.utcnow().timestamp() + STEP

    @property
    def presence(self) -> Any:
        """Return the presence coordinator of the entry."""
        assert self.entry is not None
        return self.entry.runtime_data.coordinator_presence

    @contextmanager
    def fetches(self) -> Iterator[None]:
        """Replace the live fetch, the stats fetch, the logout and the read of the query log."""

        async def fake_live(api_client: Api, **options: Any) -> None:
            """Fill the network device cache like the live fetch does, and note how it was called."""
            self.live_calls += 1
            self.live_options.append(options)
            if self.failing:
                message = "down"
                raise UpdateFailed(message)
            api_client.cache_network_devices = [dict(device) for device in self.devices]

        async def fake_activity(since: float, **_: Any) -> QueryActivity:
            """Answer like the query log: the queries not older than `since`, or the error to raise."""
            self.since.append(since)
            self.lock_held.append(self.presence._refresh_lock.locked())  # pylint: disable=protected-access
            if self.error is not None:
                raise self.error
            seen = {ip: moment for ip, moment in self.queries.items() if moment >= since}
            return QueryActivity(
                last_seen_by_ip=seen,
                newest_time=max(seen.values()) if seen else None,
                pages=1,
                queries_read=len(seen),
                complete=self.complete,
                duration=0.25,
            )

        async def fake_logout() -> None:
            """Count the logouts."""
            self.logouts += 1
            if self.logout_hangs:
                await asyncio.sleep(3600)
            if self.logout_error is not None:
                raise self.logout_error

        with ExitStack() as stack:
            stack.enter_context(patch(f"{INTEGRATION}.PLATFORMS", self.platforms))
            if self.enable_entities:
                stack.enter_context(
                    patch.object(PiHoleV6DeviceTracker, "_attr_entity_registry_enabled_default", new=True)
                )
            stack.enter_context(patch(f"{INTEGRATION}.async_get_live_data", AsyncMock(side_effect=fake_live)))
            stack.enter_context(patch(f"{INTEGRATION}.async_get_stats_data", AsyncMock()))
            stack.enter_context(patch.object(Api, "call_get_ftl_info_messages", AsyncMock(return_value={})))
            stack.enter_context(patch.object(Api, "call_logout", AsyncMock(side_effect=fake_logout)))
            stack.enter_context(patch.object(Api, "call_get_query_activity", AsyncMock(side_effect=fake_activity)))
            yield

    async def fire(self, seconds: float) -> None:
        """Move the clock forward and run what is due, the way Home Assistant does."""
        self.freezer.tick(timedelta(seconds=seconds))
        with self.fetches():
            async_fire_time_changed(self.hass, dt_util.utcnow())
            await self.hass.async_block_till_done()

    async def cycles(self, count: int, step: float = PRESENCE) -> None:
        """Fire `count` successive steps."""
        for _ in range(count):
            await self.fire(step)

    def seen(self, label: str, age: float, *, at: float | None = None) -> None:
        """Record a query of a fixture device, `age` seconds before `at` (the current time by default)."""
        moment = (dt_util.utcnow().timestamp() if at is None else at) - age
        self.queries[{"A": IP_A, "B": IP_B, "C": IP_C, "D": IP_D, "E": IP_E}[label]] = moment

    @contextmanager
    def watch_writes(self) -> Iterator[list[str]]:
        """List the entities whose state is written while the block runs."""
        written: list[str] = []
        original = PiHoleV6DeviceTracker.async_write_ha_state

        def spy(entity: PiHoleV6DeviceTracker) -> None:
            """Note the write, then do it."""
            written.append(entity.entity_id)
            original(entity)

        with patch.object(PiHoleV6DeviceTracker, "async_write_ha_state", spy):
            yield written


@pytest.fixture(name="harness")
async def harness_fixture(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> AsyncGenerator[PresenceHarness]:
    """Return a harness on the frozen clock, unloading its entry afterwards to stop the coordinators."""
    freezer.move_to(NOW)
    harness = PresenceHarness(hass, freezer)
    yield harness
    if harness.entry is not None and harness.entry.state is ConfigEntryState.LOADED:
        with patch.object(Api, "call_logout", AsyncMock()):
            await hass.config_entries.async_unload(harness.entry.entry_id)
            await hass.async_block_till_done()


STEP = 31  # One presence cycle: the next refresh is due between 29 and 31 seconds after the previous one.
OPTION = {CONF_UPDATE_INTERVAL_PRESENCE: PRESENCE}


# --------------------------------------------------------------------------------------------------
# The option decides whether anything exists
# --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ({}, None),
        ({CONF_UPDATE_INTERVAL_PRESENCE: 0}, None),
        ({CONF_UPDATE_INTERVAL_PRESENCE: 0.0}, None),
        ({CONF_UPDATE_INTERVAL_PRESENCE: -5}, None),
        ({CONF_UPDATE_INTERVAL_PRESENCE: None}, None),
        ({CONF_UPDATE_INTERVAL_PRESENCE: True}, None),
        ({CONF_UPDATE_INTERVAL_PRESENCE: "30"}, None),
        ({CONF_UPDATE_INTERVAL_PRESENCE: [30]}, None),
        ({CONF_UPDATE_INTERVAL_PRESENCE: 15}, timedelta(seconds=15)),
        ({CONF_UPDATE_INTERVAL_PRESENCE: 30}, timedelta(seconds=30)),
        ({CONF_UPDATE_INTERVAL_PRESENCE: 45.5}, timedelta(seconds=45.5)),
        ({CONF_UPDATE_INTERVAL_PRESENCE: 300}, timedelta(seconds=300)),
    ],
    ids=repr,
)
def test_presence_interval_of_an_entry(data: dict[str, Any], expected: timedelta | None) -> None:
    """Only a number above zero gives an interval: absent, 0 or unreadable means disabled."""
    entry: Any = type("Entry", (), {"data": data})()

    assert get_presence_interval(entry) == expected


@pytest.mark.parametrize("stored", [None, 0], ids=["absent", "zero"])
async def test_disabled_by_default_creates_nothing_and_calls_nothing(
    harness: PresenceHarness, stored: int | None
) -> None:
    """With the option absent or at 0 there is no coordinator, no read of the query log, and the former live fetch."""
    harness.make_entry(**{CONF_UPDATE_INTERVAL_PRESENCE: stored})
    harness.devices = [_device("B", OLD)]
    harness.seen("B", 1)

    entry = await harness.setup()
    await harness.cycles(12)

    assert entry.runtime_data.coordinator_presence is None
    assert harness.since == []
    assert harness.state("B") == STATE_NOT_HOME
    assert harness.live_options == [{"enable_device_tracker": True, "max_addresses": None}] * harness.live_calls
    assert harness.live_calls == harness.settled


async def test_tracking_disabled_creates_no_presence_coordinator(harness: PresenceHarness) -> None:
    """The option has no effect when the network devices are not tracked, and the live fetch is unchanged."""
    harness.make_entry(**OPTION, **{CONF_ENABLE_DEVICE_TRACKER: False})
    harness.devices = [_device("B", OLD)]
    harness.seen("B", 1)

    entry = await harness.setup()
    await harness.cycles(5)

    assert entry.runtime_data.coordinator_presence is None
    assert harness.since == []
    assert harness.entity_id("B") is None
    assert harness.live_options == [{"enable_device_tracker": False, "max_addresses": None}] * harness.live_calls


async def test_tracking_key_absent_means_disabled(harness: PresenceHarness) -> None:
    """An entry that never stored the tracking option (disabled by default) gets no presence coordinator either."""
    harness.make_entry(**OPTION, **{CONF_ENABLE_DEVICE_TRACKER: None})

    entry = await harness.setup()

    assert entry.runtime_data.coordinator_presence is None
    assert harness.live_options[0]["max_addresses"] is None


async def test_no_read_without_an_enabled_tracker(harness: PresenceHarness) -> None:
    """The coordinator exists but nobody listens (the trackers are disabled by default): it never polls."""
    harness.enable_entities = False
    harness.make_entry(**OPTION)
    harness.devices = [_device("B", OLD)]
    harness.seen("B", 1)

    entry = await harness.setup()
    await harness.cycles(5)

    assert entry.runtime_data.coordinator_presence is not None
    assert harness.presence.listening is False
    assert harness.since == []
    assert harness.presence.data is None


async def test_setup_never_reads_the_query_log(harness: PresenceHarness) -> None:
    """The first read happens one interval after the tracker listens, not at the setup."""
    harness.make_entry(**OPTION)
    harness.devices = [_device("B", OLD)]

    await harness.setup()

    assert harness.since == []
    assert harness.presence.data is None
    assert harness.presence.listening is True
    assert harness.presence.name == "Pihole presence"
    assert harness.presence.logger.name == "custom_components.pi_hole_v6.presence"
    assert harness.presence.update_interval == timedelta(seconds=PRESENCE)


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        ({CONF_UPDATE_INTERVAL_PRESENCE: 30}, 10),
        ({CONF_UPDATE_INTERVAL_PRESENCE: 15}, 10),
        ({CONF_UPDATE_INTERVAL_PRESENCE: 0}, None),
        ({}, None),
        ({CONF_UPDATE_INTERVAL_PRESENCE: 30, CONF_ENABLE_DEVICE_TRACKER: False}, None),
    ],
    ids=["30", "15", "zero", "absent", "no-tracking"],
)
async def test_max_addresses_is_asked_only_when_presence_is_active(
    harness: PresenceHarness, options: dict[str, Any], expected: int | None
) -> None:
    """Ten addresses per device are requested, at the setup and at every live refresh, only with the presence active."""
    harness.make_entry(**options)
    await harness.setup()
    await harness.refresh()

    assert len(harness.live_options) >= 2
    assert {call["max_addresses"] for call in harness.live_options} == {expected}


# --------------------------------------------------------------------------------------------------
# Arrival and departure
# --------------------------------------------------------------------------------------------------


async def test_arrival_is_seen_at_the_presence_cycle_without_a_live_refresh(harness: PresenceHarness) -> None:
    """A device whose table says away is home as soon as the query log shows a recent query for its address."""
    harness.make_entry(**OPTION)
    harness.devices = [_device("A", FRESH), _device("B", OLD)]
    entry = await harness.setup()
    assert harness.state("B") == STATE_NOT_HOME
    assert harness.state("A") == STATE_HOME
    harness.seen("B", 3)

    await harness.fire(STEP)

    assert harness.state("B") == STATE_HOME
    assert harness.state("A") == STATE_HOME
    assert harness.live_calls == harness.settled
    assert len(harness.since) == 1
    assert entry.runtime_data.coordinator.last_update_success is True


async def test_first_read_starts_at_the_away_delay_before_now(harness: PresenceHarness) -> None:
    """The first window is the away delay long, so an arrival during a restart is caught up."""
    harness.make_entry(**OPTION)
    harness.devices = [_device("B", OLD)]
    await harness.setup()

    await harness.fire(STEP)

    assert harness.since == [pytest.approx(dt_util.utcnow().timestamp() - 240)]


@pytest.mark.parametrize(("away", "window"), [(60, 60), (600, 600), (900, 900), (3600, 900), (86400, 900)])
async def test_first_window_is_capped(harness: PresenceHarness, away: int, window: int) -> None:
    """The window is the away delay, never more than 900 seconds."""
    harness.make_entry(**OPTION, **{CONF_DEVICE_TRACKER_CONSIDER_HOME: away})
    harness.devices = [_device("B", OLD)]
    await harness.setup()

    await harness.fire(STEP)

    assert harness.since == [pytest.approx(dt_util.utcnow().timestamp() - window)]


async def test_next_window_starts_just_before_the_newest_query(harness: PresenceHarness) -> None:
    """After a read, the window restarts five seconds before the newest query seen, and an empty window keeps it."""
    harness.make_entry(**OPTION)
    harness.devices = [_device("B", OLD)]
    await harness.setup()
    harness.seen("B", 3)
    newest = harness.queries[IP_B]

    await harness.cycles(3)

    assert harness.since[1] == pytest.approx(newest - 5)
    assert harness.since[2] == pytest.approx(newest - 5)


async def test_departure_is_seen_at_the_delay_plus_one_presence_cycle(harness: PresenceHarness) -> None:
    """Without new queries the device leaves at the first presence cycle after the away delay, not at a live one."""
    harness.make_entry(**OPTION)
    harness.devices = [_device("B", OLD)]
    await harness.setup()
    harness.queries[IP_B] = harness.t0
    states: list[tuple[int, str | None]] = []

    for cycle in range(1, 10):
        await harness.fire(STEP)
        states.append((cycle * STEP, harness.state("B")))

    assert [(elapsed, state) for elapsed, state in states if elapsed <= 240] == [
        (elapsed, STATE_HOME) for elapsed in range(STEP, 240, STEP)
    ]
    assert [state for elapsed, state in states if elapsed > 240] == [STATE_NOT_HOME] * 2
    assert harness.live_calls == harness.settled


async def test_a_device_stays_home_while_it_keeps_querying(harness: PresenceHarness) -> None:
    """A new query at each cycle keeps the device home well beyond the away delay."""
    harness.make_entry(**OPTION)
    harness.devices = [_device("B", OLD)]
    await harness.setup()

    for _ in range(12):
        harness.seen("B", 1, at=dt_util.utcnow().timestamp() + STEP)
        await harness.fire(STEP)
        assert harness.state("B") == STATE_HOME


@pytest.mark.parametrize(
    ("table_age", "log_age", "expected"),
    [
        (None, 10, STATE_HOME),
        (OLD, 10, STATE_HOME),
        (10, None, STATE_HOME),
        (OLD, None, STATE_NOT_HOME),
        (None, None, STATE_NOT_HOME),
        (OLD, 130, STATE_NOT_HOME),
        (10, 100, STATE_HOME),
        (100, 10, STATE_HOME),
    ],
    ids=repr,
)
async def test_the_newest_of_the_table_and_the_query_log_decides(
    harness: PresenceHarness, table_age: int | None, log_age: int | None, expected: str
) -> None:
    """The activity of a device is the newest of its last query in the table and in the query log."""
    harness.make_entry(**OPTION, **{CONF_DEVICE_TRACKER_CONSIDER_HOME: 120})
    harness.devices = [_device("B", table_age)]
    await harness.setup()
    # The age of a query is given at the time of the presence cycle, one step later.
    if log_age is not None:
        harness.queries[IP_B] = harness.next_cycle - log_age

    await harness.fire(STEP)

    assert harness.state("B") == expected


async def test_a_device_not_in_the_log_follows_the_table(harness: PresenceHarness) -> None:
    """Devices without a query in the log keep the table's verdict, whatever the other devices do."""
    harness.make_entry(**OPTION)
    harness.devices = [_device("A", FRESH), _device("B", OLD), _device("C", OLD)]
    await harness.setup()
    harness.seen("B", 2)

    await harness.fire(STEP)

    assert [harness.state(label) for label in "ABC"] == [STATE_HOME, STATE_HOME, STATE_NOT_HOME]


async def test_ipv6_and_second_address_of_a_device_are_attributed(harness: PresenceHarness) -> None:
    """A query from a spelling of a listed IPv6 address, not the first of the device, dates the device."""
    device = _device("B", OLD)
    device["ips"] = [*device["ips"], {"ip": "FE80:0:0:0:0:0:0:ABCD", "name": None, "lastSeen": 1700000100}]
    harness.make_entry(**OPTION)
    harness.devices = [device]
    await harness.setup()
    harness.queries["fe80::abcd"] = harness.next_cycle - 2

    await harness.fire(STEP)

    assert harness.state("B") == STATE_HOME


async def test_an_address_shared_by_two_devices_goes_to_the_most_recent(harness: PresenceHarness) -> None:
    """An address kept by an old lease on one device and by another now is attributed to the one seen last."""
    old_owner = _device("A", OLD)
    old_owner["ips"] = [{"ip": IP_B, "name": None, "lastSeen": 1700000000}]
    new_owner = _device("B", OLD)
    new_owner["ips"] = [{"ip": IP_B, "name": None, "lastSeen": 1700009999}]
    harness.make_entry(**OPTION)
    harness.devices = [old_owner, new_owner]
    await harness.setup()
    harness.queries[IP_B] = harness.next_cycle - 2

    await harness.fire(STEP)

    assert harness.state("B") == STATE_HOME
    assert harness.state("A") == STATE_NOT_HOME


async def test_a_tied_address_gives_no_arrival(harness: PresenceHarness) -> None:
    """When two devices claim an address with the same last seen, nobody arrives."""
    first = _device("A", OLD)
    second = _device("B", OLD)
    first["ips"] = [{"ip": IP_B, "name": None, "lastSeen": 1700000100}]
    second["ips"] = [{"ip": IP_B, "name": None, "lastSeen": 1700000100}]
    harness.make_entry(**OPTION)
    harness.devices = [first, second]
    await harness.setup()
    harness.queries[IP_B] = harness.next_cycle - 2

    await harness.fire(STEP)

    assert harness.state("A") == STATE_NOT_HOME
    assert harness.state("B") == STATE_NOT_HOME


async def test_the_table_of_the_last_live_refresh_is_used(harness: PresenceHarness) -> None:
    """An address changed by a live refresh is attributed from the next presence cycle, without a request for the table."""
    harness.make_entry(**OPTION)
    harness.devices = [_device("B", OLD)]
    await harness.setup()
    harness.queries["192.168.10.99"] = harness.next_cycle - 2
    await harness.fire(STEP)
    assert harness.state("B") == STATE_NOT_HOME

    renumbered = _device("B", OLD)
    renumbered["ips"] = [{"ip": "192.168.10.99", "name": None, "lastSeen": 1700000100}]
    harness.devices = [renumbered]
    await harness.refresh()
    await harness.fire(STEP)

    assert harness.state("B") == STATE_HOME


# --------------------------------------------------------------------------------------------------
# State writes
# --------------------------------------------------------------------------------------------------


async def test_presence_cycles_write_the_state_only_when_it_changes(harness: PresenceHarness) -> None:
    """A cycle that changes nothing writes nothing: one write for the arrival, none afterwards."""
    # A long away delay, so that no table entry ages into an away verdict while the clock moves.
    harness.make_entry(**OPTION, **{CONF_DEVICE_TRACKER_CONSIDER_HOME: 3600})
    harness.devices = [_device("A", FRESH), _device("B", 5000), _device("C", 5000)]
    await harness.setup()

    with harness.watch_writes() as written:
        await harness.cycles(2)
        assert written == []

        harness.seen("B", 1, at=dt_util.utcnow().timestamp() + STEP)
        await harness.fire(STEP)
        assert written == [harness.entity_id("B")]

        for _ in range(3):
            harness.seen("B", 1, at=dt_util.utcnow().timestamp() + STEP)
            await harness.fire(STEP)

    assert written == [harness.entity_id("B")]
    assert harness.presence.data is not None
    assert len(harness.since) == 6


async def test_a_live_refresh_still_writes_every_state(harness: PresenceHarness) -> None:
    """The live refresh keeps writing the state of each tracker, as before, and tells the presence handler what is shown."""
    harness.make_entry(**OPTION)
    harness.devices = [_device("A", FRESH), _device("B", OLD)]
    await harness.setup()
    harness.seen("B", 1, at=dt_util.utcnow().timestamp() + STEP)
    await harness.fire(STEP)
    assert harness.state("B") == STATE_HOME

    with harness.watch_writes() as written:
        harness.devices = [_device("A", FRESH, at=NOW + timedelta(seconds=STEP)), _device("B", OLD)]
        await harness.refresh()
        assert sorted(written) == sorted([harness.entity_id("A"), harness.entity_id("B")])
        written.clear()

        await harness.fire(STEP)

    assert written == []
    assert harness.state("B") == STATE_HOME


# --------------------------------------------------------------------------------------------------
# Failures: the table takes over
# --------------------------------------------------------------------------------------------------


def _error(kind: type[PiHoleV6Error], retry_after: float | None = None) -> PiHoleV6Error:
    """Build an error of the client, with the delay of a Retry-After header when given."""
    error = DataStructureError("get_query_activity") if kind is DataStructureError else kind()
    if retry_after is not None:
        error.retry_after = retry_after  # type: ignore[attr-defined]
    return error


@pytest.mark.parametrize(
    ("kind", "retry_after", "delay"),
    [
        (ForbiddenError, None, 600),
        (NotFoundError, None, 600),
        (BadRequestError, None, 600),
        (MethodNotAllowedError, None, 600),
        (QueryLogUnavailableError, None, 600),
        (DataStructureError, None, 600),
        (TooManyRequestsError, None, 60),
        (TooManyRequestsError, 90.0, 90),
        (ServiceUnavailableError, None, 60),
        (ServiceUnavailableError, 200.0, 200),
        (UnauthorizedError, None, 600),
        (CertificateError, None, 600),
        (CertificateChangedError, None, 600),
        (ClientConnectorError, None, PRESENCE),
        (ServerError, None, PRESENCE),
    ],
    ids=lambda value: value.__name__ if isinstance(value, type) else str(value),
)
async def test_a_failing_query_log_falls_back_and_retries_after_its_delay(
    harness: PresenceHarness, kind: type[PiHoleV6Error], retry_after: float | None, delay: int
) -> None:
    """Whatever the failure, the entry stays loaded and the trackers keep the verdict of the table; the next try is dated."""
    harness.make_entry(**OPTION)
    harness.devices = [_device("A", FRESH), _device("B", OLD)]
    entry = await harness.setup()
    harness.seen("B", 1, at=harness.next_cycle)
    harness.error = _error(kind, retry_after)

    await harness.fire(STEP)

    assert entry.state is ConfigEntryState.LOADED
    assert len(harness.since) == 1
    assert harness.presence.last_update_success is False
    assert harness.presence.last_read_error == kind.__name__
    assert kind.__name__ in str(harness.presence.last_exception)
    assert [harness.state("A"), harness.state("B")] == [STATE_HOME, STATE_NOT_HOME]

    await harness.fire(delay - 3)
    assert len(harness.since) == 1

    await harness.fire(6)
    assert len(harness.since) == 2
    assert entry.state is ConfigEntryState.LOADED


async def test_the_failure_is_a_plain_failure_for_the_live_coordinator_and_the_entities(
    harness: PresenceHarness,
) -> None:
    """A failing query log does not make the trackers unavailable nor touch the live coordinator."""
    harness.make_entry(**OPTION)
    harness.devices = [_device("A", FRESH), _device("B", OLD)]
    entry = await harness.setup()
    harness.error = ForbiddenError()

    await harness.fire(STEP)

    assert entry.runtime_data.coordinator.last_update_success is True
    assert harness.state("A") == STATE_HOME
    assert harness.state("B") == STATE_NOT_HOME


async def test_after_a_failure_the_live_cycle_applies_the_table(harness: PresenceHarness) -> None:
    """While the query log fails, the next live refresh recomputes every state from the table."""
    harness.make_entry(**OPTION)
    harness.devices = [_device("B", OLD)]
    await harness.setup()
    harness.error = ForbiddenError()
    await harness.fire(STEP)
    harness.devices = [_device("B", 5, at=NOW + timedelta(seconds=STEP))]

    await harness.refresh()

    assert harness.state("B") == STATE_HOME


async def test_recovery_after_a_failure_brings_the_arrival_back(harness: PresenceHarness) -> None:
    """When the query log answers again, the arrival is seen at the first successful cycle."""
    harness.make_entry(**OPTION)
    harness.devices = [_device("B", OLD)]
    await harness.setup()
    harness.error = ServiceUnavailableError()
    await harness.fire(STEP)
    harness.error = None
    harness.queries[IP_B] = dt_util.utcnow().timestamp() + 63 - 20
    assert harness.state("B") == STATE_NOT_HOME

    await harness.fire(60 + 3)

    assert harness.presence.last_update_success is True
    assert harness.presence.last_read_error is None
    assert harness.state("B") == STATE_HOME


@pytest.mark.parametrize("kind", [UnauthorizedError, CertificateError, CertificateChangedError])
async def test_authentication_and_certificate_errors_never_start_a_reauthentication(
    harness: PresenceHarness, kind: type[PiHoleV6Error]
) -> None:
    """The presence coordinator fails plainly: the reauthentication is the business of the live coordinator."""
    harness.make_entry(**OPTION)
    harness.devices = [_device("B", OLD)]
    entry = await harness.setup()
    harness.error = _error(kind)

    with patch.object(MockConfigEntry, "async_start_reauth") as start_reauth:
        await harness.cycles(3)

    start_reauth.assert_not_called()
    assert harness.hass.config_entries.flow.async_progress_by_handler(DOMAIN) == []
    assert entry.state is ConfigEntryState.LOADED
    assert isinstance(harness.presence.last_exception, UpdateFailed)
    assert harness.presence.last_read_error == kind.__name__


async def test_the_session_is_always_ended_and_serialized(harness: PresenceHarness) -> None:
    """Each read holds the lock shared with the other coordinators, and ends with a logout, success or not."""
    harness.make_entry(**OPTION)
    harness.devices = [_device("B", OLD)]
    await harness.setup()
    before = harness.logouts

    await harness.fire(STEP)
    assert harness.logouts == before + 1

    harness.error = ClientConnectorError("down")
    await harness.fire(STEP)

    assert harness.logouts == before + 2
    assert harness.lock_held == [True, True]
    assert harness.presence._refresh_lock.locked() is False  # pylint: disable=protected-access


async def test_a_failing_logout_does_not_hide_the_outcome(harness: PresenceHarness) -> None:
    """The logout may fail, after a read that succeeded and after one that failed: the outcome is the one of the read."""
    harness.make_entry(**OPTION)
    harness.devices = [_device("B", OLD)]
    await harness.setup()
    harness.logout_error = ClientConnectorError("down")
    harness.queries[IP_B] = harness.next_cycle - 1

    await harness.fire(STEP)

    assert harness.presence.last_update_success is True
    assert harness.state("B") == STATE_HOME

    harness.error = ForbiddenError()
    await harness.fire(STEP)

    assert harness.presence.last_update_success is False
    assert harness.presence.last_read_error == "ForbiddenError"


# --------------------------------------------------------------------------------------------------
# The window after a failure
# --------------------------------------------------------------------------------------------------


async def test_the_window_does_not_move_during_a_short_failure(harness: PresenceHarness) -> None:
    """A failure moves nothing: the next read starts from the same time, so nothing is missed."""
    harness.make_entry(**OPTION)
    harness.devices = [_device("B", OLD)]
    await harness.setup()
    harness.seen("B", 2)
    newest = harness.queries[IP_B]
    await harness.fire(STEP)

    harness.error = ClientConnectorError("down")
    await harness.cycles(2)
    harness.error = None
    await harness.fire(STEP)

    assert harness.since[1:] == [pytest.approx(newest - 5)] * 3


async def test_after_a_long_failure_the_window_restarts_at_the_floor(harness: PresenceHarness) -> None:
    """After an outage longer than the window, the read starts at now minus the window, not at the old newest query."""
    harness.make_entry(**OPTION)
    harness.devices = [_device("B", OLD)]
    await harness.setup()
    harness.seen("B", 2)
    await harness.fire(STEP)
    first_floor = harness.since[0]
    harness.error = ForbiddenError()
    await harness.fire(STEP)
    harness.error = None

    await harness.fire(620)

    assert harness.since[1] < harness.since[2]
    assert harness.since[2] == pytest.approx(dt_util.utcnow().timestamp() - 240)
    assert harness.since[2] > first_floor
    assert harness.presence.last_update_success is True


async def test_old_addresses_are_forgotten_after_the_away_delay_and_a_margin(harness: PresenceHarness) -> None:
    """An address silent for the away delay plus five minutes leaves the state kept in memory."""
    harness.make_entry(**OPTION)
    harness.devices = [_device("B", OLD)]
    await harness.setup()
    harness.queries[IP_B] = harness.t0 + 10
    harness.queries["10.9.9.9"] = harness.t0 + 10
    await harness.fire(STEP)
    assert harness.presence.data.clients_seen == 2
    assert harness.presence.data.clients_matched == 1

    await harness.fire(500)
    assert harness.presence.data.clients_seen == 2

    await harness.fire(100)

    assert harness.presence.data.clients_seen == 0
    assert harness.presence.data.clients_matched == 0
    assert harness.presence.data.last_seen_by_mac == {}


async def test_snapshot_holds_the_statistics_of_the_read(harness: PresenceHarness) -> None:
    """The snapshot keeps counters and the time of the read, and the incomplete flag of the client."""
    harness.make_entry(**OPTION)
    harness.devices = [_device("A", FRESH), _device("B", OLD)]
    await harness.setup()
    harness.seen("B", 1, at=harness.next_cycle)
    harness.seen("A", 1, at=harness.next_cycle)
    harness.queries["10.9.9.9"] = harness.next_cycle - 1
    harness.complete = False

    await harness.fire(STEP)

    snapshot = harness.presence.data
    assert snapshot.complete is False
    assert (snapshot.pages, snapshot.queries_read) == (1, 3)
    assert (snapshot.clients_seen, snapshot.clients_matched) == (3, 2)
    assert snapshot.duration == 0.25
    assert snapshot.fetched_at == dt_util.utcnow()
    assert set(snapshot.last_seen_by_mac) == {_mac("A"), _mac("B")}


# --------------------------------------------------------------------------------------------------
# Entities and registries: the presence creates and removes nothing
# --------------------------------------------------------------------------------------------------


async def test_an_unknown_client_changes_nothing_and_creates_nothing(harness: PresenceHarness) -> None:
    """A query from an address that is not in the network table gives no entity and no state change."""
    harness.make_entry(**OPTION)
    harness.devices = [_device("B", OLD)]
    await harness.setup()
    entity_registry = er.async_get(harness.hass)
    entities = len(er.async_entries_for_config_entry(entity_registry, harness.entry.entry_id))  # type: ignore[union-attr]
    devices = len(dr.async_entries_for_config_entry(dr.async_get(harness.hass), harness.entry.entry_id))  # type: ignore[union-attr]
    harness.queries["10.9.9.9"] = harness.next_cycle - 1
    harness.queries["fe80::dead"] = harness.next_cycle - 1

    with harness.watch_writes() as written:
        await harness.cycles(3)

    assert written == []
    assert harness.state("B") == STATE_NOT_HOME
    assert len(er.async_entries_for_config_entry(entity_registry, harness.entry.entry_id)) == entities  # type: ignore[union-attr]
    assert len(dr.async_entries_for_config_entry(dr.async_get(harness.hass), harness.entry.entry_id)) == devices  # type: ignore[union-attr]
    assert harness.presence.data.clients_seen == 2
    assert harness.presence.data.clients_matched == 0


async def test_a_device_excluded_by_the_whitelist_gets_no_entity_though_it_queries(harness: PresenceHarness) -> None:
    """The creation stays based on the network table and its filters: a query does not bring an excluded device in."""
    harness.make_entry(**OPTION, **{CONF_DEVICE_TRACKER_WHITELIST: True, CONF_DEVICE_TRACKER_MAC_LIST: _mac("A")})
    harness.devices = [_device("A", OLD), _device("B", OLD)]
    await harness.setup()
    harness.seen("A", 1, at=harness.next_cycle)
    harness.seen("B", 1, at=harness.next_cycle)

    await harness.cycles(2)

    assert harness.state("A") == STATE_HOME
    assert harness.entity_id("B") is None
    assert not harness.has_device("B")


async def test_a_stale_device_gets_no_entity_though_it_queries(harness: PresenceHarness) -> None:
    """A stale device without entity is not created from the query log, only from the table."""
    harness.make_entry(**OPTION, **{CONF_DEVICE_TRACKER_STALE_DAYS: 30})
    harness.devices = [_device("D", STALE), _device("E", FRESH)]
    await harness.setup()
    harness.seen("D", 1, at=harness.next_cycle)

    await harness.cycles(2)
    await harness.refresh()

    assert harness.entity_id("D") is None
    assert not harness.has_device("D")
    assert harness.state("E") == STATE_HOME


async def test_the_presence_removes_nothing(harness: PresenceHarness) -> None:
    """With the registries filled, successful and failing presence cycles remove no entity and no device."""
    harness.make_entry(**OPTION)
    for label in "ABC":
        harness.prefill(label)
    harness.devices = [_device("A", FRESH), _device("B", OLD)]
    await harness.setup()
    harness.seen("B", 1, at=harness.next_cycle)

    with (
        patch.object(PiHoleV6DeviceTracker, "async_remove", AsyncMock()) as remove_entity,
        patch.object(er.EntityRegistry, "async_remove") as remove_registry_entity,
        patch.object(dr.DeviceRegistry, "async_remove_device") as remove_device,
    ):
        await harness.cycles(2)
        harness.error = ForbiddenError()
        await harness.cycles(2)
        harness.error = None
        harness.queries.clear()
        await harness.fire(700)

    remove_entity.assert_not_called()
    remove_registry_entity.assert_not_called()
    remove_device.assert_not_called()
    for label in "ABC":
        assert harness.entity_id(label) is not None
        assert harness.has_device(label)


# --------------------------------------------------------------------------------------------------
# Availability
# --------------------------------------------------------------------------------------------------


async def test_availability_is_the_one_of_the_live_coordinator(harness: PresenceHarness) -> None:
    """A tracker is unavailable when the live refresh fails, even if the presence answers; and back with the live one."""
    harness.make_entry(**OPTION)
    harness.devices = [_device("B", OLD)]
    await harness.setup()
    harness.failing = True
    await harness.refresh()
    assert harness.state("B") == STATE_UNAVAILABLE

    harness.queries[IP_B] = harness.next_cycle - 1
    await harness.fire(STEP)

    assert harness.presence.last_update_success is True
    assert harness.state("B") == STATE_UNAVAILABLE

    harness.failing = False
    harness.devices = [_device("B", OLD)]
    await harness.refresh()

    assert harness.state("B") == STATE_HOME


async def test_a_presence_failure_does_not_make_a_tracker_unavailable(harness: PresenceHarness) -> None:
    """The availability does not read the presence coordinator at all."""
    harness.make_entry(**OPTION)
    harness.devices = [_device("A", FRESH)]
    await harness.setup()
    harness.error = ForbiddenError()

    await harness.fire(STEP)

    assert harness.presence.last_update_success is False
    assert harness.state("A") == STATE_HOME


# --------------------------------------------------------------------------------------------------
# Lifecycle
# --------------------------------------------------------------------------------------------------


async def test_unload_stops_the_presence_cycles_and_a_new_setup_starts_them_again(harness: PresenceHarness) -> None:
    """After the unload no cycle remains: no read, no listener. A new setup starts over, with its own first read."""
    harness.make_entry(**OPTION)
    harness.devices = [_device("B", OLD)]
    entry = await harness.setup()
    await harness.fire(STEP)
    assert len(harness.since) == 1
    old = harness.presence

    with harness.fetches():
        assert await harness.hass.config_entries.async_unload(entry.entry_id)
        await harness.hass.async_block_till_done()
    await harness.cycles(5)

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert len(harness.since) == 1
    assert old.listening is False

    harness.queries[IP_B] = dt_util.utcnow().timestamp() + 20
    await harness.setup()
    assert len(harness.since) == 1
    assert harness.presence is not old
    await harness.fire(STEP)

    assert len(harness.since) == 2
    assert harness.state("B") == STATE_HOME


async def test_reload_leaves_one_presence_cycle(harness: PresenceHarness) -> None:
    """A reload replaces the coordinator: one read per interval afterwards, not two."""
    harness.make_entry(**OPTION)
    harness.devices = [_device("B", OLD)]
    entry = await harness.setup()
    old = harness.presence

    with harness.fetches():
        await harness.hass.config_entries.async_reload(entry.entry_id)
        await harness.hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    harness.since.clear()
    await harness.cycles(3)

    assert harness.presence is not old
    assert old.listening is False
    assert len(harness.since) == 3


async def test_polling_disabled_by_the_user_suspends_the_presence(harness: PresenceHarness) -> None:
    """With "Enable polling for changes" off, the presence coordinator is never scheduled."""
    entry = harness.make_entry(**OPTION)
    harness.hass.config_entries.async_update_entry(entry, pref_disable_polling=True)
    harness.devices = [_device("B", OLD)]
    harness.seen("B", 1, at=harness.next_cycle)
    await harness.setup()

    await harness.cycles(6)

    assert harness.since == []
    assert harness.state("B") == STATE_NOT_HOME
    assert harness.presence.listening is True


async def test_the_refresh_data_button_does_not_refresh_the_presence(harness: PresenceHarness) -> None:
    """The button refreshes the live and stats coordinators only: the presence one runs by itself."""
    harness.platforms = [Platform.DEVICE_TRACKER, Platform.BUTTON]
    harness.make_entry(**OPTION)
    harness.devices = [_device("B", OLD)]
    entry = await harness.setup()
    entity_id = er.async_get(harness.hass).async_get_entity_id(
        Platform.BUTTON, DOMAIN, f"{entry.entry_id}/action_refresh_data"
    )
    assert entity_id is not None
    calls = harness.live_calls

    with (
        harness.fetches(),
        patch.object(Api, "call_blocking_status", AsyncMock(return_value={"code": 200})),
    ):
        await harness.hass.services.async_call("button", "press", {"entity_id": entity_id}, blocking=True)
        await harness.hass.async_block_till_done()

    assert harness.since == []
    assert harness.live_calls > calls


# --------------------------------------------------------------------------------------------------
# The tracker entity on its own
# --------------------------------------------------------------------------------------------------


def _entity(
    *, table_age: int | None, log_age: float | None, presence: bool = True, snapshot: bool = True
) -> tuple[PiHoleV6DeviceTracker, Any]:
    """Build a tracker on stand-in coordinators: a table row aged `table_age`, a query log entry aged `log_age`."""
    now = datetime.now(UTC).timestamp()
    coordinator = MagicMock()
    coordinator.name = "Pihole"
    coordinator.config_entry.data = {CONF_DEVICE_TRACKER_CONSIDER_HOME: 120}
    device = _device("B", None)
    if table_age is not None:
        device["lastQuery"] = int(now) - table_age
    api = MagicMock()
    api.cache_network_devices = [device]
    source = None
    if presence:
        source = MagicMock()
        source.data = (
            SimpleNamespace(last_seen_by_mac={} if log_age is None else {device["hwaddr"].lower(): now - log_age})
            if snapshot
            else None
        )
    return PiHoleV6DeviceTracker(api, coordinator, "server", device, source), source


@pytest.mark.parametrize(
    ("table_age", "log_age", "expected"),
    [
        (None, None, False),
        (500, None, False),
        (50, None, True),
        (None, 50, True),
        (None, 500, False),
        (500, 50, True),
        (50, 500, True),
        (500, 500, False),
        (50, 30, True),
    ],
    ids=repr,
)
def test_connection_is_the_newest_of_both_sources(table_age: int | None, log_age: float | None, expected: bool) -> None:
    """The device is home when the newest of its two last activities is within the away delay."""
    entity, _ = _entity(table_age=table_age, log_age=log_age)

    assert entity.is_connected is expected


@pytest.mark.parametrize(("presence", "snapshot"), [(False, True), (True, False)], ids=["no-presence", "no-snapshot"])
def test_without_presence_data_only_the_table_counts(presence: bool, snapshot: bool) -> None:
    """With no presence coordinator, or one that has not read yet, the table alone decides, as before."""
    assert _entity(table_age=50, log_age=10, presence=presence, snapshot=snapshot)[0].is_connected is True
    assert _entity(table_age=500, log_age=10, presence=presence, snapshot=snapshot)[0].is_connected is False
    assert _entity(table_age=None, log_age=10, presence=presence, snapshot=snapshot)[0].is_connected is False


def test_a_device_gone_from_the_table_is_away_even_if_the_log_knows_it() -> None:
    """The log never makes up a device: without a row in the table the tracker is away."""
    entity, _ = _entity(table_age=None, log_age=1)
    entity.api.cache_network_devices = []

    assert entity.is_connected is False


def test_presence_handler_writes_only_on_a_change() -> None:
    """The handler compares the new verdict with the last one written, and writes when they differ."""
    entity, source = _entity(table_age=500, log_age=None)
    entity.async_write_ha_state = MagicMock()  # type: ignore[method-assign]
    entity._reported_connected = False  # pylint: disable=protected-access

    entity._handle_presence_update()  # pylint: disable=protected-access
    entity.async_write_ha_state.assert_not_called()

    source.data = SimpleNamespace(last_seen_by_mac={entity._mac: datetime.now(UTC).timestamp() - 5})  # pylint: disable=protected-access
    entity._handle_presence_update()  # pylint: disable=protected-access
    entity._handle_presence_update()  # pylint: disable=protected-access

    entity.async_write_ha_state.assert_called_once_with()
    assert entity._reported_connected is True  # pylint: disable=protected-access


# --------------------------------------------------------------------------------------------------
# Review corrections: future times, incomplete reads, a logout that hangs, authentication errors
# --------------------------------------------------------------------------------------------------

YEAR_2100 = 4102444800.0


async def test_a_query_dated_far_in_the_future_changes_nothing(harness: PresenceHarness) -> None:
    """A line of the year 2100 neither makes a device home, nor moves the window into the future."""
    harness.make_entry(**OPTION)
    harness.devices = [_device("A", OLD), _device("B", OLD)]
    await harness.setup()
    harness.queries[IP_A] = YEAR_2100
    harness.seen("B", 2, at=harness.next_cycle)

    await harness.fire(STEP)

    now = dt_util.utcnow().timestamp()
    assert harness.state("A") == STATE_NOT_HOME
    assert harness.state("B") == STATE_HOME
    assert harness.presence._since <= now  # pylint: disable=protected-access
    assert harness.presence.data.clients_seen == 1

    await harness.cycles(3)

    assert all(since <= now + 3 * STEP for since in harness.since)
    assert harness.state("A") == STATE_NOT_HOME


async def test_a_future_only_log_leaves_the_window_alone(harness: PresenceHarness) -> None:
    """When every line is in the future there is no usable time: the window stays on the floor."""
    harness.make_entry(**OPTION)
    harness.devices = [_device("A", OLD)]
    await harness.setup()
    harness.queries[IP_A] = YEAR_2100

    await harness.cycles(3)

    assert harness.presence._since is None  # pylint: disable=protected-access
    assert harness.presence.data.clients_seen == 0
    assert harness.state("A") == STATE_NOT_HOME


@pytest.mark.parametrize(("lead", "home"), [(3, True), (4.5, True), (6, False), (60, False)])
async def test_a_pihole_clock_a_little_ahead_stays_correct(harness: PresenceHarness, lead: float, home: bool) -> None:
    """Up to five seconds ahead, a query counts (as at most now); beyond, it is ignored."""
    harness.make_entry(**OPTION)
    harness.devices = [_device("B", OLD)]
    await harness.setup()
    harness.queries[IP_B] = harness.next_cycle + lead

    await harness.fire(STEP)

    assert (harness.state("B") == STATE_HOME) is home
    if home:
        assert harness.presence.data.last_seen_by_mac[_mac("B")] <= dt_util.utcnow().timestamp()
        assert harness.presence._since <= dt_util.utcnow().timestamp()  # pylint: disable=protected-access


async def test_a_future_line_does_not_keep_a_device_home_past_the_delay(harness: PresenceHarness) -> None:
    """A device whose only 'query' is a bounded future time leaves at the away delay plus one cycle, not later."""
    harness.make_entry(**OPTION)
    harness.devices = [_device("B", OLD)]
    await harness.setup()
    harness.queries[IP_B] = harness.t0 + 20 + 4  # Four seconds ahead of the first cycle: accepted as "now".

    await harness.fire(STEP)
    assert harness.state("B") == STATE_HOME
    for _ in range(9):
        await harness.fire(STEP)

    assert harness.state("B") == STATE_NOT_HOME


async def test_an_incomplete_read_is_read_again(harness: PresenceHarness) -> None:
    """After an incomplete read the window does not advance; a complete read moves it."""
    harness.make_entry(**OPTION)
    harness.devices = [_device("B", OLD)]
    await harness.setup()
    harness.seen("B", 2, at=harness.next_cycle)
    newest = harness.queries[IP_B]
    harness.complete = False

    await harness.cycles(2)

    assert harness.presence._since is None  # pylint: disable=protected-access
    now = dt_util.utcnow().timestamp()
    assert harness.since[1] == pytest.approx(now - 240)
    assert harness.state("B") == STATE_HOME
    assert harness.presence.data.complete is False

    harness.complete = True
    await harness.cycles(2)

    assert harness.since[2] == pytest.approx(now + STEP - 240)
    assert harness.since[3] == pytest.approx(newest - 5)
    assert harness.presence.data.complete is True


async def test_a_logout_that_hangs_does_not_hold_the_lock(harness: PresenceHarness) -> None:
    """The logout is bounded: the cycle ends, nothing is raised, and the live coordinator can take the lock."""
    harness.make_entry(**OPTION)
    harness.devices = [_device("B", OLD)]
    await harness.setup()
    harness.queries[IP_B] = harness.next_cycle - 2
    harness.logout_hangs = True

    await harness.fire(STEP)
    # The cycle waits for the logout: moving the clock past its timeout of five seconds ends the wait.
    assert harness.presence._refresh_lock.locked() is True  # pylint: disable=protected-access
    await harness.fire(6)

    assert harness.presence.last_update_success is True
    assert harness.state("B") == STATE_HOME
    assert harness.presence._refresh_lock.locked() is False  # pylint: disable=protected-access

    harness.logout_hangs = False
    calls = harness.live_calls
    await harness.refresh()

    assert harness.live_calls == calls + 1


async def test_a_logout_that_hangs_after_a_failed_read_keeps_the_failure(harness: PresenceHarness) -> None:
    """The error of the read is still the outcome when the logout times out too."""
    harness.make_entry(**OPTION)
    harness.devices = [_device("B", OLD)]
    await harness.setup()
    harness.error = ForbiddenError()
    harness.logout_hangs = True

    await harness.fire(STEP)
    # The cycle waits for the logout: moving the clock past its timeout of five seconds ends the wait.
    assert harness.presence._refresh_lock.locked() is True  # pylint: disable=protected-access
    await harness.fire(6)

    assert harness.presence.last_read_error == "ForbiddenError"
    assert harness.presence._refresh_lock.locked() is False  # pylint: disable=protected-access


@pytest.mark.parametrize("kind", [UnauthorizedError, CertificateError, CertificateChangedError])
async def test_authentication_errors_do_not_log_in_again_every_cycle(
    harness: PresenceHarness, kind: type[PiHoleV6Error]
) -> None:
    """A refused login is retried after ten minutes, not at each presence interval."""
    harness.make_entry(**OPTION)
    harness.devices = [_device("B", OLD)]
    await harness.setup()
    harness.error = _error(kind)

    await harness.fire(STEP)
    await harness.cycles(15)

    assert len(harness.since) == 1
    await harness.fire(300)
    assert len(harness.since) == 2
