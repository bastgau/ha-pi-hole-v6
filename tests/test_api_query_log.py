"""Check the reading of the query log (GET /queries) by the client: parsers, pages, errors and logs.

The session is replaced by a scripted fake one, so the real `_call` runs (timeouts, status handling, Retry-After and
logging included) without any network. The rows carry a marker domain that must never come out of the client.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
import logging
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientError
from custom_components.pi_hole_v6 import async_get_live_data
from custom_components.pi_hole_v6.api import (
    QUERY_LOG_BUDGET_SECONDS,
    QUERY_LOG_MAX_PAGES,
    QUERY_LOG_PAGE_SIZE,
    Api,
    QueryActivity,
    count_hidden_clients,
    normalize_ip,
    parse_query_activity,
    parse_retry_after,
)
from custom_components.pi_hole_v6.exceptions import (
    APIError,
    BadRequestError,
    ClientConnectorError,
    DataStructureError,
    ForbiddenError,
    NotFoundError,
    QueryLogUnavailableError,
    TooManyRequestsError,
    UnauthorizedError,
)
import pytest

API = "custom_components.pi_hole_v6.api"
BASE_URL = "https://pihole.example/api"
SINCE = 1700000000.0
MARKER = "marker-domain.tracker.example"
CLIENT_A = "192.168.10.11"
CLIENT_B = "192.168.10.12"


def _row(ip: str | None = CLIENT_A, moment: Any = SINCE + 10, **extra: Any) -> dict[str, Any]:
    """Return a row of the query log, with the marker domain and the other fields Pi-hole sends."""
    return {
        "id": 1,
        "time": moment,
        "type": "A",
        "status": "GRAVITY",
        "domain": MARKER,
        "upstream": None,
        "client": {"ip": ip, "name": MARKER},
        **extra,
    }


def _page(rows: list[dict[str, Any]], cursor: Any = 4242) -> dict[str, Any]:
    """Return the body of a page of the query log."""
    return {"queries": rows, "cursor": cursor, "recordsTotal": 10, "recordsFiltered": 10, "draw": 0}


class FakeResponse:  # pylint: disable=too-few-public-methods
    """Stand-in for an aiohttp response: status, reason, headers and a JSON body."""

    def __init__(self, status: int = 200, body: Any = None, headers: dict[str, str] | None = None) -> None:
        """Keep what the client reads."""
        self.status = status
        self.reason = "OK" if status < 400 else "Error"
        self.headers = headers or {}
        self.text = "body"
        self._body = body

    async def json(self) -> Any:
        """Return the body."""
        return self._body


class FakeSession:  # pylint: disable=too-few-public-methods
    """Session answering the GET requests from a script: a response, an exception, or a function returning one."""

    def __init__(self, *script: Any) -> None:
        """Keep the script and the requests seen."""
        self.script = list(script)
        self.urls: list[str] = []

    async def get(self, url: str, **_: Any) -> FakeResponse:
        """Answer the next scripted item."""
        self.urls.append(url)
        item = self.script.pop(0)
        if callable(item):
            item = item()
        if isinstance(item, BaseException):
            raise item
        return item


def _make_api(*script: Any) -> tuple[Api, FakeSession]:
    """Build a client on a scripted session, already logged in (no password), so only the GET requests happen."""
    session = FakeSession(*script)
    api = Api(session=session, url=BASE_URL)  # type: ignore[arg-type]
    api._sid = "no password set"  # pylint: disable=protected-access
    return api, session


# --------------------------------------------------------------------------------------------------
# Parsers
# --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("192.168.1.10", "192.168.1.10"),
        (" 192.168.1.10 ", "192.168.1.10"),
        ("FE80::1", "fe80::1"),
        ("fe80:0:0:0:0:0:0:1", "fe80::1"),
        ("FE80:0000::0001", "fe80::1"),
        ("2001:DB8::ABCD", "2001:db8::abcd"),
        ("0.0.0.0", "0.0.0.0"),  # noqa: S104
        ("::ffff:192.168.1.10", "::ffff:c0a8:10a"),
        ("", None),
        ("not-an-ip", None),
        ("192.168.1", None),
        ("192.168.1.256", None),
        (None, None),
        (12345, None),
        (["192.168.1.10"], None),
    ],
    ids=repr,
)
def test_normalize_ip(value: object, expected: str | None) -> None:
    """Two spellings of an address give the same string, and anything that is not an address gives None."""
    result = normalize_ip(value)

    if expected is not None and ":" in expected and "ffff" in expected:
        # The form of an IPv4 mapped address depends on the Python version: only require a valid, stable string.
        assert result is not None
        assert normalize_ip(result) == result
    else:
        assert result == expected


def test_parse_keeps_the_newest_time_per_client() -> None:
    """The maximum per address wins whatever the order, and every row is counted."""
    rows = [
        _row(CLIENT_A, SINCE + 5),
        _row(CLIENT_A, SINCE + 30),
        _row(CLIENT_A, SINCE + 12),
        _row(CLIENT_B, SINCE + 7),
        _row("FE80:0:0:0:0:0:0:1", SINCE + 1),
        _row("fe80::1", SINCE + 2),
    ]

    newest, count = parse_query_activity(rows)

    assert newest == {CLIENT_A: SINCE + 30, CLIENT_B: SINCE + 7, "fe80::1": SINCE + 2}
    assert count == 6


@pytest.mark.parametrize(
    "bad_row",
    [
        "a string",
        None,
        42,
        ["list"],
        {"time": SINCE + 1},
        {"time": SINCE + 1, "client": None},
        {"time": SINCE + 1, "client": "192.168.10.11"},
        {"time": SINCE + 1, "client": {}},
        {"time": SINCE + 1, "client": {"ip": ""}},
        {"time": SINCE + 1, "client": {"ip": "not-an-ip"}},
        {"time": SINCE + 1, "client": {"ip": None}},
        {"client": {"ip": CLIENT_A}},
        {"time": None, "client": {"ip": CLIENT_A}},
        {"time": True, "client": {"ip": CLIENT_A}},
        {"time": False, "client": {"ip": CLIENT_A}},
        {"time": 0, "client": {"ip": CLIENT_A}},
        {"time": -5, "client": {"ip": CLIENT_A}},
        {"time": "1700000010", "client": {"ip": CLIENT_A}},
        {"time": float("nan"), "client": {"ip": CLIENT_A}},
        {"time": float("inf"), "client": {"ip": CLIENT_A}},
    ],
    ids=repr,
)
def test_parse_skips_unusable_rows_but_counts_them(bad_row: Any) -> None:
    """A row that cannot date a client is skipped, the good ones around it are kept, and every row is read."""
    newest, count = parse_query_activity([bad_row, _row(CLIENT_B, SINCE + 3)])

    assert newest == {CLIENT_B: SINCE + 3}
    assert count == 2


@pytest.mark.parametrize("queries", [None, {}, "text", 5, {"queries": []}])
def test_parse_of_something_that_is_not_a_list(queries: object) -> None:
    """Anything but a list reads as an empty log."""
    assert parse_query_activity(queries) == ({}, 0)


def test_parse_integer_time_becomes_a_float() -> None:
    """An integer time is accepted and returned as a float."""
    newest, _ = parse_query_activity([_row(CLIENT_A, 1700000010)])

    assert newest == {CLIENT_A: 1700000010.0}
    assert isinstance(newest[CLIENT_A], float)


def test_parse_output_holds_no_domain() -> None:
    """The domain and the client name of the rows never come out of the parser."""
    result = parse_query_activity([_row(CLIENT_A), _row(CLIENT_B, SINCE + 2)])

    assert MARKER not in repr(result)
    assert MARKER not in repr(QueryActivity(result[0], SINCE, 1, result[1], complete=True, duration=0.1))


NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("30", 30.0),
        ("30.5", 30.5),
        ("0", 1.0),
        ("-4", 1.0),
        ("1", 1.0),
        ("3600", 3600.0),
        ("99999", 3600.0),
        (format_datetime(NOW + timedelta(seconds=120), usegmt=True), 120.0),
        (format_datetime(NOW + timedelta(hours=5), usegmt=True), 3600.0),
        (format_datetime(NOW - timedelta(seconds=120), usegmt=True), 1.0),
        ("Mon, 01 Jun 2026 12:02:00 -0000", 120.0),
        ("Mon, 01 Jun 2026 12:02:00", 120.0),
        ("soon", None),
        ("Tue, 99 Foo 2026 25:61:61 GMT", None),
        ("nan", None),
        ("inf", None),
    ],
    ids=repr,
)
def test_parse_retry_after(value: str | None, expected: float | None) -> None:
    """Seconds or HTTP date, clamped between 1 and 3600, None when absent or unreadable."""
    assert parse_retry_after(value, NOW) == expected


# --------------------------------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------------------------------


async def test_one_short_page_is_complete() -> None:
    """A page shorter than the page size ends the read, and the first request carries no cursor and no filter."""
    api, session = _make_api(FakeResponse(body=_page([_row(CLIENT_A, SINCE + 4), _row(CLIENT_B, SINCE + 9)])))

    result = await api.call_get_query_activity(SINCE, page_size=5)

    assert result.complete is True
    assert result.pages == 1
    assert result.queries_read == 2
    assert result.last_seen_by_ip == {CLIENT_A: SINCE + 4, CLIENT_B: SINCE + 9}
    assert result.newest_time == SINCE + 9
    assert result.duration >= 0
    assert session.urls == [f"{BASE_URL}/queries?from=1700000000.000&length=5"]
    for forbidden in ("domain", "client_ip", "client_name", "cursor", "start", "upstream"):
        assert forbidden not in session.urls[0]


async def test_empty_window_is_complete_with_no_newest_time() -> None:
    """A window without any query is a complete read, whose newest time is unknown."""
    api, _ = _make_api(FakeResponse(body=_page([])))

    result = await api.call_get_query_activity(SINCE)

    assert result.complete is True
    assert result.pages == 1
    assert result.queries_read == 0
    assert result.last_seen_by_ip == {}
    assert result.newest_time is None


async def test_rows_without_usable_client_still_count_as_read() -> None:
    """Skipped rows are counted, and leave no newest time."""
    api, _ = _make_api(FakeResponse(body=_page([{"time": SINCE + 1}, "junk"])))

    result = await api.call_get_query_activity(SINCE, page_size=5)

    assert (result.queries_read, result.newest_time, result.last_seen_by_ip) == (2, None, {})


async def test_second_page_uses_the_cursor_of_the_first_and_start() -> None:
    """A full page makes a second request with the frozen cursor and the offset, and the newest time wins across pages."""
    api, session = _make_api(
        FakeResponse(body=_page([_row(CLIENT_A, SINCE + 20), _row(CLIENT_B, SINCE + 19)], cursor=777)),
        FakeResponse(body=_page([_row(CLIENT_A, SINCE + 3), _row(CLIENT_B, SINCE + 30)], cursor=777)),
        FakeResponse(body=_page([_row("10.0.0.9", SINCE + 1)], cursor=777)),
    )

    result = await api.call_get_query_activity(SINCE, page_size=2)

    assert result.pages == 3
    assert result.complete is True
    assert result.queries_read == 5
    assert result.last_seen_by_ip == {CLIENT_A: SINCE + 20, CLIENT_B: SINCE + 30, "10.0.0.9": SINCE + 1}
    assert session.urls == [
        f"{BASE_URL}/queries?from=1700000000.000&length=2",
        f"{BASE_URL}/queries?from=1700000000.000&length=2&cursor=777&start=2",
        f"{BASE_URL}/queries?from=1700000000.000&length=2&cursor=777&start=4",
    ]


async def test_two_pages_with_the_real_page_size() -> None:
    """1000 rows then 200 make two pages, the second one starting at 1000."""
    full = [_row(CLIENT_A, SINCE + 1) for _ in range(QUERY_LOG_PAGE_SIZE)]
    api, session = _make_api(
        FakeResponse(body=_page(full, cursor=99)),
        FakeResponse(body=_page(full[:200], cursor=99)),
    )

    result = await api.call_get_query_activity(SINCE)

    assert (result.pages, result.complete, result.queries_read) == (2, True, 1200)
    assert session.urls[0].endswith("length=1000")
    assert session.urls[1].endswith("length=1000&cursor=99&start=1000")


async def test_three_full_pages_stop_the_read_as_incomplete() -> None:
    """The page limit ends the read, whatever the log still holds, and says so."""
    full = [_row(CLIENT_A, SINCE + 1) for _ in range(QUERY_LOG_PAGE_SIZE)]
    api, session = _make_api(*[FakeResponse(body=_page(full, cursor=5)) for _ in range(QUERY_LOG_MAX_PAGES + 2)])

    result = await api.call_get_query_activity(SINCE)

    assert QUERY_LOG_MAX_PAGES == 3
    assert result.pages == 3
    assert result.complete is False
    assert result.queries_read == 3000
    assert len(session.urls) == 3
    assert session.urls[2].endswith("cursor=5&start=2000")


async def test_the_cursor_of_later_pages_is_ignored() -> None:
    """Only the cursor of the first page is used, even if a later page announces another one."""
    api, session = _make_api(
        FakeResponse(body=_page([_row(), _row()], cursor=10)),
        FakeResponse(body=_page([_row()], cursor=None)),
    )

    result = await api.call_get_query_activity(SINCE, page_size=2)

    assert result.pages == 2
    assert "cursor=10&start=2" in session.urls[1]


class Clock:  # pylint: disable=too-few-public-methods
    """A clock that only moves when told to, standing for `time.monotonic`."""

    def __init__(self) -> None:
        """Start at zero."""
        self.now = 0.0

    def monotonic(self) -> float:
        """Return the current time."""
        return self.now


async def test_budget_spent_stops_the_read_as_incomplete() -> None:
    """When the time budget is gone before a page, the read ends there; the timeout of a page is what remains."""
    clock = Clock()

    def slow_page() -> FakeResponse:
        """Answer a full page that took five seconds."""
        clock.now += 5
        return FakeResponse(body=_page([_row(), _row()], cursor=3))

    api, session = _make_api(slow_page, slow_page, slow_page)
    timeouts: list[float] = []
    original = api._call  # pylint: disable=protected-access

    async def spy(*args: Any, **kwargs: Any) -> dict[str, Any]:
        """Record the timeout given to each page."""
        timeouts.append(kwargs["timeout"])
        return await original(*args, **kwargs)

    with patch.object(api, "_call", spy), patch(f"{API}.time", SimpleNamespace(monotonic=clock.monotonic)):
        result = await api.call_get_query_activity(SINCE, page_size=2, budget=8.0)

    assert result.pages == 2
    assert result.complete is False
    assert len(session.urls) == 2
    assert timeouts == [5.0, 3.0]
    assert result.duration == 10.0


async def test_a_spent_budget_still_reads_the_first_page() -> None:
    """Even with no budget, the first page is read, with the shortest timeout."""
    api, session = _make_api(FakeResponse(body=_page([_row()], cursor=1)))
    timeouts: list[float] = []
    original = api._call  # pylint: disable=protected-access

    async def spy(*args: Any, **kwargs: Any) -> dict[str, Any]:
        """Record the timeout given to the page."""
        timeouts.append(kwargs["timeout"])
        return await original(*args, **kwargs)

    with patch.object(api, "_call", spy):
        result = await api.call_get_query_activity(SINCE, budget=0)

    assert result.pages == 1
    assert len(session.urls) == 1
    assert timeouts == [0.1]


def test_budget_constants() -> None:
    """The read is bounded as specified."""
    assert QUERY_LOG_BUDGET_SECONDS == 8.0
    assert QUERY_LOG_PAGE_SIZE == 1000


# --------------------------------------------------------------------------------------------------
# Timeouts
# --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("error", [TimeoutError(), ClientError("down")], ids=["timeout", "network"])
async def test_timeout_or_network_error_on_the_first_page_is_raised(error: Exception) -> None:
    """Nothing was read: the failure is the one of the connection."""
    api, _ = _make_api(error)

    with pytest.raises(ClientConnectorError):
        await api.call_get_query_activity(SINCE)


async def test_timeout_on_the_second_page_gives_a_partial_result() -> None:
    """The pages already read are kept; the read is incomplete and nothing is raised."""
    api, session = _make_api(
        FakeResponse(body=_page([_row(CLIENT_A, SINCE + 8), _row(CLIENT_B, SINCE + 6)], cursor=8)),
        TimeoutError(),
    )

    result = await api.call_get_query_activity(SINCE, page_size=2)

    assert result.pages == 1
    assert result.complete is False
    assert result.queries_read == 2
    assert result.last_seen_by_ip == {CLIENT_A: SINCE + 8, CLIENT_B: SINCE + 6}
    assert len(session.urls) == 2


async def test_hanging_body_is_bounded_by_the_outer_timeout() -> None:
    """A response whose reading never ends is cut, and reported as a connection failure."""
    api, _ = _make_api()

    async def hang(*_: Any, **__: Any) -> dict[str, Any]:
        """Never answer."""
        await asyncio.sleep(60)
        return {}

    # The outer timeout is the request timeout plus two seconds: a negative request timeout makes it short.
    with (
        patch.object(api, "_call", hang),
        pytest.raises(ClientConnectorError),
    ):
        await api._read_query_page("/queries?from=1.000", -1.95)  # pylint: disable=protected-access


# --------------------------------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "headers", "expected", "retry_after"),
    [
        (403, {}, ForbiddenError, None),
        (404, {}, NotFoundError, None),
        (400, {}, BadRequestError, None),
        (401, {}, UnauthorizedError, None),
        (429, {}, TooManyRequestsError, None),
        (429, {"Retry-After": "90"}, TooManyRequestsError, 90.0),
        (429, {"Retry-After": "0"}, TooManyRequestsError, 1.0),
        (429, {"Retry-After": "86400"}, TooManyRequestsError, 3600.0),
        (429, {"Retry-After": "later"}, TooManyRequestsError, None),
        (403, {"Retry-After": "15"}, ForbiddenError, 15.0),
    ],
)
async def test_error_statuses_raise_with_the_retry_after(
    status: int, headers: dict[str, str], expected: type[APIError], retry_after: float | None
) -> None:
    """An error status raises its exception, which carries the delay of the Retry-After header when readable."""
    api, session = _make_api(FakeResponse(status, body={"error": {"key": "x", "message": "m"}}, headers=headers))

    with pytest.raises(expected) as raised:
        await api.call_get_query_activity(SINCE)

    assert raised.value.retry_after == retry_after
    assert raised.value.body == {"error": {"key": "x", "message": "m"}}
    assert len(session.urls) == 1


async def test_retry_after_as_an_http_date() -> None:
    """A date in the header gives the seconds left until it."""
    header = format_datetime(datetime.now(UTC) + timedelta(seconds=300), usegmt=True)
    api, _ = _make_api(FakeResponse(429, headers={"Retry-After": header}))

    with pytest.raises(TooManyRequestsError) as raised:
        await api.call_get_query_activity(SINCE)

    assert raised.value.retry_after is not None
    assert 290 <= raised.value.retry_after <= 300


async def test_an_error_on_a_later_page_is_raised() -> None:
    """Only a timeout ends a read early: an error status of a later page is still an error."""
    api, _ = _make_api(FakeResponse(body=_page([_row(), _row()])), FakeResponse(403))

    with pytest.raises(ForbiddenError):
        await api.call_get_query_activity(SINCE, page_size=2)


async def test_no_cursor_means_the_query_log_is_unavailable() -> None:
    """Pi-hole answers without cursor at its maximum privacy level: that is not an empty window."""
    api, _ = _make_api(FakeResponse(body={"queries": [], "cursor": None, "recordsTotal": 0}))

    with pytest.raises(QueryLogUnavailableError):
        await api.call_get_query_activity(SINCE)


async def test_missing_cursor_key_is_unavailable_too() -> None:
    """A body without any cursor key is read as a null cursor."""
    api, _ = _make_api(FakeResponse(body={"queries": []}))

    with pytest.raises(QueryLogUnavailableError):
        await api.call_get_query_activity(SINCE)


@pytest.mark.parametrize("cursor", ["4242", 12.5, True, False, [1], {"id": 1}], ids=repr)
async def test_a_cursor_that_is_not_an_integer_is_a_structure_error(cursor: Any) -> None:
    """The cursor is sent back as it is: only an integer is accepted."""
    api, _ = _make_api(FakeResponse(body=_page([_row()], cursor=cursor)))

    with pytest.raises(DataStructureError):
        await api.call_get_query_activity(SINCE)


@pytest.mark.parametrize(
    "body",
    [None, [], "text", {"cursor": 1}, {"queries": None, "cursor": 1}, {"queries": {"a": 1}, "cursor": 1}],
    ids=repr,
)
async def test_a_body_without_a_list_of_queries_is_a_structure_error(body: Any) -> None:
    """The first page must be a dictionary holding a list of queries."""
    api, _ = _make_api(FakeResponse(body=body))

    with pytest.raises(DataStructureError):
        await api.call_get_query_activity(SINCE)


async def test_nothing_is_stored_on_the_client() -> None:
    """A read leaves the caches of the client untouched, and no domain on the object."""
    api, _ = _make_api(FakeResponse(body=_page([_row()])))
    before = {key: repr(value) for key, value in vars(api).items() if key.startswith("cache_")}

    await api.call_get_query_activity(SINCE)

    assert {key: repr(value) for key, value in vars(api).items() if key.startswith("cache_")} == before
    assert MARKER not in repr(vars(api))


# --------------------------------------------------------------------------------------------------
# Logs
# --------------------------------------------------------------------------------------------------


async def test_successful_read_logs_a_row_count_and_no_domain(caplog: pytest.LogCaptureFixture) -> None:
    """In debug, a read logs the URL and the number of rows, never a domain nor a client name."""
    api, _ = _make_api(FakeResponse(body=_page([_row(), _row(CLIENT_B)])))

    with caplog.at_level(logging.DEBUG):
        await api.call_get_query_activity(SINCE, page_size=5)

    assert MARKER not in caplog.text
    assert "marker" not in caplog.text
    assert "GET" in caplog.text
    assert "/queries?from=1700000000.000&length=5 : 2 rows" in caplog.text


async def test_failed_read_logs_no_domain_either(caplog: pytest.LogCaptureFixture) -> None:
    """The body of an error response is kept on the exception but not written to the log."""
    body = {"error": {"key": "bad_request", "message": f"cannot filter {MARKER}"}}
    api, _ = _make_api(FakeResponse(403, body=body))

    with caplog.at_level(logging.DEBUG), pytest.raises(ForbiddenError) as raised:
        await api.call_get_query_activity(SINCE)

    assert MARKER not in caplog.text
    assert "0 rows" in caplog.text
    assert raised.value.body == body


async def test_the_default_logging_still_writes_the_body(caplog: pytest.LogCaptureFixture) -> None:
    """Control: any other route keeps logging the body, so the previous tests do detect a leak."""
    api, _ = _make_api(FakeResponse(body={"value": MARKER}), FakeResponse(403, body={"value": MARKER}))

    with caplog.at_level(logging.DEBUG):
        await api._call("/info", method="GET", action="x")  # pylint: disable=protected-access
        with pytest.raises(ForbiddenError):
            await api._call("/info", method="GET", action="x")  # pylint: disable=protected-access

    assert caplog.text.count(MARKER) == 2


async def test_log_body_false_with_a_body_that_is_not_a_dictionary(caplog: pytest.LogCaptureFixture) -> None:
    """Without a list of queries the message holds zero rows, whatever the body is."""
    api, _ = _make_api(FakeResponse(body=[MARKER]))

    with caplog.at_level(logging.DEBUG):
        await api._call(  # pylint: disable=protected-access
            "/queries", method="GET", action="x", log_body=False
        )

    assert MARKER not in caplog.text
    assert "0 rows" in caplog.text


# --------------------------------------------------------------------------------------------------
# The request of the network devices is the former one without presence
# --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kwargs", "route"),
    [
        ({}, "/network/devices?max_devices=2048"),
        ({"max_addresses": None}, "/network/devices?max_devices=2048"),
        ({"max_addresses": 10}, "/network/devices?max_devices=2048&max_addresses=10"),
        ({"max_devices": 50}, "/network/devices?max_devices=50"),
        ({"max_devices": 50, "max_addresses": 10}, "/network/devices?max_devices=50&max_addresses=10"),
    ],
)
async def test_network_devices_route(kwargs: dict[str, Any], route: str) -> None:
    """Without `max_addresses` the route is exactly the former one."""
    api = Api(session=MagicMock(), url=BASE_URL)
    api._call = AsyncMock(return_value={"code": 200, "reason": "OK", "data": {"devices": []}})  # type: ignore[method-assign]  # pylint: disable=protected-access

    result = await api.call_get_network_devices(**kwargs)

    assert api._call.await_args.args[0] == route  # pylint: disable=protected-access
    assert result["code"] == 200


@pytest.mark.parametrize(("given", "expected"), [(None, None), (10, 10)])
async def test_live_data_forwards_max_addresses(given: int | None, expected: int | None) -> None:
    """The live fetch passes `max_addresses` to the request of the network devices, None by default."""
    api = MagicMock()
    for name in (
        "call_summary",
        "call_blocking_status",
        "call_get_groups",
        "call_padd",
        "call_get_configured_clients",
        "call_get_dhcp_leases",
        "call_get_network_devices",
        "call_get_auth_sessions",
    ):
        setattr(api, name, AsyncMock(return_value={}))

    if given is None:
        await async_get_live_data(api, enable_device_tracker=True)
    else:
        await async_get_live_data(api, enable_device_tracker=True, max_addresses=given)

    api.call_get_network_devices.assert_awaited_once_with(max_addresses=expected)


async def test_live_data_without_tracking_does_not_ask_for_devices() -> None:
    """With the tracking off, the network devices are not requested at all."""
    api = MagicMock()
    for name in (
        "call_summary",
        "call_blocking_status",
        "call_get_groups",
        "call_padd",
        "call_get_configured_clients",
        "call_get_dhcp_leases",
        "call_get_network_devices",
        "call_get_auth_sessions",
    ):
        setattr(api, name, AsyncMock(return_value={}))

    await async_get_live_data(api, enable_device_tracker=False, max_addresses=10)

    api.call_get_network_devices.assert_not_called()


async def test_ordinary_calls_keep_their_sixty_second_timeout() -> None:
    """A call that does not ask for a timeout keeps the former limit of 60 seconds."""
    api, _ = _make_api(FakeResponse(body={"ok": True}))

    with patch(f"{API}.asyncio.timeout", wraps=asyncio.timeout) as timeout:
        await api._call("/info", method="GET", action="x")  # pylint: disable=protected-access

    timeout.assert_called_once_with(60.0)


@pytest.mark.parametrize("status", [400, 403, 404, 405])
async def test_expected_refusals_are_not_logged_as_errors(status: int, caplog: pytest.LogCaptureFixture) -> None:
    """A refusal that only says the query log cannot be used is a debug line, however often it is tried."""
    api, _ = _make_api(*[FakeResponse(status, body={"error": {"key": "x"}}) for _ in range(3)])

    with caplog.at_level(logging.DEBUG):
        for _ in range(3):
            with pytest.raises(APIError):
                await api.call_get_query_activity(SINCE)

    assert [record for record in caplog.records if record.levelno >= logging.ERROR] == []
    assert (
        len([record for record in caplog.records if record.levelno == logging.DEBUG and "0 rows" in record.message])
        == 3
    )


@pytest.mark.parametrize("status", [401, 429, 500, 503])
async def test_other_failures_are_still_logged_as_errors(status: int, caplog: pytest.LogCaptureFixture) -> None:
    """The other failures keep their error line, one per attempt."""
    api, _ = _make_api(FakeResponse(status, body={"error": {"key": "x"}}))

    with caplog.at_level(logging.DEBUG), pytest.raises(APIError):
        await api.call_get_query_activity(SINCE)

    errors = [record for record in caplog.records if record.levelno >= logging.ERROR]
    assert len(errors) == 1
    assert MARKER not in caplog.text


# --- Clients hidden by the privacy level of Pi-hole (every client recorded as 0.0.0.0) ---


@pytest.mark.parametrize("hidden", ["0.0.0.0", "::", "0:0:0:0:0:0:0:0"])  # noqa: S104
def test_parse_skips_a_hidden_client_but_counts_the_row(hidden: str) -> None:
    """An unspecified address belongs to no device: the row is read, never kept."""
    newest, count = parse_query_activity([_row(hidden, SINCE + 9), _row(CLIENT_A, SINCE + 3)])

    assert newest == {CLIENT_A: SINCE + 3}
    assert count == 2


def test_count_hidden_clients() -> None:
    """Only the rows with an unspecified address are counted, and nothing else is looked at."""
    rows = [_row("0.0.0.0"), _row("::"), _row(CLIENT_A), "junk", {"client": None}, {"client": {"ip": "nope"}}]  # noqa: S104

    assert count_hidden_clients(rows) == 2
    assert count_hidden_clients(None) == 0
    assert count_hidden_clients({"queries": rows}) == 0


async def test_a_window_of_hidden_clients_is_unavailable() -> None:
    """At the level that hides the clients nobody can be matched: the read raises, so the fallback and the long delay apply."""
    api, _ = _make_api(FakeResponse(body=_page([_row("0.0.0.0"), _row("0.0.0.0")])))  # noqa: S104

    with pytest.raises(QueryLogUnavailableError):
        await api.call_get_query_activity(SINCE, page_size=5)


async def test_hidden_clients_next_to_real_ones_are_not_an_error() -> None:
    """Right after a change of level the log mixes both: the real addresses are kept."""
    api, _ = _make_api(FakeResponse(body=_page([_row("0.0.0.0", SINCE + 9), _row(CLIENT_A, SINCE + 5)])))  # noqa: S104

    result = await api.call_get_query_activity(SINCE, page_size=5)

    assert result.last_seen_by_ip == {CLIENT_A: SINCE + 5}
    assert result.queries_read == 2


async def test_hidden_clients_over_two_pages_with_a_real_one_on_the_second() -> None:
    """The decision is taken on the whole read, not page by page."""
    api, _ = _make_api(
        FakeResponse(body=_page([_row("0.0.0.0"), _row("0.0.0.0")])),  # noqa: S104
        FakeResponse(body=_page([_row(CLIENT_A, SINCE + 2)])),
    )

    result = await api.call_get_query_activity(SINCE, page_size=2)

    assert result.last_seen_by_ip == {CLIENT_A: SINCE + 2}
