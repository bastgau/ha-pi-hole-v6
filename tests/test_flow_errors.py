"""Check how the config and options flows route errors and drop a fingerprint that no longer applies."""

from __future__ import annotations

from typing import Any

from custom_components.pi_hole_v6.config_flow import _candidate_config, _map_errors
from custom_components.pi_hole_v6.const import CONF_CERT_FINGERPRINT, CONF_VERIFY_SSL

from homeassistant.const import CONF_PASSWORD, CONF_URL

ENTRY_DATA: dict[str, Any] = {
    CONF_URL: "https://pihole.local/api",
    CONF_PASSWORD: "secret",
    CONF_VERIFY_SSL: True,
    CONF_CERT_FINGERPRINT: "ab" * 32,
}


def test_error_on_a_missing_field_goes_to_the_form() -> None:
    """An error on a field the form does not show is attached to the whole form instead of being lost."""
    assert _map_errors({CONF_PASSWORD: "invalid_auth"}, {CONF_URL}) == {"base": "invalid_auth"}


def test_error_on_a_shown_field_stays_on_that_field() -> None:
    """An error on a field the form shows is kept on that field."""
    assert _map_errors({CONF_URL: "cannot_connect"}, {CONF_URL}) == {CONF_URL: "cannot_connect"}


def test_fingerprint_is_kept_when_verification_stays_enabled_and_url_is_unchanged() -> None:
    """Saving unrelated options keeps the confirmed certificate."""
    config = _candidate_config(ENTRY_DATA, {CONF_URL: ENTRY_DATA[CONF_URL], CONF_VERIFY_SSL: True})

    assert config[CONF_CERT_FINGERPRINT] == ENTRY_DATA[CONF_CERT_FINGERPRINT]


def test_fingerprint_is_dropped_when_verification_is_disabled() -> None:
    """Disabling verification removes the pinned certificate."""
    config = _candidate_config(ENTRY_DATA, {CONF_URL: ENTRY_DATA[CONF_URL], CONF_VERIFY_SSL: False})

    assert CONF_CERT_FINGERPRINT not in config


def test_fingerprint_is_dropped_when_the_url_changes() -> None:
    """A fingerprint belongs to one URL: changing the URL removes it."""
    config = _candidate_config(ENTRY_DATA, {CONF_URL: "https://other.local/api", CONF_VERIFY_SSL: True})

    assert CONF_CERT_FINGERPRINT not in config
