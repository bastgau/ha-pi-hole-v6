"""Check that the fingerprint shown to the user has the format openssl displays."""

from custom_components.pi_hole_v6.certificate import format_fingerprint


def test_fingerprint_is_shown_like_openssl() -> None:
    """The stored hexadecimal value is displayed in upper case with colons between bytes."""
    stored = "8c1b2f9adc5c122b60fc14ea767c416c7dd15639597e1ccfd4fe5074d29213f1"
    shown = "8C:1B:2F:9A:DC:5C:12:2B:60:FC:14:EA:76:7C:41:6C:7D:D1:56:39:59:7E:1C:CF:D4:FE:50:74:D2:92:13:F1"

    assert format_fingerprint(stored) == shown
