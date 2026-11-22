"""Presence coordinator: detect the arrival of a network device faster, from the query log of the Pi-hole.

The coordinator reads GET /queries at its own frequency and keeps, for each tracked device, the time of
its latest query. Nothing else is kept: the queried domains are never stored, logged or reported.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import logging
from typing import TYPE_CHECKING, Any, cast

from homeassistant.const import CONF_NAME
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import normalize_ip
from .const import (
    CONF_UPDATE_INTERVAL_PRESENCE,
    DEFAULT_UPDATE_INTERVAL_PRESENCE,
    PRESENCE_FUTURE_TOLERANCE,
    PRESENCE_LOGOUT_TIMEOUT,
    PRESENCE_MAX_WINDOW,
    PRESENCE_OVERLAP,
    PRESENCE_RETENTION_MARGIN,
    PRESENCE_RETRY_AFTER_AUTH,
    PRESENCE_RETRY_AFTER_BUSY,
    PRESENCE_RETRY_AFTER_UNUSABLE,
)
from .exceptions import (
    BadRequestError,
    CertificateChangedError,
    CertificateError,
    DataStructureError,
    ForbiddenError,
    MethodNotAllowedError,
    NotFoundError,
    PiHoleV6Error,
    QueryLogUnavailableError,
    ServiceUnavailableError,
    TooManyRequestsError,
    UnauthorizedError,
)
from .helper import get_consider_home

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from homeassistant.core import HomeAssistant

    from . import PiHoleV6ConfigEntry
    from .api import Api as PiholeAPI

_LOGGER = logging.getLogger(__name__)

# The errors that mean the query log cannot be used as it is (rights, old version, privacy level): the next try is far away.
_UNUSABLE_ERRORS: tuple[type[PiHoleV6Error], ...] = (
    ForbiddenError,
    NotFoundError,
    BadRequestError,
    MethodNotAllowedError,
    QueryLogUnavailableError,
    DataStructureError,
)
# The errors that mean the Pi-hole is busy: the next try is soon, or when Pi-hole says so.
_BUSY_ERRORS: tuple[type[PiHoleV6Error], ...] = (TooManyRequestsError, ServiceUnavailableError)
# The session is refused: the next try is far away, so a wrong password is not sent every cycle.
# The reauthentication is never started from here: the live coordinator sees the same cause and does it.
_AUTH_ERRORS: tuple[type[PiHoleV6Error], ...] = (UnauthorizedError, CertificateError, CertificateChangedError)


@dataclass(frozen=True, slots=True)
class PresenceSnapshot:  # pylint: disable=too-many-instance-attributes
    """Data of the presence coordinator: the newest query time of each tracked MAC, and statistics of the read (counts only).

    Attributes:
        last_seen_by_mac (Mapping[str, float]): Lowercase hwaddr (pseudo-MAC "ip-..." included) -> Pi-hole Unix time of its newest query.
        fetched_at (datetime): The Home Assistant time at the end of the read.
        complete (bool): False when the last read stopped at the page limit or the time budget.
        pages (int): The number of pages of the last read.
        queries_read (int): The number of rows of the last read.
        clients_seen (int): The number of distinct client addresses in the state kept in memory.
        clients_matched (int): The number of those addresses attributed to a row of the network table.
        duration (float): The duration of the last read in seconds, the login included.

    """

    last_seen_by_mac: Mapping[str, float]
    fetched_at: datetime
    complete: bool
    pages: int
    queries_read: int
    clients_seen: int
    clients_matched: int
    duration: float


def get_presence_interval(entry: PiHoleV6ConfigEntry) -> timedelta | None:
    """Read the refresh interval of the presence coordinator from the config entry.

    Args:
        entry (PiHoleV6ConfigEntry): The config entry holding the options.

    Returns:
        timedelta | None: The interval, None when the presence refresh is disabled (0, absent or unreadable).

    """
    value: Any = entry.data.get(CONF_UPDATE_INTERVAL_PRESENCE, DEFAULT_UPDATE_INTERVAL_PRESENCE)

    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        return None

    return timedelta(seconds=value)


def build_ip_owners(devices: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    """Tell which network device owns each IP address of the network table.

    An address listed by several rows belongs to the row whose `lastSeen` for that address is the highest.
    On an exact tie the address is dropped: better no gain than a false arrival.

    Args:
        devices (Iterable[Mapping[str, Any]]): The rows of GET /network/devices.

    Returns:
        dict[str, str]: Normalized IP address -> lowercase hwaddr of its owner.

    """
    best: dict[str, tuple[float, str]] = {}
    ambiguous: set[str] = set()

    for device in devices:
        hwaddr: Any = device.get("hwaddr")
        addresses: Any = device.get("ips")

        if not isinstance(hwaddr, str) or not isinstance(addresses, list):
            continue

        mac: str = hwaddr.lower()

        for raw_info in cast("list[Any]", addresses):
            if not isinstance(raw_info, dict):
                continue

            info: dict[str, Any] = cast("dict[str, Any]", raw_info)
            address: str | None = normalize_ip(info.get("ip"))
            if address is None:
                continue

            seen: Any = info.get("lastSeen")
            last_seen: float = float(seen) if isinstance(seen, (int, float)) and not isinstance(seen, bool) else 0.0

            current: tuple[float, str] | None = best.get(address)

            if current is None or last_seen > current[0]:
                best[address] = (last_seen, mac)
                ambiguous.discard(address)
            elif last_seen == current[0] and mac != current[1]:
                ambiguous.add(address)

    return {address: mac for address, (_, mac) in best.items() if address not in ambiguous}


def map_activity_to_devices(
    last_seen_by_ip: Mapping[str, float], devices: Iterable[Mapping[str, Any]]
) -> tuple[dict[str, float], int]:
    """Attribute the newest query time of each client address to a network device.

    A client address that is not in the network table is ignored: no entity is ever created from a query.

    Args:
        last_seen_by_ip (Mapping[str, float]): Normalized client IP address -> newest query time.
        devices (Iterable[Mapping[str, Any]]): The rows of GET /network/devices.

    Returns:
        tuple[dict[str, float], int]: The newest query time per lowercase hwaddr, and the number of addresses attributed.

    """
    owners: dict[str, str] = build_ip_owners(devices)
    last_seen_by_mac: dict[str, float] = {}
    matched: int = 0

    for address, moment in last_seen_by_ip.items():
        mac: str | None = owners.get(address)
        if mac is None:
            continue

        matched += 1
        if moment > last_seen_by_mac.get(mac, 0.0):
            last_seen_by_mac[mac] = moment

    return last_seen_by_mac, matched


class PiHoleV6PresenceCoordinator(DataUpdateCoordinator[PresenceSnapshot]):  # pylint: disable=too-many-instance-attributes
    """Read the query log of the Pi-hole to date the latest query of each network device.

    The coordinator only polls while at least one device tracker listens to it, and it is never refreshed at the setup: a failure of the
    query log must not prevent the integration from loading. The live coordinator stays the fallback of the trackers.

    Attributes:
        last_read_error (str | None): The class name of the exception of the last failed read, None after a successful one (for the diagnostics).
        _entry (PiHoleV6ConfigEntry): The config entry the coordinator belongs to.
        _api (PiholeAPI): The Pi-hole API client.
        _refresh_lock (asyncio.Lock): The lock shared with the other coordinators, which serializes the sessions.
        _since (float | None): The start of the next window, as a Pi-hole Unix time. None before the first read.
        _last_seen_by_ip (dict[str, float]): The newest query time of each client address, in memory only.

    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: PiHoleV6ConfigEntry,
        api: PiholeAPI,
        refresh_lock: asyncio.Lock,
        update_interval: timedelta,
    ) -> None:
        """Initialize the presence coordinator.

        Args:
            hass (HomeAssistant): The Home Assistant instance.
            entry (PiHoleV6ConfigEntry): The config entry the coordinator belongs to.
            api (PiholeAPI): The Pi-hole API client.
            refresh_lock (asyncio.Lock): The lock shared with the live and stats coordinators.
            update_interval (timedelta): The time between two reads of the query log.

        """
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{entry.data.get(CONF_NAME, 'Pi-hole')} presence",
            update_interval=update_interval,
            always_update=True,
        )
        self._entry = entry
        self._api = api
        self._refresh_lock = refresh_lock
        self._since: float | None = None
        self._last_seen_by_ip: dict[str, float] = {}
        self.last_read_error: str | None = None

    @property
    def listening(self) -> bool:
        """Tell whether at least one entity listens to the coordinator, which is what makes it poll.

        Returns:
            bool: True when a listener is registered.

        """
        return bool(self._listeners)

    async def _async_update_data(self) -> PresenceSnapshot:
        """Read the query log since the last read and attribute the clients to the network devices.

        When the query log cannot be read, the read fails with an UpdateFailed whose delay before the next try depends on the cause (see `_failure`).

        Returns:
            PresenceSnapshot: The newest query time per device, with the statistics of the read.

        """
        now: float = datetime.now(UTC).timestamp()
        away_delay: float = get_consider_home(self._entry.data)
        window: float = min(away_delay, PRESENCE_MAX_WINDOW)
        floor: float = now - window
        since: float = floor if self._since is None else max(self._since, floor)

        async with self._refresh_lock:
            try:
                activity = await self._api.call_get_query_activity(since)
            except PiHoleV6Error as err:
                self.last_read_error = type(err).__name__
                raise self._failure(err) from err
            finally:
                await self._logout()

        # A query dated in the future (beyond the clock skew) is ignored: it would keep a device home and push the window ahead.
        ceiling: float = now + PRESENCE_FUTURE_TOLERANCE
        newest_time: float | None = None

        for address, moment in activity.last_seen_by_ip.items():
            if moment > ceiling:
                continue
            moment = min(moment, now)  # noqa: PLW2901
            newest_time = moment if newest_time is None else max(newest_time, moment)
            if moment > self._last_seen_by_ip.get(address, 0.0):
                self._last_seen_by_ip[address] = moment

        # An incomplete read keeps the previous start: the window is read again, so no query is skipped.
        if activity.complete and newest_time is not None:
            self._since = min(max(self._since or 0.0, newest_time - PRESENCE_OVERLAP), now)

        # An address silent for longer than the away delay (and a margin) can no longer make a device home.
        retention: float = now - (away_delay + PRESENCE_RETENTION_MARGIN)
        self._last_seen_by_ip = {
            address: moment for address, moment in self._last_seen_by_ip.items() if moment >= retention
        }

        last_seen_by_mac, matched = map_activity_to_devices(self._last_seen_by_ip, self._api.cache_network_devices)
        self.last_read_error = None

        return PresenceSnapshot(
            last_seen_by_mac=last_seen_by_mac,
            fetched_at=datetime.now(UTC),
            complete=activity.complete,
            pages=activity.pages,
            queries_read=activity.queries_read,
            clients_seen=len(self._last_seen_by_ip),
            clients_matched=matched,
            duration=activity.duration,
        )

    async def _logout(self) -> None:
        """End the session, whatever happened: a failing logout never hides the outcome of the read."""
        try:
            async with asyncio.timeout(PRESENCE_LOGOUT_TIMEOUT):
                await self._api.call_logout()
        except PiHoleV6Error as err:
            _LOGGER.debug("Presence logout failed: %s", type(err).__name__)
        except TimeoutError:
            _LOGGER.debug("Presence logout timed out")

    @staticmethod
    def _failure(err: PiHoleV6Error) -> UpdateFailed:
        """Turn an error of the client into the UpdateFailed that sets the delay before the next try.

        An authentication or certificate error is a failure with a long delay: the reauthentication is never started from here, the live coordinator sees the same cause and does it.

        Args:
            err (PiHoleV6Error): The error raised by the client.

        Returns:
            UpdateFailed: The exception to raise. Its message holds the class name and the message of the error, never a domain.

        """
        message: str = f"Pi-hole query log unavailable: {type(err).__name__}"

        if isinstance(err, _AUTH_ERRORS):
            return UpdateFailed(message, retry_after=PRESENCE_RETRY_AFTER_AUTH)

        if isinstance(err, _UNUSABLE_ERRORS):
            return UpdateFailed(message, retry_after=PRESENCE_RETRY_AFTER_UNUSABLE)

        if isinstance(err, _BUSY_ERRORS):
            retry_after: float | None = getattr(err, "retry_after", None)
            return UpdateFailed(message, retry_after=retry_after or PRESENCE_RETRY_AFTER_BUSY)

        return UpdateFailed(f"{message} ({err})")
