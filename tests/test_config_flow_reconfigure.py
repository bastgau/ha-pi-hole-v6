"""Run the reconfigure flow, the options form that replaced its fields, and the translations of both.

Like tests/test_config_flow.py, the flow tests replace the network boundaries (the connection check and the
certificate read). The tests that check the entities and the reauthentication load the entry for real, with
every data fetch replaced by a fake one.
"""

from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.pi_hole_v6.api import Api
from custom_components.pi_hole_v6.config_flow import (
    CONF_CONFIRM_CERTIFICATE,
    _get_data_option_schema,
)
from custom_components.pi_hole_v6.const import (
    CONF_CERT_FINGERPRINT,
    CONF_DEVICE_TRACKER_CONSIDER_HOME,
    CONF_DEVICE_TRACKER_MAC_LIST,
    CONF_DEVICE_TRACKER_STALE_DAYS,
    CONF_DEVICE_TRACKER_WHITELIST,
    CONF_ENABLE_DEVICE_TRACKER,
    CONF_UPDATE_INTERVAL_LIVE,
    CONF_UPDATE_INTERVAL_STATS,
    CONF_VERIFY_SSL,
    DOMAIN,
)
from custom_components.pi_hole_v6.exceptions import UnauthorizedError
from custom_components.pi_hole_v6.sensor import SENSOR_TYPES
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_URL, Platform
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

if TYPE_CHECKING:
    from collections.abc import Iterator

    from homeassistant.core import HomeAssistant

# pytest fixtures are requested by name
# pylint: disable=redefined-outer-name

INTEGRATION = "custom_components.pi_hole_v6"
CONFIG_FLOW = f"{INTEGRATION}.config_flow"
COMPONENT_DIR = Path(__file__).parent.parent / "custom_components" / "pi_hole_v6"
FIXTURES = Path(__file__).parent / "fixtures"
URL = "https://pihole.local:443/api"
NEW_URL = "https://New-Pihole.local:443/api"
OTHER_URL = "https://other.local:443/api"
FINGERPRINT = "ab" * 32
NEW_FINGERPRINT = "cd" * 32
OK = ({}, False)
UNTRUSTED = ({CONF_URL: "untrusted_certificate"}, True)
CHANGED = ({CONF_URL: "certificate_changed"}, False)
BAD_PASSWORD = ({CONF_PASSWORD: "invalid_auth"}, False)
BAD_URL = ({CONF_URL: "cannot_connect"}, False)


@pytest.fixture
def no_setup() -> Iterator[None]:
    """Do not set the integration up after a flow updated its entry."""
    with patch(f"{INTEGRATION}.async_setup_entry", AsyncMock(return_value=True)):
        yield


@pytest.fixture(name="expected_lingering_timers")
def expected_lingering_timers_fixture() -> bool:
    """Accept the one second timer the sensor platform starts and never cancels when the entry unloads."""
    return True


def _entry(hass: HomeAssistant, **overrides: Any) -> MockConfigEntry:
    """Add to Home Assistant an entry with a pinned certificate, a password and non-default options."""
    data: dict[str, Any] = {
        CONF_NAME: "Pihole",
        CONF_URL: URL,
        CONF_PASSWORD: "old-password",
        CONF_VERIFY_SSL: True,
        CONF_CERT_FINGERPRINT: FINGERPRINT,
        CONF_UPDATE_INTERVAL_LIVE: 120,
        CONF_UPDATE_INTERVAL_STATS: 300,
        CONF_ENABLE_DEVICE_TRACKER: False,
        CONF_DEVICE_TRACKER_WHITELIST: True,
        CONF_DEVICE_TRACKER_MAC_LIST: "",
    }
    unique_id = overrides.pop("unique_id", URL)
    data.update(overrides)
    entry = MockConfigEntry(domain=DOMAIN, unique_id=unique_id, data=data)
    entry.add_to_hass(hass)
    return entry


@contextmanager
def _network(
    checks: list[tuple[dict[str, str], bool]],
    *,
    fingerprint: str | list[str] = NEW_FINGERPRINT,
) -> Iterator[tuple[AsyncMock, AsyncMock, MagicMock]]:
    """Replace the connection check, the certificate read and the reload; yield the three mocks."""
    results = iter(checks)
    check = AsyncMock()
    configs: list[dict[str, Any]] = []

    async def fake_check(_: Any, config: dict[str, Any]) -> tuple[dict[str, str], bool]:
        """Record a copy of the tested settings, which the flow edits afterwards, and give the next result."""
        configs.append(dict(config))
        return next(results)

    check.side_effect = fake_check
    check.configs = configs
    read = AsyncMock(side_effect=fingerprint) if isinstance(fingerprint, list) else AsyncMock(return_value=fingerprint)
    reload = MagicMock()
    with (
        patch(f"{CONFIG_FLOW}._async_check_connection", check),
        patch(f"{CONFIG_FLOW}.async_get_certificate_fingerprint", read),
        patch("homeassistant.config_entries.ConfigEntries.async_schedule_reload", reload),
    ):
        yield check, read, reload


async def _reconfigure(hass: HomeAssistant, entry: MockConfigEntry, user_input: dict[str, Any]) -> Any:
    """Open the reconfigure flow of the entry and submit the form."""
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    return await hass.config_entries.flow.async_configure(result["flow_id"], user_input)


def _field(schema: Any, name: str) -> Any:
    """Return the schema marker of a form field, or None when the field is not on the form."""
    return next((key for key in schema.schema if str(key) == name), None)


# --------------------------------------------------------------------------------------------------
# Reconfigure flow
# --------------------------------------------------------------------------------------------------


async def test_form_is_prefilled_without_the_password(hass: HomeAssistant) -> None:
    """The form suggests the current address and verification setting, and never the password."""
    entry = _entry(hass)

    result = await entry.start_reconfigure_flow(hass)

    schema = result["data_schema"]
    assert result["type"] == FlowResultType.FORM
    assert {str(key) for key in schema.schema} == {CONF_URL, CONF_PASSWORD, CONF_VERIFY_SSL}
    assert _field(schema, CONF_URL).description == {"suggested_value": URL}
    assert _field(schema, CONF_VERIFY_SSL).description == {"suggested_value": True}
    assert not (_field(schema, CONF_PASSWORD).description or {}).get("suggested_value")
    assert "old-password" not in json.dumps(result["description_placeholders"])


async def test_legacy_entry_without_verification_setting_is_shown_unverified(hass: HomeAssistant) -> None:
    """An entry stored before the option existed is offered with verification disabled."""
    entry = _entry(hass)
    hass.config_entries.async_update_entry(
        entry, data={k: v for k, v in entry.data.items() if k not in (CONF_VERIFY_SSL, CONF_CERT_FINGERPRINT)}
    )

    result = await entry.start_reconfigure_flow(hass)

    assert _field(result["data_schema"], CONF_VERIFY_SSL).description == {"suggested_value": False}


async def test_same_url_and_empty_password_keep_everything(hass: HomeAssistant) -> None:
    """Without change the connection is still tested, then the password, the pin and the unique id are kept."""
    entry = _entry(hass)

    with _network([OK]) as (check, _, reload):
        result = await _reconfigure(hass, entry, {CONF_URL: URL, CONF_PASSWORD: "", CONF_VERIFY_SSL: True})

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_PASSWORD] == "old-password"
    assert entry.data[CONF_CERT_FINGERPRINT] == FINGERPRINT
    assert entry.unique_id == URL
    assert check.configs[-1][CONF_PASSWORD] == "old-password"
    reload.assert_called_once_with(entry.entry_id)


async def test_new_password_is_saved(hass: HomeAssistant) -> None:
    """A password typed in the form is tested, saved, and replaces the old one."""
    entry = _entry(hass)

    with _network([OK]) as (check, _, _):
        result = await _reconfigure(hass, entry, {CONF_URL: URL, CONF_PASSWORD: "new-password", CONF_VERIFY_SSL: True})

    assert result["reason"] == "reconfigure_successful"
    assert check.configs[-1][CONF_PASSWORD] == "new-password"
    assert entry.data[CONF_PASSWORD] == "new-password"
    assert entry.data[CONF_CERT_FINGERPRINT] == FINGERPRINT


async def test_missing_password_field_keeps_the_old_one(hass: HomeAssistant) -> None:
    """A submission without the optional password field keeps the stored password."""
    entry = _entry(hass)

    with _network([OK]):
        await _reconfigure(hass, entry, {CONF_URL: URL, CONF_VERIFY_SSL: True})

    assert entry.data[CONF_PASSWORD] == "old-password"


async def test_new_url_updates_the_unique_id_and_drops_the_pin(hass: HomeAssistant) -> None:
    """A new address gets a lowercase unique id on the same entry, without the pin of the old address."""
    entry = _entry(hass)
    entry_id = entry.entry_id

    with _network([OK]) as (_, _, reload):
        result = await _reconfigure(hass, entry, {CONF_URL: f" {NEW_URL} ", CONF_VERIFY_SSL: True})

    assert result["reason"] == "reconfigure_successful"
    assert entry.entry_id == entry_id
    assert hass.config_entries.async_get_entry(entry_id) is entry
    assert entry.unique_id == NEW_URL.lower()
    assert entry.data[CONF_URL] == NEW_URL
    assert CONF_CERT_FINGERPRINT not in entry.data
    assert entry.data[CONF_NAME] == "Pihole"
    assert entry.data[CONF_UPDATE_INTERVAL_LIVE] == 120
    reload.assert_called_once_with(entry_id)


async def test_collision_with_another_entry_shows_the_form_and_changes_nothing(hass: HomeAssistant) -> None:
    """An address already used by another entry is a form error on the address, not an abort."""
    entry = _entry(hass)
    _entry(hass, unique_id=OTHER_URL, **{CONF_URL: OTHER_URL})
    before = dict(entry.data)

    with _network([OK]) as (check, _, reload):
        result = await _reconfigure(
            hass, entry, {CONF_URL: OTHER_URL.upper().replace("HTTPS", "https"), CONF_VERIFY_SSL: True}
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reconfigure"
        assert result["errors"] == {CONF_URL: "already_configured"}
        assert dict(entry.data) == before
        assert entry.unique_id == URL
        check.assert_not_awaited()
        reload.assert_not_called()

        # The user fixes the address in the same flow.
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_URL: NEW_URL, CONF_VERIFY_SSL: True}
        )

    assert result["reason"] == "reconfigure_successful"
    assert entry.unique_id == NEW_URL.lower()


@pytest.mark.parametrize("stored_unique_id", [URL, URL.upper().replace("HTTPS", "https")])
async def test_url_differing_only_by_case_is_not_a_collision(hass: HomeAssistant, stored_unique_id: str) -> None:
    """The entry never collides with its own unique id, whatever the case of the address typed."""
    entry = _entry(hass, unique_id=stored_unique_id)

    with _network([OK]):
        result = await _reconfigure(hass, entry, {CONF_URL: "https://PiHole.local:443/api", CONF_VERIFY_SSL: True})

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.unique_id == URL
    assert entry.data[CONF_URL] == "https://PiHole.local:443/api"


async def test_new_url_with_untrusted_certificate_asks_for_confirmation(hass: HomeAssistant) -> None:
    """The certificate of the new address is read and confirmed, then pinned with the new unique id."""
    entry = _entry(hass)

    with _network([UNTRUSTED, OK]) as (check, read, reload):
        result = await _reconfigure(hass, entry, {CONF_URL: NEW_URL, CONF_VERIFY_SSL: True})
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "pin_certificate"
        assert result["description_placeholders"]["url"] == NEW_URL
        assert result["description_placeholders"]["fingerprint"] == "CD:" * 31 + "CD"
        assert entry.unique_id == URL
        reload.assert_not_called()

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_CONFIRM_CERTIFICATE: True})

    assert result["reason"] == "reconfigure_successful"
    assert entry.unique_id == NEW_URL.lower()
    assert entry.data[CONF_URL] == NEW_URL
    assert entry.data[CONF_CERT_FINGERPRINT] == NEW_FINGERPRINT
    assert entry.data[CONF_PASSWORD] == "old-password"
    assert read.await_args.args[1] == NEW_URL
    assert check.configs[-1][CONF_CERT_FINGERPRINT] == NEW_FINGERPRINT
    reload.assert_called_once_with(entry.entry_id)


async def test_pin_not_confirmed_changes_nothing(hass: HomeAssistant) -> None:
    """Refusing to confirm the certificate keeps the form on the confirmation step and the entry untouched."""
    entry = _entry(hass)
    before = dict(entry.data)

    with _network([UNTRUSTED]) as (_, _, reload):
        result = await _reconfigure(hass, entry, {CONF_URL: NEW_URL, CONF_VERIFY_SSL: True})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_CONFIRM_CERTIFICATE: False})

    assert result["step_id"] == "pin_certificate"
    assert result["errors"] == {CONF_CONFIRM_CERTIFICATE: "certificate_not_confirmed"}
    assert dict(entry.data) == before
    reload.assert_not_called()


async def test_unreadable_certificate_aborts_the_flow(hass: HomeAssistant) -> None:
    """When the certificate of the new address cannot be read, the flow aborts and the entry is kept."""
    entry = _entry(hass)
    before = dict(entry.data)

    with _network([UNTRUSTED]) as (_, read, _):
        read.side_effect = OSError("unreachable")
        result = await _reconfigure(hass, entry, {CONF_URL: NEW_URL, CONF_VERIFY_SSL: True})

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
    assert dict(entry.data) == before


@pytest.mark.parametrize(
    ("second_check", "step_id"),
    [(OK, None), (UNTRUSTED, "pin_certificate")],
    ids=["trusted-now", "untrusted-now"],
)
async def test_changed_certificate_drops_the_pin_and_retests_once(
    hass: HomeAssistant, second_check: tuple[dict[str, str], bool], step_id: str | None
) -> None:
    """A kept pin that no longer matches is forgotten and the connection is tested a second time."""
    entry = _entry(hass)

    with _network([CHANGED, second_check]) as (check, _, _):
        result = await _reconfigure(hass, entry, {CONF_URL: URL, CONF_VERIFY_SSL: True})

    assert check.await_count == 2
    assert check.configs[0][CONF_CERT_FINGERPRINT] == FINGERPRINT
    assert CONF_CERT_FINGERPRINT not in check.configs[1]
    if step_id is None:
        assert result["reason"] == "reconfigure_successful"
        assert CONF_CERT_FINGERPRINT not in entry.data
    else:
        assert result["step_id"] == step_id
        assert entry.data[CONF_CERT_FINGERPRINT] == FINGERPRINT


async def test_changed_certificate_then_confirmation_pins_the_new_one(hass: HomeAssistant) -> None:
    """After a changed certificate and a confirmation, the new fingerprint replaces the old one."""
    entry = _entry(hass)

    with _network([CHANGED, UNTRUSTED, OK]):
        result = await _reconfigure(hass, entry, {CONF_URL: URL, CONF_VERIFY_SSL: True})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_CONFIRM_CERTIFICATE: True})

    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_CERT_FINGERPRINT] == NEW_FINGERPRINT


@pytest.mark.parametrize(
    ("check", "errors"),
    [
        (BAD_PASSWORD, {CONF_PASSWORD: "invalid_auth"}),
        (BAD_URL, {CONF_URL: "cannot_connect"}),
        (({CONF_URL: "invalid_path"}, False), {CONF_URL: "invalid_path"}),
    ],
    ids=["password", "unreachable", "path"],
)
async def test_connection_errors_go_back_to_the_form(
    hass: HomeAssistant, check: tuple[dict[str, str], bool], errors: dict[str, str]
) -> None:
    """A failed connection test shows its error on the field, keeps the entry, and never pre-fills the password."""
    entry = _entry(hass)
    before = dict(entry.data)

    with _network([check]) as (_, _, reload):
        result = await _reconfigure(hass, entry, {CONF_URL: NEW_URL, CONF_PASSWORD: "typed", CONF_VERIFY_SSL: True})

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == errors
    assert not (_field(result["data_schema"], CONF_PASSWORD).description or {}).get("suggested_value")
    assert _field(result["data_schema"], CONF_URL).description == {"suggested_value": NEW_URL}
    assert dict(entry.data) == before
    assert entry.unique_id == URL
    reload.assert_not_called()


async def test_error_after_pin_certificate_goes_back_to_the_reconfigure_form(hass: HomeAssistant) -> None:
    """A wrong password found once the certificate is confirmed returns to the reconfigure form, without the pin."""
    entry = _entry(hass)
    before = dict(entry.data)

    with _network([UNTRUSTED, BAD_PASSWORD, OK]) as (_, _, reload):
        result = await _reconfigure(hass, entry, {CONF_URL: NEW_URL, CONF_PASSWORD: "wrong", CONF_VERIFY_SSL: True})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_CONFIRM_CERTIFICATE: True})

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reconfigure"
        assert result["errors"] == {CONF_PASSWORD: "invalid_auth"}
        assert dict(entry.data) == before
        reload.assert_not_called()

        # Submitting again goes through the whole check, the flow is still the reconfigure one.
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_URL: NEW_URL, CONF_PASSWORD: "right", CONF_VERIFY_SSL: False}
        )

    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_PASSWORD] == "right"
    assert CONF_CERT_FINGERPRINT not in entry.data


async def test_insecure_settings_are_warned_about(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    """Saving an unverified or clear text connection logs a warning."""
    entry = _entry(hass)

    with _network([OK]):
        await _reconfigure(hass, entry, {CONF_URL: "http://pihole.local/api", CONF_VERIFY_SSL: False})

    assert "verification is disabled" in caplog.text
    assert "unencrypted connection" in caplog.text


# --------------------------------------------------------------------------------------------------
# The three origins of the certificate confirmation
# --------------------------------------------------------------------------------------------------


async def test_pin_origin_user_creates_the_entry_and_returns_to_the_user_form(hass: HomeAssistant) -> None:
    """From the user flow, the confirmation creates the entry; a connection error returns to the user form."""
    user_input = {CONF_NAME: "Pi-hole", CONF_URL: URL, CONF_PASSWORD: "pw", CONF_VERIFY_SSL: True}

    with _network([UNTRUSTED, BAD_PASSWORD, UNTRUSTED, OK]):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input)
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_CONFIRM_CERTIFICATE: True})
        assert result["step_id"] == "user"
        assert result["errors"] == {CONF_PASSWORD: "invalid_auth"}

        result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input)
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_CONFIRM_CERTIFICATE: True})

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_CERT_FINGERPRINT] == NEW_FINGERPRINT
    assert result["data"][CONF_NAME] == "Pi-hole"


async def test_pin_origin_reauth_returns_to_the_reauth_form(hass: HomeAssistant, no_setup: None) -> None:
    """From reauth, a connection error after the confirmation returns to the password form."""
    entry = _entry(hass)

    with _network(
        [UNTRUSTED, BAD_PASSWORD, UNTRUSTED, OK], fingerprint=[FINGERPRINT, NEW_FINGERPRINT, NEW_FINGERPRINT]
    ):
        result = await entry.start_reauth_flow(hass)
        assert result["step_id"] == "reauth_confirm"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_PASSWORD: "typed"})
        assert result["step_id"] == "pin_certificate"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_CONFIRM_CERTIFICATE: True})

        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {CONF_PASSWORD: "invalid_auth"}
        assert entry.data[CONF_PASSWORD] == "old-password"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_PASSWORD: "new"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_CONFIRM_CERTIFICATE: True})

    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "new"
    assert entry.data[CONF_CERT_FINGERPRINT] == NEW_FINGERPRINT


async def test_reauth_with_changed_certificate_goes_straight_to_the_confirmation(
    hass: HomeAssistant, no_setup: None
) -> None:
    """Reauth with a stored pin that no longer matches the served certificate asks to confirm the new one."""
    entry = _entry(hass)

    with _network([OK]):
        result = await entry.start_reauth_flow(hass)
        assert result["step_id"] == "pin_certificate"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_CONFIRM_CERTIFICATE: True})

    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_CERT_FINGERPRINT] == NEW_FINGERPRINT
    assert entry.data[CONF_PASSWORD] == "old-password"
    assert entry.unique_id == URL


# --------------------------------------------------------------------------------------------------
# Options
# --------------------------------------------------------------------------------------------------


def test_options_schema_has_no_connection_field() -> None:
    """The address and the certificate verification are no longer options."""
    fields = {str(key) for key in _get_data_option_schema().schema}

    assert fields == {
        CONF_UPDATE_INTERVAL_LIVE,
        CONF_UPDATE_INTERVAL_STATS,
        CONF_ENABLE_DEVICE_TRACKER,
        CONF_DEVICE_TRACKER_WHITELIST,
        CONF_DEVICE_TRACKER_MAC_LIST,
        CONF_DEVICE_TRACKER_CONSIDER_HOME,
        CONF_DEVICE_TRACKER_STALE_DAYS,
    }


async def test_options_form_has_no_connection_field(hass: HomeAssistant) -> None:
    """The options form shows the refresh and tracking options only."""
    entry = _entry(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    shown = {str(key) for key in result["data_schema"].schema}
    assert CONF_URL not in shown
    assert CONF_VERIFY_SSL not in shown
    assert CONF_UPDATE_INTERVAL_LIVE in shown


async def test_saving_options_makes_no_connection_test_and_keeps_the_rest_of_the_data(hass: HomeAssistant) -> None:
    """Options are saved locally: no network call, and the connection data, pin included, stays as it was."""
    entry = _entry(hass)

    with (
        patch(f"{CONFIG_FLOW}._async_check_connection", AsyncMock()) as check,
        patch(f"{CONFIG_FLOW}.async_get_certificate_fingerprint", AsyncMock()) as read,
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_UPDATE_INTERVAL_LIVE: 60,
                CONF_UPDATE_INTERVAL_STATS: 600,
                CONF_ENABLE_DEVICE_TRACKER: True,
                CONF_DEVICE_TRACKER_WHITELIST: False,
                CONF_DEVICE_TRACKER_MAC_LIST: "aa:bb:cc:dd:ee:ff",
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    check.assert_not_awaited()
    read.assert_not_awaited()
    assert entry.data[CONF_UPDATE_INTERVAL_LIVE] == 60
    assert entry.data[CONF_UPDATE_INTERVAL_STATS] == 600
    assert entry.data[CONF_ENABLE_DEVICE_TRACKER] is True
    assert entry.data[CONF_DEVICE_TRACKER_MAC_LIST] == "aa:bb:cc:dd:ee:ff"
    assert entry.data[CONF_URL] == URL
    assert entry.data[CONF_PASSWORD] == "old-password"
    assert entry.data[CONF_VERIFY_SSL] is True
    assert entry.data[CONF_CERT_FINGERPRINT] == FINGERPRINT
    assert entry.data[CONF_NAME] == "Pihole"
    assert entry.unique_id == URL


@pytest.mark.parametrize(
    ("live", "stats", "error_field"),
    [
        (1, 300, CONF_UPDATE_INTERVAL_LIVE),
        (120, 100, CONF_UPDATE_INTERVAL_STATS),
    ],
)
async def test_invalid_options_show_their_error(hass: HomeAssistant, live: int, stats: int, error_field: str) -> None:
    """An invalid interval stays on the options form with its error and changes nothing."""
    entry = _entry(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    # Opening the form completes an older entry with the defaults of the options it lacks.
    before = dict(entry.data)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_UPDATE_INTERVAL_LIVE: live,
            CONF_UPDATE_INTERVAL_STATS: stats,
            CONF_ENABLE_DEVICE_TRACKER: False,
            CONF_DEVICE_TRACKER_WHITELIST: True,
            CONF_DEVICE_TRACKER_MAC_LIST: "",
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert set(result["errors"]) == {error_field}
    assert dict(entry.data) == before


# --------------------------------------------------------------------------------------------------
# Real setup: entities and reauthentication
# --------------------------------------------------------------------------------------------------


@contextmanager
def _fetches(*, failing: bool = False) -> Iterator[None]:
    """Replace every data fetch, with the padd one filling its cache from the fixture, or failing to log in."""
    padd = json.loads((FIXTURES / "padd_sensors.json").read_text(encoding="utf-8"))

    async def fake_live(api_client: Api, **_: Any) -> None:
        """Fill the padd cache like the live fetch does."""
        if failing:
            raise UnauthorizedError
        api_client.cache_padd = padd

    only_cpu = tuple(description for description in SENSOR_TYPES if description.key == "cpu_temperature")
    with (
        patch(f"{INTEGRATION}.PLATFORMS", [Platform.SENSOR]),
        patch(f"{INTEGRATION}.sensor.SENSOR_TYPES", only_cpu),
        patch(f"{INTEGRATION}.async_get_live_data", AsyncMock(side_effect=fake_live)),
        patch(f"{INTEGRATION}.async_get_stats_data", AsyncMock()),
        patch.object(Api, "call_get_ftl_info_messages", AsyncMock(return_value={})),
        patch.object(Api, "call_logout", AsyncMock()),
    ):
        yield


def _enable_cpu_sensor(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Pre-create the cpu temperature sensor, enabled, so that the setup creates its state."""
    er.async_get(hass).async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        f"{entry.entry_id}/cpu_temperature",
        config_entry=entry,
        suggested_object_id="pihole_cpu_temperature",
        disabled_by=None,
    )


def _registry_snapshot(hass: HomeAssistant, entry: MockConfigEntry) -> dict[str, str]:
    """Return the entity ids of the entry mapped to their unique ids."""
    return {
        registry_entry.entity_id: registry_entry.unique_id
        for registry_entry in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    }


async def test_entities_keep_their_ids_after_reconfigure(hass: HomeAssistant) -> None:
    """After pointing the entry to another address and reloading it, the entities are the same ones."""
    entry = _entry(hass)
    _enable_cpu_sensor(hass, entry)

    with _fetches():
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED
        before = _registry_snapshot(hass, entry)
        assert before == {"sensor.pihole_cpu_temperature": f"{entry.entry_id}/cpu_temperature"}
        assert hass.states.get("sensor.pihole_cpu_temperature").state == "48.3"

        with (
            patch(f"{CONFIG_FLOW}._async_check_connection", AsyncMock(side_effect=[UNTRUSTED, OK])),
            patch(f"{CONFIG_FLOW}.async_get_certificate_fingerprint", AsyncMock(return_value=NEW_FINGERPRINT)),
        ):
            result = await _reconfigure(hass, entry, {CONF_URL: NEW_URL, CONF_VERIFY_SSL: True})
            result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_CONFIRM_CERTIFICATE: True})
            await hass.async_block_till_done()

        assert result["reason"] == "reconfigure_successful"
        assert entry.state is ConfigEntryState.LOADED
        assert entry.runtime_data.api.url == NEW_URL
        assert _registry_snapshot(hass, entry) == before
        assert hass.states.get("sensor.pihole_cpu_temperature").state == "48.3"
        assert entry.unique_id == NEW_URL.lower()

        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_reauth_in_progress_is_aborted_once_reconfigure_reloads_the_entry(hass: HomeAssistant) -> None:
    """Home Assistant ends a pending reauthentication when the reloaded entry sets up successfully."""
    entry = _entry(hass)

    with (
        _fetches(failing=True),
        patch(f"{CONFIG_FLOW}.async_get_certificate_fingerprint", AsyncMock(return_value=FINGERPRINT)),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]

    with _fetches(), patch(f"{CONFIG_FLOW}._async_check_connection", AsyncMock(return_value=OK)):
        result = await _reconfigure(hass, entry, {CONF_URL: URL, CONF_PASSWORD: "new-password", CONF_VERIFY_SSL: True})
        await hass.async_block_till_done()

        assert result["reason"] == "reconfigure_successful"
        assert entry.state is ConfigEntryState.LOADED
        assert hass.config_entries.flow.async_progress_by_handler(DOMAIN) == []

        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


# --------------------------------------------------------------------------------------------------
# Translations
# --------------------------------------------------------------------------------------------------

TRANSLATIONS = ("strings.json", "translations/en.json", "translations/fr.json")
ORPHAN_OPTION_KEYS = ("url", "verify_ssl", "confirm_certificate")
ORPHAN_OPTION_ERRORS = (
    "untrusted_certificate",
    "certificate_changed",
    "certificate_not_confirmed",
    "cannot_connect",
    "invalid_path",
    "invalid_auth",
)


def _load(name: str) -> dict[str, Any]:
    """Read one translation file of the integration."""
    return json.loads((COMPONENT_DIR / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", TRANSLATIONS)
def test_reconfigure_step_is_translated(name: str) -> None:
    """The reconfigure step has a title, a description and a label and a help text for each of its fields."""
    step = _load(name)["config"]["step"]["reconfigure"]

    assert step["title"]
    assert "{example_url}" in step["data_description"]["url"]
    assert set(step["data"]) == {CONF_URL, CONF_PASSWORD, CONF_VERIFY_SSL}
    assert set(step["data_description"]) == {CONF_URL, CONF_PASSWORD, CONF_VERIFY_SSL}
    assert all(step["data"].values())
    assert step["description"]


@pytest.mark.parametrize("name", TRANSLATIONS)
def test_errors_and_abort_reasons_used_by_the_flows_are_translated(name: str) -> None:
    """Every error and abort reason the config flow can produce has a text."""
    config = _load(name)["config"]

    for error in (*ORPHAN_OPTION_ERRORS, "already_configured"):
        assert config["error"][error], error
    assert config["abort"]["reconfigure_successful"]
    assert config["abort"]["reauth_successful"]
    assert config["step"]["pin_certificate"]["data"]["confirm_certificate"]


@pytest.mark.parametrize("name", TRANSLATIONS)
def test_certificate_read_failure_abort_is_translated(name: str) -> None:
    """The pin_certificate step aborts with cannot_connect when the certificate cannot be read."""
    assert _load(name)["config"]["abort"]["cannot_connect"]


@pytest.mark.parametrize("name", TRANSLATIONS)
def test_options_form_has_no_text_left_from_its_connection_fields(name: str) -> None:
    """The options keep no label, error or step belonging to the removed address, verification and pin fields."""
    options = _load(name)["options"]

    assert set(options["step"]) == {"init"}
    for section in ("data", "data_description"):
        for key in ORPHAN_OPTION_KEYS:
            assert key not in options["step"]["init"][section]
    assert set(options["error"]) == {
        "invalid_update_interval_live",
        "invalid_update_interval_stats",
        "invalid_consider_home",
        "invalid_stale_days",
    }
    assert "abort" not in options


def test_translation_files_have_the_same_keys() -> None:
    """The three translation files describe the same steps, fields and errors."""

    def paths(node: Any, prefix: str = "") -> set[str]:
        if not isinstance(node, dict):
            return {prefix}
        return {path for key, value in node.items() for path in paths(value, f"{prefix}/{key}")}

    def forms(name: str) -> set[str]:
        content = _load(name)
        return paths(
            {
                "config": {"step": content["config"]["step"], "error": content["config"]["error"]},
                "options": content["options"],
            }
        )

    reference = forms("strings.json")
    for name in TRANSLATIONS[1:]:
        # en.json and fr.json also carry the error of the data structure, which strings.json does not have.
        assert forms(name) - {"/config/error/incorrect_data_expected"} == reference, name
