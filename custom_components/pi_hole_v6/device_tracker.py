"""Support for device tracking via Pi-hole network devices."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from homeassistant.components.device_tracker import ScannerEntity, SourceType
from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import ATTRIBUTION, DOMAIN, MIN_TIME_BETWEEN_UPDATES
from .helper import create_entity_id_name

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import PiHoleV6ConfigEntry
    from .api import Api as PiholeAPI

async def async_setup_entry(
    hass: HomeAssistant,
    entry: PiHoleV6ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Pi-hole V6 device tracker from network devices.

    Creates a device tracker entity for each network device known to Pi-hole.
    New devices appearing in subsequent coordinator updates are automatically added.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        entry (PiHoleV6ConfigEntry): The config entry providing runtime data.
        async_add_entities (AddConfigEntryEntitiesCallback): Callback to register new entities.

    Returns:
        None

    """
    hole_data = entry.runtime_data
    server_unique_id = entry.entry_id

    tracked_macs: set[str] = set()
    tracked_entities: dict[str, PiHoleV6DeviceTracker] = {}
    _add_lock = asyncio.Lock()

    async def _async_add_remove_trackers() -> None:
        """Add new and remove stale device tracker entities.

        Returns:
            None

        """
        async with _add_lock:
            new_entities: list[PiHoleV6DeviceTracker] = []
            stale: list[str] = []
            seen_macs: set[str] = set()

            for device in hole_data.api.cache_network_devices:
                mac: str = device["hwaddr"].lower()
                seen_macs.add(mac)

                if mac not in tracked_macs:
                    tracked_macs.add(mac)
                    entity = PiHoleV6DeviceTracker(
                        hole_data.api,
                        hole_data.coordinator,
                        server_unique_id,
                        device,
                    )
                    new_entities.append(entity)
                    tracked_entities[mac] = entity

            # Remove entities for devices no longer in the cache
            stale.extend(mac for mac in tracked_macs if mac not in seen_macs)

            for mac in stale:
                if mac in tracked_entities:
                    await tracked_entities.pop(mac).async_remove()
                tracked_macs.discard(mac)

            if new_entities:
                async_add_entities(new_entities, update_before_add=True)

    await _async_add_remove_trackers()

    @callback
    def _schedule_add_remove_trackers() -> None:
        """Schedule adding and removing trackers when coordinator updates.

        Returns:
            None

        """
        hass.async_create_task(_async_add_remove_trackers())

    entry.async_on_unload(hole_data.coordinator.async_add_listener(_schedule_add_remove_trackers))


class PiHoleV6DeviceTracker(CoordinatorEntity[DataUpdateCoordinator[None]], ScannerEntity):
    """Representation of a device tracked via Pi-hole network data.

    Each instance creates its own device in the Home Assistant device registry,
    identified by the MAC address from the network device.

    Attributes:
        api (PiholeAPI): The Pi-hole API client instance.

    """

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    _attr_translation_key = "network_device"

    def __init__(
        self,
        api: PiholeAPI,
        coordinator: DataUpdateCoordinator[None],
        server_unique_id: str,
        device: dict[str, Any],
    ) -> None:
        """Initialize a Pi-hole V6 device tracker entity.

        Args:
            api (PiholeAPI): The Pi-hole API client instance.
            coordinator (DataUpdateCoordinator[None]): The data update coordinator.
            server_unique_id (str): A unique identifier for the server entry.
            device (dict[str, Any]): The network device data dict containing hwaddr,
                macVendor, ips, lastQuery, and other fields.

        Returns:
            None

        """
        super().__init__(coordinator)
        self.api = api

        self._mac: str = device["hwaddr"].lower()
        self._server_unique_id: str = server_unique_id

        self._hostname: str | None = None
        self._ip_address: str | None = None
        self._manufacturer: str | None = None

        self._attr_unique_id = f"{server_unique_id}/{self._mac}"

        name: str = coordinator.name
        raw_name: str = f"device_tracker.{name}_{self._mac.replace(':', '_')}"
        self.entity_id = create_entity_id_name(raw_name)

    def _find_device(self) -> dict[str, Any] | None:
        """Find the current network device entry for this MAC address.

        Updates cached hostname, IP address, and manufacturer when found.

        Returns:
            dict[str, Any] | None: The device dict if found, None otherwise.

        """
        for device in self.api.cache_network_devices:
            if device["hwaddr"].lower() == self._mac:
                # Pick the first non-null hostname from the IP list
                for ip_info in device["ips"]:
                    name: str | None = ip_info.get("name")
                    if name:
                        self._hostname = name
                        break

                # Pick the most recently seen IP address
                best_ip: str | None = None
                best_seen: int = 0
                for ip_info in device["ips"]:
                    seen: int = ip_info.get("lastSeen", 0)
                    if seen > best_seen:
                        best_seen = seen
                        best_ip = ip_info["ip"]
                self._ip_address = best_ip

                self._manufacturer = device.get("macVendor") or None

                return device
        return None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this tracked device.

        Creates a unique device in the HA device registry per MAC address,
        linked to the Pi-hole server device via `via_device`.

        Returns:
            DeviceInfo: The device information for this tracked client.

        """
        self._find_device()
        device_name: str = self._hostname or self._mac

        return DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, self._mac)},
            identifiers={(DOMAIN, self._mac)},
            manufacturer=self._manufacturer,
            name=device_name,
            via_device=(DOMAIN, self._server_unique_id),
        )

    @property
    def name(self) -> str | None:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Return the name of the entity within the device.

        Returns None so the entity uses the device name directly,
        avoiding duplication like "berlin berlin".

        Returns:
            str | None: None, letting HA use the device name.

        """
        return None

    @property
    def source_type(self) -> SourceType:
        """Return the source type of the device tracker.

        Returns:
            SourceType: Always ROUTER since the data comes from Pi-hole.

        """
        return SourceType.ROUTER

    @property
    def is_connected(self) -> bool:
        """Return True if the device was active recently.

        A device is considered connected if its last query timestamp is
        within the configured threshold.

        Returns:
            bool: True if the device has recent activity, False otherwise.

        """
        device = self._find_device()
        if not device:
            return False
        last_query = datetime.fromtimestamp(device["lastQuery"], tz=UTC)
        return (datetime.now(UTC) - last_query).total_seconds() <= 2 * MIN_TIME_BETWEEN_UPDATES.total_seconds()

    @property
    def ip_address(self) -> str | None:
        """Return the most recently seen IP address from the network device data.

        Returns:
            str | None: The IP address if found, None otherwise.

        """
        self._find_device()
        return self._ip_address

    @property
    def mac_address(self) -> str:
        """Return the MAC address of the tracked device.

        Returns:
            str: The MAC address in lowercase colon-separated format.

        """
        return self._mac

    @property
    def hostname(self) -> str | None:
        """Return the hostname of the tracked device.

        Returns:
            str | None: The hostname from the network device data, or None if unknown.

        """
        self._find_device()
        return self._hostname

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Return extra state attributes for the device tracker.

        Includes manufacturer, interface, query count, and timestamps from the
        network device data. IP, MAC, and hostname are surfaced by ScannerEntity.

        Returns:
            dict[str, Any] | None: A dictionary of extra attributes, or None if the
                device is not found in the current network data.

        """
        device = self._find_device()
        if not device:
            return None

        attrs: dict[str, Any] = {}
        if self._manufacturer:
            attrs["manufacturer"] = self._manufacturer
        if device.get("interface"):
            attrs["interface"] = device["interface"]
        if device.get("numQueries"):
            attrs["num_queries"] = device["numQueries"]
        if device.get("firstSeen"):
            attrs["first_seen"] = datetime.fromtimestamp(device["firstSeen"], tz=UTC).isoformat()
        if device.get("lastQuery"):
            attrs["last_query"] = datetime.fromtimestamp(device["lastQuery"], tz=UTC).isoformat()

        return attrs
