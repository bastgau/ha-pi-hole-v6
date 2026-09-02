"""Constants for Pi-hole V6."""

from datetime import timedelta

CONFIG_ENTRY_VERSION = 1

CONF_UPDATE_INTERVAL = "update_interval"
CONF_UPDATE_INTERVAL_DETAILS = "update_interval_details"
CONF_ENABLE_DEVICE_TRACKER = "enable_device_tracker"
CONF_DEVICE_TRACKER_WHITELIST = "device_tracker_whitelist"
CONF_DEVICE_TRACKER_MAC_LIST = "device_tracker_mac_list"

DOMAIN = "pi_hole_v6"
DEFAULT_NAME = "Pi-hole"
DEFAULT_URL = "https://pihole.local:443/api"
DEFAULT_PASSWORD = ""
EXAMPLE_URL = "https://pihole.local:443/api"

SERVICE_DISABLE = "disable"
SERVICE_DISABLE_ATTR_DURATION = "duration"
SERVICE_ENABLE = "enable"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=300)
MIN_TIME_BETWEEN_UPDATES_DETAILS = timedelta(seconds=3600)

# Identifiers of the two data update coordinators.
# "live" drives the fast moving data (activity summary, PADD, blocking status, groups),
# "details" drives the slow moving inventories (clients, leases, sessions, FTL messages, network devices).
COORDINATOR_LIVE = "live"
COORDINATOR_DETAILS = "details"
DEFAULT_ENABLE_DEVICE_TRACKER = False
DEFAULT_DEVICE_TRACKER_WHITELIST = True
DEFAULT_DEVICE_TRACKER_MAC_LIST = ""
MAX_NETWORK_DEVICES = 2048

ATTRIBUTION = "Data provided by your Pi-hole instance API"
