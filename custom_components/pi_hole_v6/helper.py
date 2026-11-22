"""Helper utility functions for the Pi-hole V6 integration."""

from collections.abc import Mapping
import re
from typing import Any

from homeassistant.util import slugify

from .const import CONF_DEVICE_TRACKER_CONSIDER_HOME, DEFAULT_DEVICE_TRACKER_CONSIDER_HOME


def create_entity_id_name(input_string: str) -> str:
    """Create a normalized entity ID name from a raw input string.

    Args:
        input_string (str): The raw input string to transform.

    Returns:
        str: The normalized entity ID name.

    """

    # Split the string at the first "."
    first_part, second_part = input_string.split(".", 1)

    # Replace non-alphanumeric characters (except "_") with "_" in both parts
    first_part = first_part.lower()
    second_part = slugify(second_part)

    # Recombine with the first "." preserved
    return f"{first_part}.{second_part}"


def parse_mac_list(raw_list: str) -> set[str]:
    """Parse a raw MAC address list into a normalized set.

    Accepts MAC addresses separated by commas, newlines, or both. Each address
    is lowercased and stripped of surrounding whitespace before being added
    to the result set. Empty entries are ignored.

    Args:
        raw_list (str): The raw MAC address list as entered by the user.

    Returns:
        set[str]: A set of normalized (lowercase, trimmed) MAC addresses.

    """
    return {mac.strip().lower() for mac in re.split(r"[,\n]", raw_list) if mac.strip()}


def get_consider_home(data: Mapping[str, Any] | None) -> float:
    """Read the away delay of the device tracker from the data of a config entry.

    Args:
        data (Mapping[str, Any] | None): The data of the config entry, None when there is none.

    Returns:
        float: The away delay in seconds. The default one when the option is absent or is not a number.

    """
    value: Any = data.get(CONF_DEVICE_TRACKER_CONSIDER_HOME, DEFAULT_DEVICE_TRACKER_CONSIDER_HOME) if data else None

    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return float(DEFAULT_DEVICE_TRACKER_CONSIDER_HOME)

    return float(value)
