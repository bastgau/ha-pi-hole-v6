"""Support for device tracking via Pi-hole network devices."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from homeassistant.components.device_tracker.const import SourceType
from homeassistant.components.device_tracker.entity import ScannerEntity
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import (
    ATTRIBUTION,
    CONF_DEVICE_TRACKER_MAC_LIST,
    CONF_DEVICE_TRACKER_WHITELIST,
    CONF_ENABLE_DEVICE_TRACKER,
    DEFAULT_DEVICE_TRACKER_MAC_LIST,
    DEFAULT_DEVICE_TRACKER_WHITELIST,
    DEFAULT_ENABLE_DEVICE_TRACKER,
    DOMAIN,
    MIN_TIME_BETWEEN_UPDATES,
)
from .helper import create_entity_id_name, parse_mac_list

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import Event, HomeAssistant
    from homeassistant.helpers.device_registry import EventDeviceRegistryUpdatedData
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import PiHoleV6ConfigEntry
    from .api import Api as PiholeAPI


def _build_mac_filter(entry: PiHoleV6ConfigEntry) -> Callable[[str], bool]:
    """Build a predicate that decides whether a MAC address should be tracked.

    Reads the whitelist/blacklist mode and MAC list from the config entry options.
    An empty list disables filtering entirely, regardless of the selected mode.

    Args:
        entry (PiHoleV6ConfigEntry): The config entry providing the filter options.

    Returns:
        Callable[[str], bool]: A predicate returning True if the given (lowercase)
            MAC address should be tracked.

    """
    mac_list = parse_mac_list(entry.data.get(CONF_DEVICE_TRACKER_MAC_LIST, DEFAULT_DEVICE_TRACKER_MAC_LIST))

    if not mac_list:
        return lambda _mac: True

    is_whitelist = entry.data.get(CONF_DEVICE_TRACKER_WHITELIST, DEFAULT_DEVICE_TRACKER_WHITELIST)

    if is_whitelist:
        return lambda mac: mac in mac_list
    return lambda mac: mac not in mac_list


def _purge_network_devices(
    hass: HomeAssistant,
    entry: PiHoleV6ConfigEntry,
    is_mac_allowed: Callable[[str], bool] = lambda _mac: False,
) -> None:
    """Remove device_tracker entities and their network devices from the registries.

    Removes any network device (and its device_tracker entity) already present in the
    registries for this config entry whose MAC address is rejected by `is_mac_allowed`.
    This also catches devices that are no longer part of the current Pi-hole cache.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        entry (PiHoleV6ConfigEntry): The config entry owning the entities and devices.
        is_mac_allowed (Callable[[str], bool]): Predicate deciding whether a MAC address
            should still be tracked. Defaults to always False, removing every network
            device (used when device tracking is fully disabled).

    Returns:
        None

    """
    entity_registry = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        if entity_entry.domain != "device_tracker":
            continue
        mac = entity_entry.unique_id.rsplit("/", 1)[-1]
        if not is_mac_allowed(mac):
            entity_registry.async_remove(entity_entry.entity_id)

    device_registry = dr.async_get(hass)
    for device_entry in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        device_macs = {mac for conn_type, mac in device_entry.connections if conn_type == dr.CONNECTION_NETWORK_MAC}
        if device_macs and not any(is_mac_allowed(mac) for mac in device_macs):
            device_registry.async_update_device(device_entry.id, remove_config_entry_id=entry.entry_id)


def _device_display_name(device: dict[str, Any]) -> str:
    """Return the best display name for a network device.

    Picks the first non-null hostname from the device's IP list, falling
    back to the MAC address when no hostname is known.

    Args:
        device (dict[str, Any]): The network device data dict.

    Returns:
        str: The hostname if found, otherwise the MAC address.

    """
    for ip_info in device["ips"]:
        name: str | None = ip_info.get("name")
        if name:
            return name
    return device["hwaddr"].lower()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PiHoleV6ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Pi-hole V6 device tracker from network devices.

    Creates a device tracker entity for each network device known to Pi-hole.
    New devices appearing in subsequent coordinator updates are automatically added.
    If network device tracking is disabled, any previously created device tracker
    entities and their associated network device entries are removed from their
    respective registries.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        entry (PiHoleV6ConfigEntry): The config entry providing runtime data.
        async_add_entities (AddConfigEntryEntitiesCallback): Callback to register new entities.

    Returns:
        None

    """
    if not entry.data.get(CONF_ENABLE_DEVICE_TRACKER, DEFAULT_ENABLE_DEVICE_TRACKER):
        _purge_network_devices(hass, entry)
        return

    hole_data = entry.runtime_data
    server_unique_id = entry.entry_id

    device_registry = dr.async_get(hass)

    _purge_network_devices(hass, entry, _build_mac_filter(entry))

    tracked_macs: set[str] = set()
    tracked_entities: dict[str, PiHoleV6DeviceTracker] = {}
    _add_lock = asyncio.Lock()

    async def _async_add_remove_trackers() -> None:
        """Add new devices and remove entities excluded by the current MAC filter.

        Devices that Pi-hole simply stops reporting keep their entity, which then
        naturally reports as not_home. Only devices rejected by the whitelist or
        blacklist filter are actively removed.

        Returns:
            None

        """
        async with _add_lock:
            is_mac_allowed = _build_mac_filter(entry)

            new_entities: list[PiHoleV6DeviceTracker] = []

            for device in hole_data.api.cache_network_devices:
                mac: str = device["hwaddr"].lower()

                if not is_mac_allowed(mac):
                    continue

                if mac not in tracked_macs:
                    tracked_macs.add(mac)

                    device_registry.async_get_or_create(
                        config_entry_id=entry.entry_id,
                        connections={(dr.CONNECTION_NETWORK_MAC, mac)},
                        manufacturer=device.get("macVendor") or None,
                        model="Network device",
                        name=_device_display_name(device),
                        via_device=(DOMAIN, server_unique_id),
                    )

                    entity = PiHoleV6DeviceTracker(
                        hole_data.api,
                        hole_data.coordinator,
                        server_unique_id,
                        device,
                    )
                    new_entities.append(entity)
                    tracked_entities[mac] = entity

            # A device excluded by the current filter is removed even if Pi-hole still
            # reports it. A device simply absent from Pi-hole's response keeps its
            # entity, which naturally reports as not_home via ScannerEntity.
            excluded: list[str] = [mac for mac in tracked_macs if not is_mac_allowed(mac)]

            for mac in excluded:
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

    @callback
    def _forget_manually_removed_device(event: Event[EventDeviceRegistryUpdatedData]) -> None:
        """Forget a manually removed network device so it can be recreated later.

        When the user removes a network device from the UI, it disappears from
        `tracked_macs`/`tracked_entities` bookkeeping so that, if Pi-hole reports it
        again on a later refresh, a fresh entity is created for it instead of the
        removal being silently undone by the next tracker cycle.

        Args:
            event (Event[EventDeviceRegistryUpdatedData]): The device registry update event.

        Returns:
            None

        """
        if event.data["action"] != "remove":
            return

        for conn_type, mac in event.data["device"]["connections"]:
            if conn_type == dr.CONNECTION_NETWORK_MAC:
                tracked_macs.discard(mac)
                tracked_entities.pop(mac, None)

    entry.async_on_unload(hass.bus.async_listen(dr.EVENT_DEVICE_REGISTRY_UPDATED, _forget_manually_removed_device))


class PiHoleV6DeviceTracker(  # pyright: ignore[reportIncompatibleVariableOverride]
    CoordinatorEntity[DataUpdateCoordinator[None]],
    ScannerEntity,
):
    """Representation of a device tracked via Pi-hole network data.

    Each tracked device gets its own entry in the Home Assistant device registry,
    identified by its MAC address and created by `async_setup_entry`. This entity
    auto-attaches to that device registry entry via its `mac_address` property.

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
        self._hostname: str | None = None
        self._ip_address: str | None = None

        self._attr_unique_id = f"{server_unique_id}/{self._mac}"

        name: str = coordinator.name
        raw_name: str = f"device_tracker.{name}_{self._mac.replace(':', '_')}"
        self.entity_id = create_entity_id_name(raw_name)

    def _find_device(self) -> dict[str, Any] | None:
        """Find the current network device entry for this MAC address.

        Updates cached hostname and IP address when found.

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

                return device
        return None

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
    def ip_address(self) -> str | None:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Return the most recently seen IP address from the network device data.

        Returns:
            str | None: The IP address if found, None otherwise.

        """
        self._find_device()
        return self._ip_address

    @property
    def mac_address(self) -> str:  # pyright: ignore[reportIncompatibleVariableOverride]
        """Return the MAC address of the tracked device.

        Returns:
            str: The MAC address in lowercase colon-separated format.

        """
        return self._mac

    @property
    def hostname(self) -> str | None:  # pyright: ignore[reportIncompatibleVariableOverride]
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
        if device.get("macVendor"):
            attrs["manufacturer"] = device["macVendor"]
        if device.get("interface"):
            attrs["interface"] = device["interface"]
        if device.get("numQueries"):
            attrs["num_queries"] = device["numQueries"]
        if device.get("firstSeen"):
            attrs["first_seen"] = datetime.fromtimestamp(device["firstSeen"], tz=UTC).isoformat()
        if device.get("lastQuery"):
            attrs["last_query"] = datetime.fromtimestamp(device["lastQuery"], tz=UTC).isoformat()

        return attrs
