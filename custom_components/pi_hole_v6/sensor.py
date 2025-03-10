"""Support for getting statistical data from a Pi-hole system."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.const import CONF_NAME, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import PiHoleV6ConfigEntry
from .api import API as ClientAPI
from .entity import PiHoleV6Entity

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="ads_blocked",
        translation_key="ads_blocked",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="ads_blocked_percentage",
        translation_key="ads_blocked_percentage",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="seen_clients",
        translation_key="seen_clients",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="total_queries",
        translation_key="total_queries",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="domains_lists",
        translation_key="domains_lists",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="queries_cached",
        translation_key="queries_cached",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="queries_forwarded",
        translation_key="queries_forwarded",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="unique_clients",
        translation_key="unique_clients",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="unique_domains",
        translation_key="unique_domains",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="remaining_until_blocking_mode",
        translation_key="remaining_until_blocking_mode",
        suggested_display_precision=0,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PiHoleV6ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Pi-hole V6 sensor."""
    name = entry.data[CONF_NAME]
    hole_data = entry.runtime_data
    sensors = [
        PiHoleV6Sensor(
            hole_data.api,
            hole_data.coordinator,
            name,
            entry.entry_id,
            description,
        )
        for description in SENSOR_TYPES
    ]
    async_add_entities(sensors, True)


class PiHoleV6Sensor(PiHoleV6Entity, SensorEntity):
    """Representation of a Pi-hole V6 sensor."""

    entity_description: SensorEntityDescription

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
        self.entity_id = f"sensor.{name}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the device."""

        match self.entity_description.key:
            case "ads_blocked":
                return self.api.cache_summary["queries"]["blocked"]
            case "ads_blocked_percentage":
                return self.api.cache_summary["queries"]["percent_blocked"]
            case "seen_clients":
                return self.api.cache_summary["clients"]["total"]
            case "total_queries":
                return self.api.cache_summary["queries"]["total"]
            case "domains_lists":
                return self.api.cache_summary["gravity"]["domains_being_blocked"]
            case "queries_cached":
                return self.api.cache_summary["queries"]["cached"]
            case "queries_forwarded":
                return self.api.cache_summary["queries"]["forwarded"]
            case "unique_clients":
                return self.api.cache_summary["clients"]["active"]
            case "unique_domains":
                return self.api.cache_summary["queries"]["unique_domains"]
            case "remaining_until_blocking_mode":
                value: int | None = self.api.cache_blocking["timer"]
                return value if value is not None else 0

        return ""
