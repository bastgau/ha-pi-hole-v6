"""Support for getting statistical data from a Pi-hole system."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
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
        key="ads_blocked_today",
        translation_key="ads_blocked_today",
    ),
    SensorEntityDescription(
        key="ads_percentage_blocked_today",
        translation_key="ads_percentage_blocked_today",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="seen_clients",
        translation_key="seen_clients",
    ),
    SensorEntityDescription(
        key="dns_queries_today",
        translation_key="dns_queries_today",
    ),
    SensorEntityDescription(
        key="domains_blocked",
        translation_key="domains_blocked",
    ),
    SensorEntityDescription(
        key="dns_queries_cached",
        translation_key="dns_queries_cached",
    ),
    SensorEntityDescription(
        key="dns_queries_forwarded",
        translation_key="dns_queries_forwarded",
    ),
    SensorEntityDescription(
        key="dns_unique_clients",
        translation_key="dns_unique_clients",
    ),
    SensorEntityDescription(
        key="dns_unique_domains",
        translation_key="dns_unique_domains",
    ),
    SensorEntityDescription(
        key="remaining_until_blocking_mode",
        translation_key="remaining_until_blocking_mode",
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
            case "ads_blocked_today":
                return self.api.cache_summary["queries"]["blocked"]
            case "ads_percentage_blocked_today":
                return self.api.cache_summary["queries"]["percent_blocked"]
            case "seen_clients":
                return self.api.cache_summary["clients"]["total"]
            case "dns_queries_today":
                return self.api.cache_summary["queries"]["total"]
            case "domains_blocked":
                return self.api.cache_summary["gravity"]["domains_being_blocked"]
            case "dns_queries_cached":
                return self.api.cache_summary["queries"]["cached"]
            case "dns_queries_forwarded":
                return self.api.cache_summary["queries"]["forwarded"]
            case "dns_unique_clients":
                return self.api.cache_summary["clients"]["active"]
            case "dns_unique_domains":
                return self.api.cache_summary["queries"]["unique_domains"]
            case "timer":
                value: int | None = self.api.cache_blocking["timer"]
                return value if value is not None else 0

        return ""
