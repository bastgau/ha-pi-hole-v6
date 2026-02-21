"""Support for getting status from a Pi-hole V6 system."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

from .entity import PiHoleV6Entity
from .helper import create_entity_id_name

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

    from . import PiHoleV6ConfigEntry
    from .api import Api as PiholeAPI

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PiHoleV6BinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes PiHole binary sensor entity.

    Attributes:
        state_value (Callable[[PiholeAPI], Any]): A callable that takes the API client
            and returns the current state value of the sensor.

    """

    state_value: Callable[[PiholeAPI], Any]


BINARY_SENSOR_TYPES: tuple[PiHoleV6BinarySensorEntityDescription, ...] = (
    PiHoleV6BinarySensorEntityDescription(
        key="status",
        device_class=BinarySensorDeviceClass.RUNNING,
        translation_key="status",
        state_value=lambda client_api: bool(client_api.cache_blocking.get("blocking", None) == "enabled"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 # pylint: disable=unused-argument
    entry: PiHoleV6ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Pi-hole V6 binary sensor.

    Args:
        hass (HomeAssistant): The Home Assistant instance (unused).
        entry (PiHoleV6ConfigEntry): The config entry providing runtime data.
        async_add_entities (AddConfigEntryEntitiesCallback): Callback to register new entities.

    Returns:
        None

    """
    hole_data = entry.runtime_data
    binary_sensors = [
        PiHoleV6BinarySensor(
            hole_data.api,
            hole_data.coordinator,
            entry.entry_id,
            description,
        )
        for description in BINARY_SENSOR_TYPES
    ]
    async_add_entities(binary_sensors, update_before_add=True)


class PiHoleV6BinarySensor(PiHoleV6Entity, BinarySensorEntity):
    """Representation of a Pi-hole V6 binary sensor."""

    entity_description: PiHoleV6BinarySensorEntityDescription

    def __init__(
        self,
        api: PiholeAPI,
        coordinator: DataUpdateCoordinator[None],
        server_unique_id: str,
        description: PiHoleV6BinarySensorEntityDescription,
    ) -> None:
        """Initialize a Pi-hole V6 sensor.

        Args:
            api (PiholeAPI): The Pi-hole API client instance.
            coordinator (DataUpdateCoordinator[None]): The data update coordinator.
            server_unique_id (str): A unique identifier for the server entry.
            description (PiHoleV6BinarySensorEntityDescription): The entity description.

        Returns:
            None

        """

        name: str = coordinator.name
        super().__init__(api, coordinator, name, server_unique_id)
        self.entity_description = description  # pyright: ignore[reportIncompatibleVariableOverride]
        self._attr_unique_id = f"{self._server_unique_id}/{description.key}"

        raw_name: str = f"binary_sensor.{name}_{description.key}"
        self.entity_id = create_entity_id_name(raw_name)

    @property
    def is_on(self) -> bool:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Return if the service is on.

        Returns:
            bool: True if the blocking service is enabled, False otherwise.

        """
        return self.entity_description.state_value(self.api)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Return the state attributes of the Pi-hole V6.

        Returns:
            dict[str, Any] | None: A dictionary of extra attributes, or None if not applicable.

        """

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
