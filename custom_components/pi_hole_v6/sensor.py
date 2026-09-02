"""Support for getting statistical data from a Pi-hole system."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CONF_NAME, PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.helpers.event import async_track_time_interval

from .common import sensor_update_timer
from .const import COORDINATOR_DETAILS, COORDINATOR_LIVE
from .entity import PiHoleV6Entity
from .helper import create_entity_id_name

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
    from homeassistant.helpers.typing import StateType
    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

    from . import PiHoleV6ConfigEntry
    from .api import Api as ClientAPI

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PiHoleV6SensorEntityDescription(SensorEntityDescription):
    """Describes a Pi-hole V6 sensor entity.

    Attributes:
        coordinator_key (str): The coordinator feeding this sensor, either COORDINATOR_LIVE for the data
            that must feel responsive or COORDINATOR_DETAILS for the data refreshed at a slower pace.
        follow_every_coordinator (bool): Whether the sensor also has to be written when a coordinator it is
            not attached to completes a refresh, used by the sensors reporting on every coordinator.

    """

    coordinator_key: str = COORDINATOR_LIVE
    follow_every_coordinator: bool = False


SENSOR_TYPES: tuple[PiHoleV6SensorEntityDescription, ...] = (
    PiHoleV6SensorEntityDescription(
        key="remaining_until_blocking_mode",
        translation_key="remaining_until_blocking_mode",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        suggested_display_precision=0,
    ),
    PiHoleV6SensorEntityDescription(
        key="ads_blocked_today",
        coordinator_key=COORDINATOR_DETAILS,
        translation_key="ads_blocked_today",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PiHoleV6SensorEntityDescription(
        key="ads_percentage_blocked_today",
        coordinator_key=COORDINATOR_DETAILS,
        translation_key="ads_percentage_blocked_today",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PiHoleV6SensorEntityDescription(
        key="seen_clients",
        coordinator_key=COORDINATOR_DETAILS,
        translation_key="seen_clients",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PiHoleV6SensorEntityDescription(
        key="dns_queries_today",
        coordinator_key=COORDINATOR_DETAILS,
        translation_key="dns_queries_today",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PiHoleV6SensorEntityDescription(
        key="domains_blocked",
        coordinator_key=COORDINATOR_DETAILS,
        translation_key="domains_blocked",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PiHoleV6SensorEntityDescription(
        key="dns_queries_cached",
        coordinator_key=COORDINATOR_DETAILS,
        translation_key="dns_queries_cached",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PiHoleV6SensorEntityDescription(
        key="dns_queries_forwarded",
        coordinator_key=COORDINATOR_DETAILS,
        translation_key="dns_queries_forwarded",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PiHoleV6SensorEntityDescription(
        key="dns_queries_frequency",
        coordinator_key=COORDINATOR_DETAILS,
        translation_key="dns_queries_frequency",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    PiHoleV6SensorEntityDescription(
        key="dns_unique_clients",
        coordinator_key=COORDINATOR_DETAILS,
        translation_key="dns_unique_clients",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PiHoleV6SensorEntityDescription(
        key="dns_unique_domains",
        coordinator_key=COORDINATOR_DETAILS,
        translation_key="dns_unique_domains",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PiHoleV6SensorEntityDescription(
        key="configured_clients",
        coordinator_key=COORDINATOR_DETAILS,
        translation_key="configured_clients",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    PiHoleV6SensorEntityDescription(
        key="dhcp_leases",
        coordinator_key=COORDINATOR_DETAILS,
        translation_key="dhcp_leases",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    PiHoleV6SensorEntityDescription(
        entity_category=EntityCategory.DIAGNOSTIC,
        key="latest_data_refresh",
        follow_every_coordinator=True,
        translation_key="latest_data_refresh",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
    ),
    PiHoleV6SensorEntityDescription(
        entity_category=EntityCategory.DIAGNOSTIC,
        key="memory_use",
        translation_key="memory_use",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    PiHoleV6SensorEntityDescription(
        entity_category=EntityCategory.DIAGNOSTIC,
        key="cpu_use",
        translation_key="cpu_use",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
    ),
    PiHoleV6SensorEntityDescription(
        key="ftl_info_message_count",
        coordinator_key=COORDINATOR_DETAILS,
        translation_key="ftl_info_message_count",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    PiHoleV6SensorEntityDescription(
        entity_category=EntityCategory.DIAGNOSTIC,
        key="auth_sessions",
        coordinator_key=COORDINATOR_DETAILS,
        translation_key="auth_sessions",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PiHoleV6ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Pi-hole V6 sensor.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        entry (PiHoleV6ConfigEntry): The config entry providing runtime data.
        async_add_entities (AddConfigEntryEntitiesCallback): Callback to register new entities.

    Returns:
        None

    """
    name = entry.data[CONF_NAME]
    hole_data = entry.runtime_data

    coordinators: dict[str, DataUpdateCoordinator[Any]] = {
        COORDINATOR_LIVE: hole_data.coordinator,
        COORDINATOR_DETAILS: hole_data.coordinator_details,
    }

    def get_extra_coordinators(
        description: PiHoleV6SensorEntityDescription,
    ) -> list[DataUpdateCoordinator[Any]]:
        """Return the coordinators the sensor must listen to besides its own.

        Args:
            description (PiHoleV6SensorEntityDescription): The description of the sensor being created.

        Returns:
            list[DataUpdateCoordinator[Any]]: The other coordinators, or an empty list.

        """

        if not description.follow_every_coordinator:
            return []

        return [value for key, value in coordinators.items() if key != description.coordinator_key]

    sensors = [
        PiHoleV6Sensor(
            hole_data.api,
            coordinators[description.coordinator_key],
            entry.entry_id,
            description,
            get_extra_coordinators(description),
        )
        for description in SENSOR_TYPES
    ]
    async_add_entities(sensors, update_before_add=True)

    hass.data[f"pi_hole_entities_sensor_{name}"] = []
    hass.data[f"pi_hole_entities_sensor_{name}"].extend(sensors)

    async def update_timer(_: Any) -> None:
        """Trigger sensor state update on a time interval basis.

        Args:
            _ (Any): The time event (unused).

        Returns:
            None

        """
        await sensor_update_timer(hass, name)

    async_track_time_interval(hass, update_timer, timedelta(seconds=1))


class PiHoleV6Sensor(PiHoleV6Entity, SensorEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    """Representation of a Pi-hole V6 sensor."""

    entity_description: PiHoleV6SensorEntityDescription

    def __init__(
        self,
        api: ClientAPI,
        coordinator: DataUpdateCoordinator[Any],
        server_unique_id: str,
        description: PiHoleV6SensorEntityDescription,
        extra_coordinators: list[DataUpdateCoordinator[Any]] | None = None,
    ) -> None:
        """Initialize a Pi-hole V6 sensor.

        Args:
            api (ClientAPI): The Pi-hole API client instance.
            coordinator (DataUpdateCoordinator[Any]): The data update coordinator feeding this sensor.
            server_unique_id (str): A unique identifier for the server entry.
            description (PiHoleV6SensorEntityDescription): The entity description.
            extra_coordinators (list[DataUpdateCoordinator[Any]] | None): Other coordinators whose refresh
                must also trigger a state write, for the sensors reporting on every coordinator.

        """

        name: str = coordinator.name
        super().__init__(api, coordinator, name, server_unique_id)
        self._extra_coordinators: list[DataUpdateCoordinator[Any]] = extra_coordinators or []
        self.entity_description = description  # pyright: ignore[reportIncompatibleVariableOverride]
        self._attr_unique_id = f"{self._server_unique_id}/{description.key}"

        raw_name: str = f"sensor.{name}_{description.key}"
        self.entity_id = create_entity_id_name(raw_name)

    async def async_added_to_hass(self) -> None:
        """Subscribe to the coordinators the sensor is not attached to.

        Returns:
            None

        """

        await super().async_added_to_hass()

        for coordinator in self._extra_coordinators:
            self.async_on_remove(coordinator.async_add_listener(self.async_write_ha_state))

    @property
    def native_value(self) -> StateType | datetime:  # pyright: ignore[reportIncompatibleVariableOverride] # pylint: disable=too-many-return-statements, too-many-branches
        """Return the state of the device.

        Returns:
            StateType | datetime: The current state value of the sensor.

        """

        match self.entity_description.key:
            case "latest_data_refresh":
                return self.native_latest_data_refresh()
            case "ads_blocked_today":
                return self.api.cache_summary["queries"]["blocked"]
            case "ads_percentage_blocked_today":
                return self.api.cache_summary["queries"]["percent_blocked"]
            case "seen_clients":
                return self.api.cache_summary["clients"]["total"]
            case "dns_queries_today":
                return self.api.cache_summary["queries"]["total"]
            case "domains_blocked":
                return self.api.cache_summary["gravity"]["domains_being_blocked"]
            case "dns_queries_cached":
                return self.api.cache_summary["queries"]["cached"]
            case "dns_queries_forwarded":
                return self.api.cache_summary["queries"]["forwarded"]
            case "dns_unique_clients":
                return self.api.cache_summary["clients"]["active"]
            case "dns_unique_domains":
                return self.api.cache_summary["queries"]["unique_domains"]
            case "dns_queries_frequency":
                return round(self.api.cache_summary["queries"]["frequency"] * 60, 0)
            case "memory_use":
                return self.api.cache_padd["%mem"]
            case "cpu_use":
                return self.api.cache_padd["%cpu"]
            case "ftl_info_message_count":
                return self.api.cache_ftl_info["message_count"]
            case "remaining_until_blocking_mode":
                return self.native_remaining_until_blocking_mode()
            case "configured_clients":
                return len(self.api.cache_configured_clients)
            case "dhcp_leases":
                return len(self.api.cache_dhcp_leases)
            case "auth_sessions":
                return len(self.api.cache_auth_sessions)
            case _:
                pass

        return ""

    def native_latest_data_refresh(self) -> datetime | None:
        """Return the most recent refresh timestamp across every coordinator.

        Returns:
            datetime | None: The latest refresh timestamp, or None if no coordinator has refreshed yet.

        """

        if not self.api.last_refresh:
            return None

        return max(self.api.last_refresh.values())

    def native_remaining_until_blocking_mode(self) -> int:
        """Compute the remaining seconds until blocking mode is automatically restored.

        Updates the cache of remaining dates based on the current blocking timer value.

        Returns:
            int: Remaining seconds until blocking mode is restored, or 0 if no timer is active.

        """

        value = round(self.api.cache_blocking["timer"]) if self.api.cache_blocking["timer"] is not None else 0

        if value > 0:
            until_date: datetime = datetime.now(UTC) + timedelta(seconds=value)
            self.api.cache_remaining_dates[f"{self._name}_sensor/global"] = until_date
        elif f"{self._name}_sensor/global" in self.api.cache_remaining_dates:
            del self.api.cache_remaining_dates[f"{self._name}_sensor/global"]

        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:  # pyright: ignore[reportIncompatibleVariableOverride] # pylint: disable=too-many-return-statements, too-many-branches
        """Return the state attributes of the Pi-hole V6.

        Returns:
            dict[str, Any] | None: A dictionary of extra attributes, or None if not applicable.

        """

        if self.entity_description.key == "latest_data_refresh":
            return {
                "live_data_refresh": self.api.last_refresh.get(COORDINATOR_LIVE),
                "detailed_data_refresh": self.api.last_refresh.get(COORDINATOR_DETAILS),
                "note": "Most recent refresh of the two coordinators.",
            }

        if self.entity_description.key == "memory_use":
            return self.api.cache_padd["system"]["memory"]

        if self.entity_description.key == "cpu_use":
            return self.api.cache_padd["system"]["cpu"]

        if self.entity_description.key == "ftl_info_message_count":
            raw_messages: list[Any] = self.api.cache_ftl_info["message_list"]
            messages: list[Any] = [{k: v for k, v in message.items() if k != "html"} for message in raw_messages]
            status: str = self.api.cache_ftl_info["status"]
            return {"messages": messages, "status": status, "note": "Total number of Pi-hole diagnosis messages."}

        if self.entity_description.key == "configured_clients":
            raw_clients: list[Any] = self.api.cache_configured_clients
            excluding: list[str] = ["date_added", "date_modified"]
            clients: list[Any] = [{k: v for k, v in client.items() if k not in excluding} for client in raw_clients]
            return {"clients": clients, "note": "Total number of configured clients."}

        if self.entity_description.key == "dhcp_leases":
            raw_leases: list[Any] = self.api.cache_dhcp_leases
            excluding: list[str] = []
            leases: list[Any] = [{k: v for k, v in lease.items() if k not in excluding} for lease in raw_leases]
            return {"leases": leases, "note": "Total number of active DHCP leases."}

        if self.entity_description.key == "auth_sessions":
            raw_sessions: list[Any] = self.api.cache_auth_sessions
            excluding: list[str] = ["tls", "x_forwarded_for"]
            sessions: list[Any] = [{k: v for k, v in session.items() if k not in excluding} for session in raw_sessions]
            return {"sessions": sessions, "note": "Total number of auth sessions."}

        match self.entity_description.key:
            case "ads_blocked_today":
                return {"note": "Number of blocked queries during the last 24h."}
            case "ads_percentage_blocked_today":
                return {"note": "Percent of blocked queries during the last 24h."}
            case "seen_clients":
                return {"note": "Total number of clients seen by FTL."}
            case "dns_queries_today":
                return {"note": "Total number of queries during the last 24h."}
            case "domains_blocked":
                return {"note": "Number of domain on your Pi-hole's gravity."}
            case "dns_queries_cached":
                return {"note": "Number of queries replied to from cache or local configuration."}
            case "dns_queries_forwarded":
                return {"note": "Number of queries that have been forwarded."}
            case "dns_unique_clients":
                return {"note": "Number of active clients (seen in the last 24h)."}
            case "dns_unique_domains":
                return {"note": "Number of unique domains FTL knows."}
            case "dns_queries_frequency":
                return {"note": "Average number of DNS queries per minute."}
            case "remaining_until_blocking_mode":
                return {"note": "Remaining seconds until blocking mode is automatically changed."}
            case _:
                pass

        return None
