"""Check the certificate verification option and its migration for existing config entries."""

from types import SimpleNamespace
from typing import Any

from custom_components.pi_hole_v6 import migrate_legacy_verify_ssl
from custom_components.pi_hole_v6.const import (
    CONF_VERIFY_SSL,
    DEFAULT_VERIFY_SSL,
    LEGACY_VERIFY_SSL,
)


class _FakeConfigEntries:
    """Record the updates made to a config entry, as Home Assistant would store them."""

    def __init__(self) -> None:
        self.updates: list[dict[str, Any]] = []

    def async_update_entry(self, entry: Any, data: dict[str, Any]) -> None:
        """Store the new data on the entry and remember the update."""
        entry.data = data
        self.updates.append(data)


def _hass() -> SimpleNamespace:
    return SimpleNamespace(config_entries=_FakeConfigEntries())


def test_new_entries_verify_certificates_by_default() -> None:
    """The option defaults to verification for new entries."""
    assert DEFAULT_VERIFY_SSL is True


def test_legacy_entry_without_option_keeps_previous_behaviour() -> None:
    """An entry created before the option existed is stored with verification disabled."""
    hass = _hass()
    entry = SimpleNamespace(data={"url": "https://pihole.local/api"})

    assert migrate_legacy_verify_ssl(hass, entry) is False  # type: ignore[arg-type]
    assert entry.data[CONF_VERIFY_SSL] is LEGACY_VERIFY_SSL
    assert entry.data["url"] == "https://pihole.local/api"
    assert len(hass.config_entries.updates) == 1  # type: ignore[attr-defined]


def test_entry_with_option_is_not_rewritten() -> None:
    """An entry that already stores the option keeps its value and is not updated again."""
    hass = _hass()
    entry = SimpleNamespace(data={"url": "https://pihole.local/api", CONF_VERIFY_SSL: True})

    assert migrate_legacy_verify_ssl(hass, entry) is True  # type: ignore[arg-type]
    assert hass.config_entries.updates == []  # type: ignore[attr-defined]
