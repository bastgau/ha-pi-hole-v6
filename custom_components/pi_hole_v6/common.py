"""..."""

from copy import deepcopy
from datetime import datetime
from typing import Any, Dict
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant


def find_entity_switch(current_hass: HomeAssistant, key: str, context_name: str) -> Any:
    """..."""

    for entity in current_hass.data.get(f"pi_hole_entities_switch_{context_name}", []):
        if hasattr(entity, "entity_description"):
            if entity.entity_description.key == key:
                return entity

            if entity.entity_description.key == "group" and f"{context_name}/{entity.group_name}" == key:
                return entity

    return None


def find_entity_sensor(current_hass: HomeAssistant, key: str, context_name: str) -> Any:
    """..."""

    for entity in current_hass.data.get(f"pi_hole_entities_sensor_{context_name}", []):
        if hasattr(entity, "entity_description") and entity.entity_description.key == key:
            return entity


def calculate_remaining_until_blocking_mode_until_value(entity: Any, remaining_key: str) -> int:
    """..."""

    new_value = -1

    if remaining_key in entity.api.cache_remaining_dates:
        new_value = 0

        if entity.api.cache_remaining_dates[remaining_key] > datetime.now():
            new_value = round((entity.api.cache_remaining_dates[remaining_key] - datetime.now()).total_seconds())

    return new_value


def get_remaining_dates(hass: HomeAssistant, name: str) -> Dict[str, datetime]:
    """..."""

    entities = hass.data.get(f"pi_hole_entities_switch_{name}", [])
    entity_model = None

    if len(entities) > 0:
        entity_model = entities[0]

    if entity_model is not None and hass.states.get(entity_model.entity_id) is not None:
        return entity_model.api.cache_remaining_dates

    return {}


async def sensor_update_timer(hass: HomeAssistant, now: Any, name: str) -> None:
    """..."""

    entity = find_entity_sensor(hass, "remaining_until_blocking_mode", name)

    if entity is not None and hass.states.get(entity.entity_id) is not None:
        new_value = calculate_remaining_until_blocking_mode_until_value(entity, f"{name}_sensor/global")

        if new_value < 0:
            return None

        state = hass.states.get(entity.entity_id)
        existing_attributes = dict(state.attributes)

        until_date_attribute: Dict[str, Any] = {}

        request_refresh: bool = False

        if new_value > 0:
            paris_tz: ZoneInfo = ZoneInfo("Europe/Paris")
            until_date: datetime = entity.api.cache_remaining_dates[f"{name}_sensor/global"].astimezone(paris_tz)
            until_date_attribute = {"until_date": until_date}
        else:
            request_refresh = True
            if "until_date" in existing_attributes:
                del existing_attributes["until_date"]

        new_attributes = existing_attributes | until_date_attribute
        hass.states.async_set(entity.entity_id, new_value, new_attributes)

        if request_refresh is True:
            hass.async_create_task(entity.async_update_ha_state(force_refresh=True))


async def switch_update_timer(hass: HomeAssistant, now: Any, name: str) -> None:
    """..."""

    remaining_dates: Dict[str, datetime] = get_remaining_dates(hass, name)

    if len(remaining_dates) == 0:
        return

    remaining_dates_copy = deepcopy(remaining_dates)

    need_refresh = False

    for remaining_key, remaining_date in remaining_dates_copy.items():
        switch_entity = find_entity_switch(hass, remaining_key, name)

        if switch_entity is not None and hass.states.get(switch_entity.entity_id) is not None:
            new_value = calculate_remaining_until_blocking_mode_until_value(switch_entity, remaining_key)

            if new_value < 0:
                return None

            state = hass.states.get(switch_entity.entity_id)
            existing_attributes = dict(state.attributes)

            new_state_value: str = switch_entity.state

            until_date_attribute: Dict[str, Any] = {}
            remaining_seconds_attribute: Dict[str, Any] = {"remaining_seconds": 0}

            if new_value > 0:
                paris_tz: ZoneInfo = ZoneInfo("Europe/Paris")
                until_date: datetime = remaining_date.astimezone(paris_tz)
                until_date_attribute = {"until_date": until_date}
                remaining_seconds_attribute = {"remaining_seconds": new_value}
            else:
                if "until_date" in existing_attributes:
                    del existing_attributes["until_date"]

                if (
                    remaining_key != f"{name}_sensor/global"
                    and f"{name}/{switch_entity.group_name}" in switch_entity.api.cache_remaining_dates
                ):
                    del switch_entity.api.cache_remaining_dates[f"{name}/{switch_entity.group_name}"]

            new_attributes = existing_attributes | until_date_attribute | remaining_seconds_attribute
            hass.states.async_set(switch_entity.entity_id, new_state_value, new_attributes)

            if new_value == 0:
                await switch_entity.async_turn_switch(action="enable", with_update=True)
                need_refresh = True

    if need_refresh is True:
        hass.async_create_task(switch_entity.async_update_ha_state(force_refresh=True))
