"""Support for getting status from a Pi-hole V6 system."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import PiHoleV6ConfigEntry
from .api import API as PiholeAPI
from .entity import PiHoleV6Entity


@dataclass(frozen=True, kw_only=True)
class PiHoleV6BinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes PiHole binary sensor entity."""

    state_value: Callable[[PiholeAPI], bool]
    extra_value: Callable[[PiholeAPI], dict[str, Any] | None] = lambda PiholeAPI: None


BINARY_SENSOR_TYPES: tuple[PiHoleV6BinarySensorEntityDescription, ...] = (
    PiHoleV6BinarySensorEntityDescription(
        key="status",
        device_class=BinarySensorDeviceClass.RUNNING,
        translation_key="status",
        state_value=lambda ClientAPI: bool(ClientAPI.cache_blocking.get("blocking", None) == "enabled"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PiHoleV6ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Pi-hole V6 binary sensor."""
    name = entry.data[CONF_NAME]
    hole_data = entry.runtime_data
    binary_sensors = [
        PiHoleV6BinarySensor(
            hole_data.api,
            hole_data.coordinator,
            name,
            entry.entry_id,
            description,
        )
        for description in BINARY_SENSOR_TYPES
    ]
    async_add_entities(binary_sensors, True)


class PiHoleV6BinarySensor(PiHoleV6Entity, BinarySensorEntity):
    """Representation of a Pi-hole V6 binary sensor."""

    entity_description: PiHoleV6BinarySensorEntityDescription

    def __init__(
        self,
        api: PiholeAPI,
        coordinator: DataUpdateCoordinator[None],
        name: str,
        server_unique_id: str,
        description: PiHoleV6BinarySensorEntityDescription,
    ) -> None:
        """Initialize a Pi-hole V6 sensor."""
        super().__init__(api, coordinator, name, server_unique_id)
        self.entity_description = description
        self._attr_unique_id = f"{self._server_unique_id}/{description.key}"
        self.entity_id = f"binary_sensor.{name}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return if the service is on."""
        return self.entity_description.state_value(self.api)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the Pi-hole V6."""

        if self.entity_description.key == "status":
            url: str = self.api.url.split("/api")[0] + "/admin"

            core_version: str = self.api.cache_padd["version"]["core"]["local"]["version"]
            web_version: str = self.api.cache_padd["version"]["web"]["local"]["version"]
            ftl_version: str = self.api.cache_padd["version"]["ftl"]["local"]["version"]

            docker_info: dict[str, Any] = {}

            if self.api.cache_padd["version"]["docker"]["local"] is not None:
                docker_version: str = self.api.cache_padd["version"]["docker"]["local"]
                docker_info = {
                    "Docker version": docker_version,
                }

            info: dict[str, Any] = {
                "Core version": core_version,
                "Web interface version": web_version,
                "FTL version": ftl_version,
            } | docker_info

            return {"URL instance": url} | {k: info[k] for k in sorted(info)}

        return None
