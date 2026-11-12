"""Constants for Pi-hole V6."""

from datetime import timedelta

CONFIG_ENTRY_VERSION = 1

CONF_UPDATE_INTERVAL_LIVE = "update_interval_live"
# Key used before the coordinator split, still present in entries created back then.
LEGACY_CONF_UPDATE_INTERVAL = "update_interval"
CONF_UPDATE_INTERVAL_STATS = "update_interval_stats"
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

MIN_TIME_BETWEEN_UPDATES_LIVE = timedelta(seconds=120)
MIN_TIME_BETWEEN_UPDATES_STATS = timedelta(seconds=300)

# Identifiers of the two data update coordinators.
# "live" drives the entities that must reflect the current state of the Pi-hole instance,
# "stats" drives the cumulative counters and the periodic checks, whose values only matter as a trend.
COORDINATOR_LIVE = "live"
COORDINATOR_STATS = "stats"
DEFAULT_ENABLE_DEVICE_TRACKER = False
DEFAULT_DEVICE_TRACKER_WHITELIST = True
DEFAULT_DEVICE_TRACKER_MAC_LIST = ""
MAX_NETWORK_DEVICES = 2048

# Kinds of access the account used by the integration can have, deduced from GET /auth/sessions.
ACCESS_MAIN_PASSWORD = "main_password"
ACCESS_APP_SUDO = "app_sudo"
ACCESS_APP_NO_SUDO = "app_no_sudo"
ACCESS_RESTRICTED = "restricted"
ACCESS_LEVELS: list[str] = [ACCESS_MAIN_PASSWORD, ACCESS_APP_SUDO, ACCESS_APP_NO_SUDO, ACCESS_RESTRICTED]
# The accesses for which Pi-hole refuses to list the sessions.
ACCESS_WITHOUT_SESSIONS: frozenset[str] = frozenset({ACCESS_APP_NO_SUDO, ACCESS_RESTRICTED})

ATTRIBUTION ="Data provided by your Pi-hole instance API"
