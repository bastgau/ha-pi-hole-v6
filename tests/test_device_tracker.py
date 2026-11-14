"""Check the device information provided by the Pi-hole V6 device tracker entities."""

from unittest.mock import MagicMock

from custom_components.pi_hole_v6.device_tracker import PiHoleV6DeviceTracker

from homeassistant.helpers import device_registry as dr


def test_device_info_links_entity_to_its_mac_device() -> None:
    """The entity declares the MAC connection of its network device, as Home Assistant requires."""
    coordinator = MagicMock()
    coordinator.name = "pihole"
    device = {"hwaddr": "AA:BB:CC:DD:EE:FF", "ips": []}

    entity = PiHoleV6DeviceTracker(MagicMock(), coordinator, "server_id", device)

    # `device_info` is final and returns None before Home Assistant 2026.11, so read the attribute.
    device_info = entity._attr_device_info  # pylint: disable=protected-access
    assert device_info is not None
    assert device_info["connections"] == {(dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:ff")}
