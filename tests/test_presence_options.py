"""Check the presence refresh option of the options form: field, default, bounds, saving and texts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from custom_components.pi_hole_v6.config_flow import _async_validate_input
from custom_components.pi_hole_v6.const import (
    CONF_DEVICE_TRACKER_CONSIDER_HOME,
    CONF_DEVICE_TRACKER_MAC_LIST,
    CONF_DEVICE_TRACKER_STALE_DAYS,
    CONF_DEVICE_TRACKER_WHITELIST,
    CONF_ENABLE_DEVICE_TRACKER,
    CONF_UPDATE_INTERVAL_LIVE,
    CONF_UPDATE_INTERVAL_PRESENCE,
    CONF_UPDATE_INTERVAL_STATS,
    DEFAULT_UPDATE_INTERVAL_PRESENCE,
    DOMAIN,
    MAX_UPDATE_INTERVAL_PRESENCE,
    MIN_UPDATE_INTERVAL_PRESENCE,
    RECOMMENDED_UPDATE_INTERVAL_PRESENCE,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_URL
from homeassistant.data_entry_flow import FlowResultType, InvalidData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

COMPONENT_DIR = Path(__file__).parent.parent / "custom_components" / "pi_hole_v6"
URL = "https://pihole.local:443/api"
ERROR = "invalid_update_interval_presence"
BASE_INPUT: dict[str, Any] = {
    CONF_UPDATE_INTERVAL_LIVE: 120,
    CONF_UPDATE_INTERVAL_STATS: 300,
    CONF_ENABLE_DEVICE_TRACKER: True,
    CONF_DEVICE_TRACKER_WHITELIST: True,
    CONF_DEVICE_TRACKER_MAC_LIST: "",
    CONF_DEVICE_TRACKER_CONSIDER_HOME: 240,
    CONF_DEVICE_TRACKER_STALE_DAYS: 0,
}


def _entry(hass: HomeAssistant, **overrides: Any) -> MockConfigEntry:
    """Add to Home Assistant an entry with the earlier options, and without the presence one unless given."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=URL,
        data={CONF_NAME: "Pihole", CONF_URL: URL, CONF_PASSWORD: "pw", **BASE_INPUT, **overrides},
    )
    entry.add_to_hass(hass)
    return entry


def _field(result: Any) -> Any:
    """Return the schema key of the presence field of a form result."""
    return next(key for key in result["data_schema"].schema if str(key) == CONF_UPDATE_INTERVAL_PRESENCE)


def test_constants() -> None:
    """The bounds and the defaults are those of the specification."""
    assert DEFAULT_UPDATE_INTERVAL_PRESENCE == 0
    assert MIN_UPDATE_INTERVAL_PRESENCE == 15
    assert MAX_UPDATE_INTERVAL_PRESENCE == 300
    assert RECOMMENDED_UPDATE_INTERVAL_PRESENCE == 30
    assert CONF_UPDATE_INTERVAL_PRESENCE == "update_interval_presence"


async def test_old_entry_receives_the_default_zero(hass: HomeAssistant) -> None:
    """Opening the form of an entry that lacks the option stores 0 (disabled) and shows it."""
    entry = _entry(hass)
    assert CONF_UPDATE_INTERVAL_PRESENCE not in entry.data

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert entry.data[CONF_UPDATE_INTERVAL_PRESENCE] == 0
    assert _field(result).description == {"suggested_value": 0}


@pytest.mark.parametrize("stored", [0, 30, 300])
async def test_stored_value_is_kept_and_shown(hass: HomeAssistant, stored: int) -> None:
    """A stored value, 0 included, is neither replaced nor lost when the form opens."""
    entry = _entry(hass, **{CONF_UPDATE_INTERVAL_PRESENCE: stored})

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert entry.data[CONF_UPDATE_INTERVAL_PRESENCE] == stored
    assert _field(result).description == {"suggested_value": stored}


async def test_stored_none_counts_as_missing(hass: HomeAssistant) -> None:
    """A value stored as null is completed with the default."""
    entry = _entry(hass, **{CONF_UPDATE_INTERVAL_PRESENCE: None})

    await hass.config_entries.options.async_init(entry.entry_id)

    assert entry.data[CONF_UPDATE_INTERVAL_PRESENCE] == 0


async def test_selector_is_a_bounded_box_in_seconds(hass: HomeAssistant) -> None:
    """The field is a number box of step 1 from 0 to 300 seconds, optional like the other options."""
    entry = _entry(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    key = _field(result)
    config = result["data_schema"].schema[key].validators[0].config
    assert (config["min"], config["max"], config["step"]) == (0, 300, 1)
    assert config["unit_of_measurement"] == "s"
    assert config["mode"] == "box"
    assert type(key).__name__ == "Optional"


async def test_field_comes_after_the_stale_days(hass: HomeAssistant) -> None:
    """The field closes the group of the network tracking options."""
    entry = _entry(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    names = [str(key) for key in result["data_schema"].schema]
    assert names.index(CONF_UPDATE_INTERVAL_PRESENCE) == names.index(CONF_DEVICE_TRACKER_STALE_DAYS) + 1
    assert names[-1] == CONF_UPDATE_INTERVAL_PRESENCE


@pytest.mark.parametrize("value", [0, 15, 16, 30, 299, 300])
async def test_valid_values_are_saved_as_integers(hass: HomeAssistant, value: int) -> None:
    """0 and every value from 15 to 300 are written to the entry data."""
    entry = _entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**BASE_INPUT, CONF_UPDATE_INTERVAL_PRESENCE: value}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.data[CONF_UPDATE_INTERVAL_PRESENCE] == value
    assert isinstance(entry.data[CONF_UPDATE_INTERVAL_PRESENCE], int)


async def test_float_input_is_stored_as_an_integer(hass: HomeAssistant) -> None:
    """The number box sends floats: they become integers."""
    entry = _entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)

    await hass.config_entries.options.async_configure(
        result["flow_id"], {**BASE_INPUT, CONF_UPDATE_INTERVAL_PRESENCE: 30.0}
    )

    assert entry.data[CONF_UPDATE_INTERVAL_PRESENCE] == 30
    assert isinstance(entry.data[CONF_UPDATE_INTERVAL_PRESENCE], int)


@pytest.mark.parametrize("value", [1, 2, 7, 14])
async def test_one_to_fourteen_come_back_to_the_form_with_the_error(hass: HomeAssistant, value: int) -> None:
    """A value between 1 and 14 is refused with its own error code, and nothing is saved."""
    entry = _entry(hass, **{CONF_UPDATE_INTERVAL_PRESENCE: 30})
    result = await hass.config_entries.options.async_init(entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**BASE_INPUT, CONF_UPDATE_INTERVAL_PRESENCE: value}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_UPDATE_INTERVAL_PRESENCE: ERROR}
    assert entry.data[CONF_UPDATE_INTERVAL_PRESENCE] == 30
    assert _field(result).description == {"suggested_value": value}


@pytest.mark.parametrize("value", [301, 1000, -1])
async def test_out_of_the_selector_is_refused_by_the_schema(hass: HomeAssistant, value: int) -> None:
    """Above 300 or below 0 the selector refuses before the validation, and the stored value does not change."""
    entry = _entry(hass, **{CONF_UPDATE_INTERVAL_PRESENCE: 30})
    result = await hass.config_entries.options.async_init(entry.entry_id)

    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(
            result["flow_id"], {**BASE_INPUT, CONF_UPDATE_INTERVAL_PRESENCE: value}
        )

    assert entry.data[CONF_UPDATE_INTERVAL_PRESENCE] == 30


async def test_omitting_the_field_keeps_the_stored_value(hass: HomeAssistant) -> None:
    """Saving without the field leaves what the entry holds."""
    entry = _entry(hass, **{CONF_UPDATE_INTERVAL_PRESENCE: 45})
    result = await hass.config_entries.options.async_init(entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**BASE_INPUT, CONF_UPDATE_INTERVAL_LIVE: 60}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.data[CONF_UPDATE_INTERVAL_PRESENCE] == 45
    assert entry.data[CONF_UPDATE_INTERVAL_LIVE] == 60


async def test_saving_the_presence_leaves_the_other_options(hass: HomeAssistant) -> None:
    """Only the submitted values change."""
    entry = _entry(hass, **{CONF_DEVICE_TRACKER_CONSIDER_HOME: 900, CONF_DEVICE_TRACKER_STALE_DAYS: 45})
    result = await hass.config_entries.options.async_init(entry.entry_id)

    required = {
        key: value
        for key, value in BASE_INPUT.items()
        if key
        in (
            CONF_UPDATE_INTERVAL_LIVE,
            CONF_UPDATE_INTERVAL_STATS,
            CONF_ENABLE_DEVICE_TRACKER,
            CONF_DEVICE_TRACKER_WHITELIST,
            CONF_DEVICE_TRACKER_MAC_LIST,
        )
    }
    await hass.config_entries.options.async_configure(
        result["flow_id"], {**required, CONF_UPDATE_INTERVAL_PRESENCE: 60}
    )

    assert entry.data[CONF_UPDATE_INTERVAL_PRESENCE] == 60
    assert entry.data[CONF_DEVICE_TRACKER_CONSIDER_HOME] == 900
    assert entry.data[CONF_DEVICE_TRACKER_STALE_DAYS] == 45
    assert entry.data[CONF_ENABLE_DEVICE_TRACKER] is True


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, {}),
        (0, {}),
        (15, {}),
        (300, {}),
        (1, {CONF_UPDATE_INTERVAL_PRESENCE: ERROR}),
        (14, {CONF_UPDATE_INTERVAL_PRESENCE: ERROR}),
        (301, {CONF_UPDATE_INTERVAL_PRESENCE: ERROR}),
        (-1, {CONF_UPDATE_INTERVAL_PRESENCE: ERROR}),
    ],
    ids=repr,
)
async def test_validation_called_directly(value: int | None, expected: dict[str, str]) -> None:
    """The validation names the field; an absent field is not an error, and values past the bounds are refused too."""
    data = dict(BASE_INPUT)
    if value is not None:
        data[CONF_UPDATE_INTERVAL_PRESENCE] = value

    assert await _async_validate_input(data) == expected


async def test_other_errors_come_first() -> None:
    """The earlier checks keep their precedence over the presence one."""
    assert set(
        await _async_validate_input({**BASE_INPUT, CONF_UPDATE_INTERVAL_LIVE: 1, CONF_UPDATE_INTERVAL_PRESENCE: 5})
    ) == {CONF_UPDATE_INTERVAL_LIVE}
    assert set(
        await _async_validate_input(
            {**BASE_INPUT, CONF_DEVICE_TRACKER_STALE_DAYS: -1, CONF_UPDATE_INTERVAL_PRESENCE: 5}
        )
    ) == {CONF_DEVICE_TRACKER_STALE_DAYS}


# --------------------------------------------------------------------------------------------------
# Translations
# --------------------------------------------------------------------------------------------------

TRANSLATIONS = ("strings.json", "translations/en.json", "translations/fr.json")


def _options(name: str) -> dict[str, Any]:
    """Return the options section of a translation file."""
    return json.loads((COMPONENT_DIR / name).read_text(encoding="utf-8"))["options"]


@pytest.mark.parametrize("name", TRANSLATIONS)
def test_texts_exist(name: str) -> None:
    """The field has a label and a help text, and its error has a message."""
    options = _options(name)
    step = options["step"]["init"]

    assert step["data"][CONF_UPDATE_INTERVAL_PRESENCE].strip()
    assert step["data_description"][CONF_UPDATE_INTERVAL_PRESENCE].strip()
    assert options["error"][ERROR].strip()


@pytest.mark.parametrize("name", TRANSLATIONS)
def test_texts_quote_the_bounds_and_the_privacy_promise(name: str) -> None:
    """The help gives the bounds, the good value and the promise about domains; the error gives the bounds."""
    options = _options(name)
    text = options["step"]["init"]["data_description"][CONF_UPDATE_INTERVAL_PRESENCE]
    error = options["error"][ERROR]

    for number in ("15", "300", "30"):
        assert number in text
        if number != "30":
            assert number in error
    assert "0" in error
    if name.endswith("fr.json"):
        assert "domaines" in text
        assert "jamais" in text
        assert "diagnostics" in text
        assert "Rechargez" in text
        assert "désactiv" in text
    else:
        assert "domains" in text
        assert "never" in text
        assert "diagnostics" in text
        assert "Reload" in text
        assert "disables" in text


def test_label_in_the_three_languages() -> None:
    """The labels are the specified ones."""
    labels = [_options(name)["step"]["init"]["data"][CONF_UPDATE_INTERVAL_PRESENCE] for name in TRANSLATIONS]

    assert labels[0] == labels[1] == "Presence refresh frequency (seconds)"
    assert labels[2] == "Fréquence de rafraîchissement de la présence (secondes)"


def test_english_texts_are_the_same_in_strings_and_en() -> None:
    """The source file and its English translation say the same."""
    assert (
        _options("strings.json")["step"]["init"]["data_description"][CONF_UPDATE_INTERVAL_PRESENCE]
        == _options("translations/en.json")["step"]["init"]["data_description"][CONF_UPDATE_INTERVAL_PRESENCE]
    )
    assert _options("strings.json")["error"][ERROR] == _options("translations/en.json")["error"][ERROR]


def test_the_error_is_an_options_error_only() -> None:
    """The error has no place in the config flow texts."""
    for name in TRANSLATIONS:
        config = json.loads((COMPONENT_DIR / name).read_text(encoding="utf-8"))["config"]
        assert ERROR not in config.get("error", {})
