"""The output limit which can be set in the APsystems local API integration."""

from __future__ import annotations

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.const import CONF_NAME, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import PiHoleV6ConfigEntry
from .api import API as ClientAPI
from .entity import PiHoleV6Entity

SENSOR_TYPES: tuple[NumberEntityDescription, ...] = (
    NumberEntityDescription(
        key="default_blocking_time",
        translation_key="default_blocking_time",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PiHoleV6ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    name = entry.data[CONF_NAME]
    hole_data = entry.runtime_data
    sensors = [
        PiHoleV6Number(
            hole_data.api,
            hole_data.coordinator,
            name,
            entry.entry_id,
            description,
        )
        for description in SENSOR_TYPES
    ]
    async_add_entities(sensors, True)


class PiHoleV6Number(PiHoleV6Entity, NumberEntity):
    """Base sensor to be used with description."""

    _attr_native_step = 1
    _attr_device_class = NumberDeviceClass.DURATION
    _attr_mode = NumberMode.AUTO
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_translation_key = "max_output"

    def __init__(
        self,
        api: ClientAPI,
        coordinator: DataUpdateCoordinator[None],
        name: str,
        server_unique_id: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize a Pi-hole V6 sensor."""
        super().__init__(api, coordinator, name, server_unique_id)
        self.entity_description = description
        self._attr_unique_id = f"{self._server_unique_id}/{description.key}"
        self.entity_id = f"number.{name}_{description.key}"

    async def async_set_native_value(self, value: float) -> None:
        """Set the desired output power."""
        self._attr_native_value = value
