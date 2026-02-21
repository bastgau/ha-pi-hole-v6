"""The pi_hole component."""

from __future__ import annotations

from typing import TYPE_CHECKING

from propcache.api import cached_property

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import ATTRIBUTION, DOMAIN

if TYPE_CHECKING:
    from .api import Api as PiholeAPI


class PiHoleV6Entity(CoordinatorEntity[DataUpdateCoordinator[None]]):
    """Representation of a Pi-hole V6 entity.

    Attributes:
        api (PiholeAPI): The Pi-hole API client instance.

    """

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        api: PiholeAPI,
        coordinator: DataUpdateCoordinator[None],
        name: str,
        server_unique_id: str,
    ) -> None:
        """Initialize a Pi-hole V6 entity.

        Args:
            api (PiholeAPI): The Pi-hole API client instance.
            coordinator (DataUpdateCoordinator[None]): The data update coordinator.
            name (str): The name of the Pi-hole instance.
            server_unique_id (str): A unique identifier for the server entry.

        Returns:
            None

        """
        super().__init__(coordinator)
        self.api = api
        self._name = name
        self._server_unique_id = server_unique_id

    @cached_property
    def device_info(self) -> DeviceInfo:
        """Return the device information of the entity.

        Returns:
            DeviceInfo: The device information object for this entity.

        """

        config_url = self.api.url.split("/api")[0] + "/admin"

        return DeviceInfo(
            identifiers={(DOMAIN, self._server_unique_id)},
            name=self._name,
            manufacturer="Pi-hole",
            configuration_url=config_url,
            model="Pi-hole ",
            sw_version="v6",
        )
