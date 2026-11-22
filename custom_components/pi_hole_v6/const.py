"""Constants for Pi-hole V6."""

from datetime import timedelta

CONFIG_ENTRY_VERSION = 1

CONF_UPDATE_INTERVAL_LIVE = "update_interval_live"
# Key used before the coordinator split, still present in entries created back then.
LEGACY_CONF_UPDATE_INTERVAL = "update_interval"
CONF_UPDATE_INTERVAL_STATS = "update_interval_stats"
# Seconds between two reads of the query log to detect arrivals faster (0 disables it).
CONF_UPDATE_INTERVAL_PRESENCE = "update_interval_presence"
CONF_ENABLE_DEVICE_TRACKER = "enable_device_tracker"
CONF_DEVICE_TRACKER_WHITELIST = "device_tracker_whitelist"
CONF_DEVICE_TRACKER_MAC_LIST = "device_tracker_mac_list"
# Seconds after the last DNS query of a device beyond which it is reported away.
CONF_DEVICE_TRACKER_CONSIDER_HOME = "device_tracker_consider_home"
# Days of inactivity beyond which a device gets no entity created (0 disables it).
CONF_DEVICE_TRACKER_STALE_DAYS = "device_tracker_stale_days"
# Whether the TLS certificate presented by the Pi-hole must be validated.
CONF_VERIFY_SSL = "verify_ssl"
# SHA-256 digest (hexadecimal) of the Pi-hole certificate, confirmed by the user.
CONF_CERT_FINGERPRINT = "cert_fingerprint"

DOMAIN = "pi_hole_v6"
DEFAULT_NAME = "Pi-hole"
DEFAULT_URL = "https://pihole.local:443/api"
DEFAULT_PASSWORD = ""
# Value for new config entries. Entries created before this option existed are migrated to False.
DEFAULT_VERIFY_SSL = True
LEGACY_VERIFY_SSL = False
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
# Written as a literal, not derived from the default live refresh interval, so changing that interval never moves it.
DEFAULT_DEVICE_TRACKER_CONSIDER_HOME = 240
MIN_DEVICE_TRACKER_CONSIDER_HOME = 60
MAX_DEVICE_TRACKER_CONSIDER_HOME = 86400
DEFAULT_DEVICE_TRACKER_STALE_DAYS = 30
MAX_DEVICE_TRACKER_STALE_DAYS = 3650
MAX_NETWORK_DEVICES = 2048
# Addresses per device asked to /network/devices when the presence refresh is enabled (Pi-hole answers 3 by default).
PRESENCE_MAX_ADDRESSES = 10

# 0 disables the presence refresh: the coordinator is not created and the query log is never read.
DEFAULT_UPDATE_INTERVAL_PRESENCE = 0
MIN_UPDATE_INTERVAL_PRESENCE = 15
MAX_UPDATE_INTERVAL_PRESENCE = 300
RECOMMENDED_UPDATE_INTERVAL_PRESENCE = 30
# Seconds before the next try when the query log cannot be used (rights, old version, privacy level).
PRESENCE_RETRY_AFTER_UNUSABLE = 600
# Seconds before the next try when the session is refused (credentials, certificate): never poll the login every cycle.
PRESENCE_RETRY_AFTER_AUTH = 600
# Seconds allowed to the logout of a presence cycle, which holds the shared refresh lock.
PRESENCE_LOGOUT_TIMEOUT = 5
# Seconds before the next try when Pi-hole is overloaded and did not say when to come back.
PRESENCE_RETRY_AFTER_BUSY = 60
# Longest window of the query log read at once, in seconds.
PRESENCE_MAX_WINDOW = 900
# Overlap of two consecutive reads, in seconds: covers a query stored with a slightly older time.
PRESENCE_OVERLAP = 5
# Seconds a query time may be ahead of the clock of Home Assistant (clock skew) before the row is ignored.
PRESENCE_FUTURE_TOLERANCE = 5
# Seconds kept in memory beyond the away delay before an address is forgotten.
PRESENCE_RETENTION_MARGIN = 300

# Kinds of access the account used by the integration can have, deduced from GET /auth/sessions.
ACCESS_MAIN_PASSWORD = "main_password"  # noqa: S105
ACCESS_APP_SUDO = "app_sudo"
ACCESS_APP_NO_SUDO = "app_no_sudo"
ACCESS_RESTRICTED = "restricted"
ACCESS_LEVELS: list[str] = [ACCESS_MAIN_PASSWORD, ACCESS_APP_SUDO, ACCESS_APP_NO_SUDO, ACCESS_RESTRICTED]
# The accesses for which Pi-hole refuses to list the sessions.
ACCESS_WITHOUT_SESSIONS: frozenset[str] = frozenset({ACCESS_APP_NO_SUDO, ACCESS_RESTRICTED})

ATTRIBUTION = "Data provided by your Pi-hole instance API"
