"""Common helper functions for Pi-hole V6 integration."""

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant, State


def find_entity_switch(current_hass: HomeAssistant, key: str, context_name: str) -> Any:
    """Find a switch entity by its key within a given context.

    Args:
        current_hass (HomeAssistant): The Home Assistant instance.
        key (str): The entity description key or group-based composite key to match.
        context_name (str): The name of the Pi-hole instance used to scope the entity list.

    Returns:
        Any: The matching switch entity, or None if not found.

    """

    for entity in current_hass.data.get(f"pi_hole_entities_switch_{context_name}", []):
        if hasattr(entity, "entity_description"):
            if entity.entity_description.key == key:
                return entity

            if entity.entity_description.key == "group" and f"{context_name}/{entity.group_name}" == key:
                return entity

    return None


def find_entity_sensor(current_hass: HomeAssistant, key: str, context_name: str) -> Any:
    """Find a sensor entity by its key within a given context.

    Args:
        current_hass (HomeAssistant): The Home Assistant instance.
        key (str): The entity description key to match.
        context_name (str): The name of the Pi-hole instance used to scope the entity list.

    Returns:
        Any: The matching sensor entity, or None if not found.

    """

    for entity in current_hass.data.get(f"pi_hole_entities_sensor_{context_name}", []):
        if hasattr(entity, "entity_description") and entity.entity_description.key == key:
            return entity

    return None


def calculate_remaining_until_blocking_mode_until_value(entity: Any, remaining_key: str) -> int:
    """Calculate the remaining seconds until the blocking mode is automatically restored.

    Args:
        entity (Any): The entity holding the API cache with remaining dates.
        remaining_key (str): The key used to look up the target datetime in the cache.

    Returns:
        int: The remaining seconds as a positive integer, 0 if the date has passed, or -1 if the key is not present.

    """

    new_value = -1

    if remaining_key in entity.api.cache_remaining_dates:
        new_value = 0

        if entity.api.cache_remaining_dates[remaining_key] > datetime.now(UTC):
            new_value = round((entity.api.cache_remaining_dates[remaining_key] - datetime.now(UTC)).total_seconds())

    return new_value


def get_remaining_dates(hass: HomeAssistant, name: str) -> dict[str, datetime]:
    """Retrieve the remaining dates cache from the first registered switch entity.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        name (str): The name of the Pi-hole instance used to scope the entity list.

    Returns:
        dict[str, datetime]: A dictionary of remaining dates keyed by their identifiers, or an empty dict if unavailable.

    """

    entities = hass.data.get(f"pi_hole_entities_switch_{name}", [])
    entity_model = None

    if len(entities) > 0:
        entity_model = entities[0]

    if entity_model is not None and hass.states.get(entity_model.entity_id) is not None:
        return entity_model.api.cache_remaining_dates

    return {}


async def sensor_update_timer(hass: HomeAssistant, name: str) -> None:
    """Update the remaining blocking mode sensor state on each timer tick.

    Computes the remaining seconds and updates the entity state and attributes accordingly.
    Triggers a full refresh when the timer reaches zero.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        name (str): The name of the Pi-hole instance used to scope the entity lookup.

    """

    entity = find_entity_sensor(hass, "remaining_until_blocking_mode", name)

    if entity is not None and hass.states.get(entity.entity_id) is not None:
        new_value = calculate_remaining_until_blocking_mode_until_value(entity, f"{name}_sensor/global")

        entity_state: State | None = hass.states.get(entity.entity_id)

        if entity_state is None or (entity_state.state == str(0) and new_value < 0):
            return

        state: State | None = hass.states.get(entity.entity_id)

        if state is None:
            return

        existing_attributes = dict(state.attributes)

        until_date_attribute: dict[str, Any] = {}

        request_refresh: bool = False

        if new_value > 0:
            until_date: datetime = entity.api.cache_remaining_dates[f"{name}_sensor/global"].astimezone(
                ZoneInfo(hass.config.time_zone)
            )
            until_date_attribute = {"until_date": until_date}
        else:
            request_refresh = True
            existing_attributes.pop("until_date", None)

        new_attributes = existing_attributes | until_date_attribute
        hass.states.async_set(entity.entity_id, str(new_value), new_attributes)

        if request_refresh is True:
            hass.async_create_task(entity.async_update_ha_state(force_refresh=True))


async def switch_update_timer(hass: HomeAssistant, name: str) -> None:
    """Update all switch entity states related to blocking timers on each timer tick.

    Iterates over all remaining dates, updates attributes and remaining seconds for each
    switch entity, and re-enables blocking when the timer expires.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        name (str): The name of the Pi-hole instance used to scope the entity lookup.

    """

    remaining_dates: dict[str, datetime] = get_remaining_dates(hass, name)

    if len(remaining_dates) == 0:
        return

    remaining_dates_copy = deepcopy(remaining_dates)

    need_refresh = False

    switch_entity: Any = None

    for remaining_key, remaining_date in remaining_dates_copy.items():
        switch_entity = find_entity_switch(hass, remaining_key, name)

        if switch_entity is not None and hass.states.get(switch_entity.entity_id) is not None:
            new_value = calculate_remaining_until_blocking_mode_until_value(switch_entity, remaining_key)

            if new_value < 0:
                return

            state = hass.states.get(switch_entity.entity_id)

            if state is None:
                continue

            existing_attributes = dict(state.attributes)

            until_date_attribute: dict[str, Any] = {}
            remaining_seconds_attribute: dict[str, Any] = {"remaining_seconds": 0}

            if new_value > 0:
                until_date_attribute = {"until_date": remaining_date.astimezone(ZoneInfo(hass.config.time_zone))}
                remaining_seconds_attribute = {"remaining_seconds": new_value}
            else:
                existing_attributes.pop("until_date", None)

                if (
                    remaining_key != f"{name}_sensor/global"
                    and f"{name}/{switch_entity.group_name}" in switch_entity.api.cache_remaining_dates
                ):
                    del switch_entity.api.cache_remaining_dates[f"{name}/{switch_entity.group_name}"]

            new_attributes = existing_attributes | until_date_attribute | remaining_seconds_attribute
            hass.states.async_set(switch_entity.entity_id, switch_entity.state, new_attributes)

            if new_value == 0:
                await switch_entity.async_turn_switch(action="enable", with_update=True)
                need_refresh = True

    if need_refresh is True and switch_entity is not None:
        hass.async_create_task(switch_entity.async_update_ha_state(force_refresh=True))
