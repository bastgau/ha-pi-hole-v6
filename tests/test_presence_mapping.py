"""Check the pure attribution of the clients of the query log to the devices of the network table."""

from __future__ import annotations

from typing import Any

from custom_components.pi_hole_v6.presence import build_ip_owners, map_activity_to_devices
import pytest

MAC_A = "aa:00:00:00:00:0a"
MAC_B = "aa:00:00:00:00:0b"


def _row(mac: Any, *ips: tuple[Any, Any]) -> dict[str, Any]:
    """Return a row of the network table with the given (address, lastSeen) pairs."""
    return {"hwaddr": mac, "ips": [{"ip": ip, "lastSeen": seen, "name": None} for ip, seen in ips]}


def test_one_address_per_device() -> None:
    """Each address belongs to the lowercase MAC of its row."""
    owners = build_ip_owners(
        [_row("AA:00:00:00:00:0A", ("192.168.1.10", 100)), _row(MAC_B, ("192.168.1.11", 90), ("192.168.1.12", 80))]
    )

    assert owners == {"192.168.1.10": MAC_A, "192.168.1.11": MAC_B, "192.168.1.12": MAC_B}


@pytest.mark.parametrize("order", [(0, 1), (1, 0)])
def test_shared_address_goes_to_the_most_recent_last_seen(order: tuple[int, int]) -> None:
    """An address listed twice belongs to the row seen last, whatever the order of the rows."""
    rows = [_row(MAC_A, ("192.168.1.10", 100)), _row(MAC_B, ("192.168.1.10", 200))]

    owners = build_ip_owners([rows[order[0]], rows[order[1]]])

    assert owners == {"192.168.1.10": MAC_B}


def test_exact_tie_drops_the_address() -> None:
    """Better no gain than a false arrival: an address shared with the same last seen is nobody's."""
    owners = build_ip_owners(
        [_row(MAC_A, ("192.168.1.10", 100), ("192.168.1.20", 5)), _row(MAC_B, ("192.168.1.10", 100))]
    )

    assert owners == {"192.168.1.20": MAC_A}


def test_a_later_newer_row_overrules_a_tie() -> None:
    """A third row, newer than a tied pair, takes the address."""
    owners = build_ip_owners(
        [
            _row(MAC_A, ("192.168.1.10", 100)),
            _row(MAC_B, ("192.168.1.10", 100)),
            _row("aa:00:00:00:00:0c", ("192.168.1.10", 300)),
        ]
    )

    assert owners == {"192.168.1.10": "aa:00:00:00:00:0c"}


def test_an_older_row_after_a_tie_keeps_it_dropped() -> None:
    """A row older than a tied pair changes nothing: the address stays dropped."""
    owners = build_ip_owners(
        [
            _row(MAC_A, ("192.168.1.10", 100)),
            _row(MAC_B, ("192.168.1.10", 100)),
            _row("aa:00:00:00:00:0c", ("192.168.1.10", 50)),
        ]
    )

    assert owners == {}


def test_the_same_device_listing_an_address_twice_is_not_a_tie() -> None:
    """Two entries of one row for the same address (or one MAC in two spellings) are not ambiguous."""
    owners = build_ip_owners(
        [_row(MAC_A, ("192.168.1.10", 100), ("192.168.1.10", 100)), _row(MAC_A.upper(), ("192.168.1.10", 100))]
    )

    assert owners == {"192.168.1.10": MAC_A}


def test_pseudo_mac_row_is_a_row_like_any_other() -> None:
    """A client without a MAC is a row whose hwaddr is ip-x, lowercased, owning its own address."""
    owners = build_ip_owners([_row("IP-192.168.1.10", ("192.168.1.10", 100))])

    assert owners == {"192.168.1.10": "ip-192.168.1.10"}


def test_pseudo_mac_and_real_mac_on_the_same_address() -> None:
    """The row last seen on the address wins between a pseudo-MAC and a real one."""
    owners = build_ip_owners([_row("ip-192.168.1.10", ("192.168.1.10", 100)), _row(MAC_A, ("192.168.1.10", 400))])

    assert owners == {"192.168.1.10": MAC_A}


def test_ipv6_is_normalized_so_two_spellings_meet() -> None:
    """The same IPv6 address in two forms is one address: here a tie, hence dropped."""
    assert build_ip_owners([_row(MAC_A, ("FE80:0:0:0:0:0:0:1", 7))]) == {"fe80::1": MAC_A}
    assert build_ip_owners([_row(MAC_A, ("FE80:0:0:0:0:0:0:1", 7)), _row(MAC_B, ("fe80::1", 7))]) == {}
    assert build_ip_owners([_row(MAC_A, ("FE80:0:0:0:0:0:0:1", 9)), _row(MAC_B, ("fe80::1", 7))]) == {"fe80::1": MAC_A}


@pytest.mark.parametrize(
    "seen",
    [None, "9", True, [5], {}],
    ids=repr,
)
def test_unusable_last_seen_counts_as_zero(seen: Any) -> None:
    """A last seen that is not a number loses against any real one, and ties with another missing one."""
    assert build_ip_owners([_row(MAC_A, ("192.168.1.10", seen)), _row(MAC_B, ("192.168.1.10", 1))]) == {
        "192.168.1.10": MAC_B
    }
    assert build_ip_owners([_row(MAC_A, ("192.168.1.10", seen)), _row(MAC_B, ("192.168.1.10", None))]) == {}


def test_float_last_seen_is_compared_as_a_number() -> None:
    """Fractions of seconds count."""
    owners = build_ip_owners([_row(MAC_A, ("192.168.1.10", 100.5)), _row(MAC_B, ("192.168.1.10", 100.25))])

    assert owners == {"192.168.1.10": MAC_A}


@pytest.mark.parametrize(
    "row",
    [
        {},
        {"hwaddr": None, "ips": [{"ip": "192.168.1.10"}]},
        {"hwaddr": 5, "ips": [{"ip": "192.168.1.10"}]},
        {"hwaddr": MAC_A},
        {"hwaddr": MAC_A, "ips": None},
        {"hwaddr": MAC_A, "ips": "192.168.1.10"},
        {"hwaddr": MAC_A, "ips": ["192.168.1.10", None, 3]},
        {"hwaddr": MAC_A, "ips": [{}]},
        {"hwaddr": MAC_A, "ips": [{"ip": None}, {"ip": ""}, {"ip": "nope"}, {"ip": 12}]},
    ],
    ids=repr,
)
def test_malformed_rows_are_skipped(row: Any) -> None:
    """A row that cannot name an owner or an address gives nothing, and does not hide the good rows."""
    owners = build_ip_owners([row, _row(MAC_B, ("192.168.1.11", 1))])

    assert owners == {"192.168.1.11": MAC_B}


def test_no_devices() -> None:
    """An empty table owns nothing."""
    assert build_ip_owners([]) == {}
    assert map_activity_to_devices({"192.168.1.10": 5.0}, []) == ({}, 0)


def test_unknown_client_is_ignored_and_not_counted() -> None:
    """A client absent from the table gives no entry and is not counted as attributed."""
    devices = [_row(MAC_A, ("192.168.1.10", 100))]

    result = map_activity_to_devices({"192.168.1.10": 50.0, "10.9.9.9": 60.0}, devices)

    assert result == ({MAC_A: 50.0}, 1)


def test_several_addresses_of_one_device_keep_the_maximum() -> None:
    """The newest query of any address of a device dates the device, and both addresses count as attributed."""
    devices = [_row(MAC_A, ("192.168.1.10", 1), ("fe80::1", 1)), _row(MAC_B, ("192.168.1.11", 1))]

    result = map_activity_to_devices({"192.168.1.10": 50.0, "fe80::1": 80.0, "192.168.1.11": 10.0}, devices)

    assert result == ({MAC_A: 80.0, MAC_B: 10.0}, 3)


def test_the_older_address_does_not_lower_the_device() -> None:
    """Whatever the iteration order, the maximum is kept."""
    devices = [_row(MAC_A, ("192.168.1.10", 1), ("fe80::1", 1))]

    assert map_activity_to_devices({"fe80::1": 80.0, "192.168.1.10": 50.0}, devices) == ({MAC_A: 80.0}, 2)
    assert map_activity_to_devices({"192.168.1.10": 50.0, "fe80::1": 80.0}, devices) == ({MAC_A: 80.0}, 2)


def test_ambiguous_address_is_not_attributed() -> None:
    """An address dropped by a tie gives no gain to either device."""
    devices = [_row(MAC_A, ("192.168.1.10", 100)), _row(MAC_B, ("192.168.1.10", 100))]

    assert map_activity_to_devices({"192.168.1.10": 50.0}, devices) == ({}, 0)


def test_pseudo_mac_is_attributed() -> None:
    """A query from a client without a MAC dates its pseudo-MAC row."""
    devices = [_row("ip-192.168.1.10", ("192.168.1.10", 100))]

    assert map_activity_to_devices({"192.168.1.10": 50.0}, devices) == ({"ip-192.168.1.10": 50.0}, 1)


def test_accepts_any_iterable() -> None:
    """The devices may come as a generator."""
    devices = (_row(MAC_A, ("192.168.1.10", 100)) for _ in range(1))

    assert map_activity_to_devices({"192.168.1.10": 50.0}, devices) == ({MAC_A: 50.0}, 1)
