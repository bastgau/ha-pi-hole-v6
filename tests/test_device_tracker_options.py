"""Check the two network tracking options of the options form: their fields, their defaults, their bounds and their texts."""

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
    CONF_UPDATE_INTERVAL_STATS,
    DEFAULT_DEVICE_TRACKER_CONSIDER_HOME,
    DEFAULT_DEVICE_TRACKER_STALE_DAYS,
    DOMAIN,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_URL
from homeassistant.data_entry_flow import FlowResultType, InvalidData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

COMPONENT_DIR = Path(__file__).parent.parent / "custom_components" / "pi_hole_v6"
URL = "https://pihole.local:443/api"
BASE_INPUT: dict[str, Any] = {
    CONF_UPDATE_INTERVAL_LIVE: 120,
    CONF_UPDATE_INTERVAL_STATS: 300,
    CONF_ENABLE_DEVICE_TRACKER: True,
    CONF_DEVICE_TRACKER_WHITELIST: True,
    CONF_DEVICE_TRACKER_MAC_LIST: "",
}
NEW_KEYS = (CONF_DEVICE_TRACKER_CONSIDER_HOME, CONF_DEVICE_TRACKER_STALE_DAYS)


def _entry(hass: HomeAssistant, **overrides: Any) -> MockConfigEntry:
    """Add to Home Assistant an entry as the former versions stored it: without the two new options."""
    data: dict[str, Any] = {
        CONF_NAME: "Pihole",
        CONF_URL: URL,
        CONF_PASSWORD: "pw",
        **BASE_INPUT,
    }
    data.update(overrides)
    entry = MockConfigEntry(domain=DOMAIN, unique_id=URL, data=data)
    entry.add_to_hass(hass)
    return entry


def _field(result: Any, name: str) -> Any:
    """Return the schema key of a field of a form result."""
    return next(key for key in result["data_schema"].schema if str(key) == name)


# --------------------------------------------------------------------------------------------------
# Form
# --------------------------------------------------------------------------------------------------


async def test_form_shows_both_fields_and_completes_an_old_entry_with_the_defaults(hass: HomeAssistant) -> None:
    """Opening the form of an entry that lacks the options stores 240 and 30 and shows them."""
    entry = _entry(hass)
    assert not any(key in entry.data for key in NEW_KEYS)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert entry.data[CONF_DEVICE_TRACKER_CONSIDER_HOME] == 240
    assert entry.data[CONF_DEVICE_TRACKER_STALE_DAYS] == 30
    assert entry.data[CONF_DEVICE_TRACKER_CONSIDER_HOME] == DEFAULT_DEVICE_TRACKER_CONSIDER_HOME
    assert entry.data[CONF_DEVICE_TRACKER_STALE_DAYS] == DEFAULT_DEVICE_TRACKER_STALE_DAYS
    assert _field(result, CONF_DEVICE_TRACKER_CONSIDER_HOME).description == {"suggested_value": 240}
    assert _field(result, CONF_DEVICE_TRACKER_STALE_DAYS).description == {"suggested_value": 30}


async def test_form_selectors_are_bounded_boxes_with_their_unit(hass: HomeAssistant) -> None:
    """The fields are number boxes of step 1, bounded as specified, in seconds and in days."""
    entry = _entry(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    away = result["data_schema"].schema[_field(result, CONF_DEVICE_TRACKER_CONSIDER_HOME)]
    stale = result["data_schema"].schema[_field(result, CONF_DEVICE_TRACKER_STALE_DAYS)]
    away_config = away.validators[0].config
    stale_config = stale.validators[0].config
    assert (away_config["min"], away_config["max"], away_config["step"]) == (60, 86400, 1)
    assert (stale_config["min"], stale_config["max"], stale_config["step"]) == (0, 3650, 1)
    assert away_config["unit_of_measurement"] == "s"
    assert stale_config["unit_of_measurement"] == "d"
    assert away_config["mode"] == stale_config["mode"] == "box"


async def test_form_keeps_the_stored_values(hass: HomeAssistant) -> None:
    """An entry that holds the options keeps them when the form opens, and shows them."""
    entry = _entry(hass, **{CONF_DEVICE_TRACKER_CONSIDER_HOME: 900, CONF_DEVICE_TRACKER_STALE_DAYS: 45})

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert entry.data[CONF_DEVICE_TRACKER_CONSIDER_HOME] == 900
    assert entry.data[CONF_DEVICE_TRACKER_STALE_DAYS] == 45
    assert _field(result, CONF_DEVICE_TRACKER_CONSIDER_HOME).description == {"suggested_value": 900}
    assert _field(result, CONF_DEVICE_TRACKER_STALE_DAYS).description == {"suggested_value": 45}


@pytest.mark.parametrize("missing", NEW_KEYS)
async def test_form_completes_only_the_missing_option(hass: HomeAssistant, missing: str) -> None:
    """When one option is stored and the other is not, only the absent one receives its default."""
    stored = next(key for key in NEW_KEYS if key != missing)
    entry = _entry(hass, **{stored: 77 if stored == CONF_DEVICE_TRACKER_STALE_DAYS else 700})

    await hass.config_entries.options.async_init(entry.entry_id)

    assert entry.data[stored] == (77 if stored == CONF_DEVICE_TRACKER_STALE_DAYS else 700)
    assert entry.data[missing] == (30 if missing == CONF_DEVICE_TRACKER_STALE_DAYS else 240)


async def test_form_completes_a_stored_none(hass: HomeAssistant) -> None:
    """An option stored as null counts as missing."""
    entry = _entry(hass, **{CONF_DEVICE_TRACKER_CONSIDER_HOME: None, CONF_DEVICE_TRACKER_STALE_DAYS: None})

    await hass.config_entries.options.async_init(entry.entry_id)

    assert entry.data[CONF_DEVICE_TRACKER_CONSIDER_HOME] == 240
    assert entry.data[CONF_DEVICE_TRACKER_STALE_DAYS] == 30


async def test_form_keeps_a_stored_zero_stale_days(hass: HomeAssistant) -> None:
    """0 is a real value for the stale days: it is not replaced."""
    entry = _entry(hass, **{CONF_DEVICE_TRACKER_CONSIDER_HOME: 300, CONF_DEVICE_TRACKER_STALE_DAYS: 0})

    await hass.config_entries.options.async_init(entry.entry_id)

    assert entry.data[CONF_DEVICE_TRACKER_STALE_DAYS] == 0
    assert entry.data[CONF_DEVICE_TRACKER_CONSIDER_HOME] == 300


async def test_form_still_completes_the_former_options(hass: HomeAssistant) -> None:
    """The rewritten completion still gives the defaults of the earlier options, and replaces a stored 0 interval."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=URL,
        data={CONF_NAME: "Pihole", CONF_URL: URL, CONF_PASSWORD: "pw", CONF_UPDATE_INTERVAL_LIVE: 0},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.options.async_init(entry.entry_id)

    assert entry.data[CONF_UPDATE_INTERVAL_LIVE] == 120
    assert entry.data[CONF_UPDATE_INTERVAL_STATS] == 300
    assert entry.data[CONF_ENABLE_DEVICE_TRACKER] is False
    assert entry.data[CONF_DEVICE_TRACKER_WHITELIST] is True
    assert entry.data[CONF_DEVICE_TRACKER_MAC_LIST] == ""
    assert entry.data[CONF_DEVICE_TRACKER_CONSIDER_HOME] == 240
    assert entry.data[CONF_DEVICE_TRACKER_STALE_DAYS] == 30


# --------------------------------------------------------------------------------------------------
# Saving
# --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("consider_home", "stale_days"),
    [(60, 0), (86400, 3650), (240, 1), (600, 30)],
)
async def test_valid_values_are_saved_as_integers(hass: HomeAssistant, consider_home: int, stale_days: int) -> None:
    """Values within the bounds, boundaries included, are written to the entry data."""
    entry = _entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {**BASE_INPUT, CONF_DEVICE_TRACKER_CONSIDER_HOME: consider_home, CONF_DEVICE_TRACKER_STALE_DAYS: stale_days},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.data[CONF_DEVICE_TRACKER_CONSIDER_HOME] == consider_home
    assert entry.data[CONF_DEVICE_TRACKER_STALE_DAYS] == stale_days
    assert isinstance(entry.data[CONF_DEVICE_TRACKER_CONSIDER_HOME], int)
    assert isinstance(entry.data[CONF_DEVICE_TRACKER_STALE_DAYS], int)


async def test_float_input_is_stored_as_an_integer(hass: HomeAssistant) -> None:
    """The number box sends floats: they are coerced to integers."""
    entry = _entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)

    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {**BASE_INPUT, CONF_DEVICE_TRACKER_CONSIDER_HOME: 300.0, CONF_DEVICE_TRACKER_STALE_DAYS: 10.0},
    )

    assert isinstance(entry.data[CONF_DEVICE_TRACKER_CONSIDER_HOME], int)
    assert entry.data[CONF_DEVICE_TRACKER_CONSIDER_HOME] == 300
    assert entry.data[CONF_DEVICE_TRACKER_STALE_DAYS] == 10


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (CONF_DEVICE_TRACKER_CONSIDER_HOME, 59),
        (CONF_DEVICE_TRACKER_CONSIDER_HOME, 86401),
        (CONF_DEVICE_TRACKER_CONSIDER_HOME, -1),
        (CONF_DEVICE_TRACKER_CONSIDER_HOME, 0),
        (CONF_DEVICE_TRACKER_STALE_DAYS, -1),
        (CONF_DEVICE_TRACKER_STALE_DAYS, 3651),
    ],
)
async def test_out_of_bounds_values_are_rejected_by_the_schema(hass: HomeAssistant, field: str, value: int) -> None:
    """The form refuses a value outside its bounds, and the stored one does not change."""
    entry = _entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    before = dict(entry.data)

    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(result["flow_id"], {**BASE_INPUT, field: value})

    assert dict(entry.data) == before


async def test_omitted_keys_keep_the_stored_values(hass: HomeAssistant) -> None:
    """Saving without the two fields leaves what the entry holds, whatever else changes."""
    entry = _entry(hass, **{CONF_DEVICE_TRACKER_CONSIDER_HOME: 900, CONF_DEVICE_TRACKER_STALE_DAYS: 45})
    result = await hass.config_entries.options.async_init(entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**BASE_INPUT, CONF_UPDATE_INTERVAL_LIVE: 60}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.data[CONF_UPDATE_INTERVAL_LIVE] == 60
    assert entry.data[CONF_DEVICE_TRACKER_CONSIDER_HOME] == 900
    assert entry.data[CONF_DEVICE_TRACKER_STALE_DAYS] == 45


async def test_saving_one_field_leaves_the_other(hass: HomeAssistant) -> None:
    """Only the submitted option changes."""
    entry = _entry(hass, **{CONF_DEVICE_TRACKER_CONSIDER_HOME: 900, CONF_DEVICE_TRACKER_STALE_DAYS: 45})
    result = await hass.config_entries.options.async_init(entry.entry_id)

    await hass.config_entries.options.async_configure(
        result["flow_id"], {**BASE_INPUT, CONF_DEVICE_TRACKER_STALE_DAYS: 0}
    )

    assert entry.data[CONF_DEVICE_TRACKER_STALE_DAYS] == 0
    assert entry.data[CONF_DEVICE_TRACKER_CONSIDER_HOME] == 900


# --------------------------------------------------------------------------------------------------
# Validation, called directly
# --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("extra", "expected"),
    [
        ({}, {}),
        ({CONF_DEVICE_TRACKER_CONSIDER_HOME: 60, CONF_DEVICE_TRACKER_STALE_DAYS: 0}, {}),
        ({CONF_DEVICE_TRACKER_CONSIDER_HOME: 86400, CONF_DEVICE_TRACKER_STALE_DAYS: 3650}, {}),
        (
            {CONF_DEVICE_TRACKER_CONSIDER_HOME: 59},
            {CONF_DEVICE_TRACKER_CONSIDER_HOME: "invalid_consider_home"},
        ),
        (
            {CONF_DEVICE_TRACKER_CONSIDER_HOME: 86401},
            {CONF_DEVICE_TRACKER_CONSIDER_HOME: "invalid_consider_home"},
        ),
        (
            {CONF_DEVICE_TRACKER_CONSIDER_HOME: -1},
            {CONF_DEVICE_TRACKER_CONSIDER_HOME: "invalid_consider_home"},
        ),
        ({CONF_DEVICE_TRACKER_STALE_DAYS: -1}, {CONF_DEVICE_TRACKER_STALE_DAYS: "invalid_stale_days"}),
        ({CONF_DEVICE_TRACKER_STALE_DAYS: 3651}, {CONF_DEVICE_TRACKER_STALE_DAYS: "invalid_stale_days"}),
        (
            {CONF_DEVICE_TRACKER_CONSIDER_HOME: 59, CONF_DEVICE_TRACKER_STALE_DAYS: -1},
            {CONF_DEVICE_TRACKER_CONSIDER_HOME: "invalid_consider_home"},
        ),
    ],
    ids=repr,
)
async def test_validation_errors(extra: dict[str, Any], expected: dict[str, str]) -> None:
    """The validation names the field in error; an absent field is not an error."""
    assert await _async_validate_input({**BASE_INPUT, **extra}) == expected


async def test_interval_errors_come_before_the_new_ones() -> None:
    """The refresh interval checks keep their precedence."""
    result = await _async_validate_input(
        {**BASE_INPUT, CONF_UPDATE_INTERVAL_LIVE: 1, CONF_DEVICE_TRACKER_CONSIDER_HOME: 59}
    )

    assert set(result) == {CONF_UPDATE_INTERVAL_LIVE}


# --------------------------------------------------------------------------------------------------
# Translations
# --------------------------------------------------------------------------------------------------

TRANSLATIONS = ("strings.json", "translations/en.json", "translations/fr.json")


def _init_step(name: str) -> dict[str, Any]:
    """Return the init step of the options of a translation file."""
    options = json.loads((COMPONENT_DIR / name).read_text(encoding="utf-8"))["options"]
    return options["step"]["init"]


@pytest.mark.parametrize("name", TRANSLATIONS)
def test_both_fields_have_a_label_and_a_description(name: str) -> None:
    """Each field has a label and a help text, and the two errors have a text."""
    options = json.loads((COMPONENT_DIR / name).read_text(encoding="utf-8"))["options"]
    step = options["step"]["init"]

    for key in NEW_KEYS:
        assert step["data"][key].strip(), key
        assert step["data_description"][key].strip(), key
    assert options["error"]["invalid_consider_home"].strip()
    assert options["error"]["invalid_stale_days"].strip()


@pytest.mark.parametrize("name", TRANSLATIONS)
def test_bounds_in_the_texts_match_the_code(name: str) -> None:
    """The help and the errors quote the bounds and the defaults the code enforces."""
    options = json.loads((COMPONENT_DIR / name).read_text(encoding="utf-8"))["options"]
    step = options["step"]["init"]["data_description"]

    assert "240" in step[CONF_DEVICE_TRACKER_CONSIDER_HOME]
    assert "60" in step[CONF_DEVICE_TRACKER_CONSIDER_HOME]
    assert "60" in options["error"]["invalid_consider_home"]
    assert "86400" in options["error"]["invalid_consider_home"]
    assert "3650" in options["error"]["invalid_stale_days"]
    assert "0" in options["error"]["invalid_stale_days"]


@pytest.mark.parametrize(
    ("name", "never", "forbidden"),
    [
        ("strings.json", "never removed", ("deleted at", "removed at the next reload", "will be removed")),
        ("translations/en.json", "never removed", ("deleted at", "removed at the next reload", "will be removed")),
        (
            "translations/fr.json",
            "jamais supprim",
            ("supprimées au prochain", "seront supprim", "supprimés au prochain"),
        ),
    ],
)
def test_stale_description_promises_no_deletion(name: str, never: str, forbidden: tuple[str, ...]) -> None:
    """The text says nothing is removed by the setting, and the earlier wording about removal at reload is gone."""
    text = _init_step(name)["data_description"][CONF_DEVICE_TRACKER_STALE_DAYS]

    assert never in text
    for phrase in forbidden:
        assert phrase not in text


@pytest.mark.parametrize("name", TRANSLATIONS)
def test_config_flow_has_no_stale_text_leftover(name: str) -> None:
    """The two options are texts of the options form only."""
    config = json.loads((COMPONENT_DIR / name).read_text(encoding="utf-8"))["config"]

    assert "invalid_consider_home" not in config.get("error", {})
    assert "invalid_stale_days" not in config.get("error", {})


def test_translation_texts_are_in_the_three_files() -> None:
    """The three files carry the same set of keys for the two options."""
    keysets = [
        {key for key in _init_step(name)["data"] if key in NEW_KEYS}
        | {key for key in _init_step(name)["data_description"] if key in NEW_KEYS}
        for name in TRANSLATIONS
    ]

    assert keysets[0] == set(NEW_KEYS)
    assert keysets[0] == keysets[1] == keysets[2]
