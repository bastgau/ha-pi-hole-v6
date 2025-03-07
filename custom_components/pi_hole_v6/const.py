"""Constants for Pi-hole V6."""

from datetime import timedelta

DOMAIN = "pi_hole_v6"
DEFAULT_NAME = "Pi-hole"
DEFAULT_URL = "https://pi.hole:443/api"
DEFAULT_PASSWORD = "xxxxx"

SERVICE_DISABLE = "disable"
SERVICE_DISABLE_ATTR_DURATION = "duration"
SERVICE_ENABLE = "enable"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=300)
