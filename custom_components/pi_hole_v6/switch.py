"""Support for turning on and off Pi-hole system."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

import voluptuous as vol
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import PiHoleV6ConfigEntry
from .api import API as PiholeAPI
from .common import switch_update_timer
from .const import SERVICE_DISABLE, SERVICE_DISABLE_ATTR_DURATION, SERVICE_ENABLE
from .entity import PiHoleV6Entity
from .exceptions import (
    BadGatewayException,
    BadRequestException,
    ForbiddenException,
    GatewayTimeoutException,
    NotFoundException,
    RequestFailedException,
    ServerErrorException,
    ServiceUnavailableException,
    TooManyRequestsException,
    UnauthorizedException,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PiHoleV6ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Pi-hole V6 switch."""
    name = entry.data[CONF_NAME]
    hole_data = entry.runtime_data

    description: SwitchEntityDescription = SwitchEntityDescription(
        key="global",
    )

    switches = [
        PiHoleV6Switch(
            hole_data.api,
            hole_data.coordinator,
            name,
            entry.entry_id,
            description,
        )
    ]

    for group in hole_data.api.cache_groups.values():
        description: SwitchEntityDescription = SwitchEntityDescription(
            key="group",
            translation_key="group",
            translation_placeholders={
                "group_name": group["name"],
            },
        )

        switches.append(
            PiHoleV6Group(
                hole_data.api,
                hole_data.coordinator,
                name,
                entry.entry_id,
                description,
                group,
            )
        )

    async_add_entities(switches, True)
    hass.data[f"pi_hole_entities_switch_{name}"] = []
    hass.data[f"pi_hole_entities_switch_{name}"].extend(switches)

    async def update_timer(now: Any) -> None:
        """..."""
        await switch_update_timer(hass, now, name)

    async_track_time_interval(hass, update_timer, timedelta(seconds=1))

    # register service
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_DISABLE,
        {
            vol.Optional(SERVICE_DISABLE_ATTR_DURATION): vol.All(cv.time_period_str, cv.positive_timedelta),
        },
        "async_service_disable",
    )
    platform.async_register_entity_service(
        SERVICE_ENABLE,
        {},
        "async_service_enable",
    )


class PiHoleV6Switch(PiHoleV6Entity, SwitchEntity):
    """Representation of a Pi-hole V6 switch."""

    _attr_icon = "mdi:pi-hole"
    _attr_has_entity_name = False

    def __init__(
        self,
        api: PiholeAPI,
        coordinator: DataUpdateCoordinator,
        name: str,
        server_unique_id: str,
        description: SwitchEntityDescription,
    ) -> None:
        super().__init__(api, coordinator, name, server_unique_id)
        self.entity_description = description

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the unique id of the switch."""
        return f"{self._server_unique_id}/Switch"

    @property
    def is_on(self) -> bool:
        """Return if the service is on."""
        return bool(self.api.cache_blocking.get("blocking", None) == "enabled")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the service."""
        await self.async_turn_switch(action="enable")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the service."""
        await self.async_turn_switch(action="disable")

    async def async_turn_switch(self, action: str, duration: Any = None, with_update: bool = True) -> None:
        """Turn on/off the service."""

        try:
            if action == "enable":
                await self.api.call_blocking_enabled()

            if action == "disable":
                await self.api.call_blocking_disabled(duration)

            if with_update is True:
                await self.async_update()
                self.schedule_update_ha_state(force_refresh=True)

        except (
            BadRequestException,
            UnauthorizedException,
            RequestFailedException,
            ForbiddenException,
            NotFoundException,
            TooManyRequestsException,
            ServerErrorException,
            BadGatewayException,
            ServiceUnavailableException,
            GatewayTimeoutException,
        ) as err:
            _LOGGER.error("Unable to %s Pi-hole V6: %s", action, err)

    async def async_service_disable(self, duration: Any = None) -> None:
        """..."""
        duration_seconds: int | None = calculate_duration(duration, self._name)
        await self.async_turn_switch(action="disable", duration=duration_seconds)

    async def async_service_enable(self) -> None:
        """..."""
        _LOGGER.debug("Enabling Pi-hole '%s'", self.name)
        await self.async_turn_switch(action="enable")


class PiHoleV6Group(PiHoleV6Entity, SwitchEntity):
    """Representation of a Pi-hole V6 group."""

    entity_description: SwitchEntityDescription
    _attr_has_entity_name = True
    _attr_icon = "mdi:account-multiple"
    _attr_translation_key = "group"

    def __init__(
        self,
        api: PiholeAPI,
        coordinator: DataUpdateCoordinator,
        name: str,
        server_unique_id: str,
        description: SwitchEntityDescription,
        group: Dict[str, Any],
    ) -> None:
        super().__init__(api, coordinator, name, server_unique_id)
        self.entity_description = description

        group_name: str = group["name"]

        self._attr_unique_id = f"{self._server_unique_id}/{name}_group_{group_name.lower()}"
        self.entity_id = f"switch.{name}_group_{group_name.lower()}"
        self.group_name = group_name

    @property
    def is_on(self) -> bool:
        """Return if the group is on."""
        return self.api.cache_groups[self.group_name]["enabled"]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the group."""
        await self.async_turn_group(action="enable")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the group."""
        await self.async_turn_group(action="disable")

    async def async_turn_group(self, action: str, with_update: bool = True) -> None:
        """Turn on/off the group."""

        try:
            if action == "enable":
                self.api.cache_groups[self.group_name]["enabled"] = True
                await self.api.call_group_enable(self.group_name)
                if f"{self._name}/{self.group_name}" in self.api.cache_remaining_dates:
                    del self.api.cache_remaining_dates[f"{self._name}/{self.group_name}"]

            if action == "disable":
                self.api.cache_groups[self.group_name]["enabled"] = False
                await self.api.call_group_disable(self.group_name)

            if with_update is True:
                await self.async_update()
                self.schedule_update_ha_state(force_refresh=True)

        except (
            BadRequestException,
            UnauthorizedException,
            RequestFailedException,
            ForbiddenException,
            NotFoundException,
            TooManyRequestsException,
            ServerErrorException,
            BadGatewayException,
            ServiceUnavailableException,
            GatewayTimeoutException,
        ) as err:
            _LOGGER.error("Unable to %s Pi-hole V6 group %s: %s", action, self.group_name, err)

    async def async_service_enable(self) -> None:
        """..."""

        _LOGGER.debug("Enabling Pi-hole '%s'", self.name)
        await self.async_turn_switch(action="enable")

    async def async_service_disable(self, duration: Any = None) -> None:
        """..."""
        duration_seconds: int | None = calculate_duration(duration, f"group/{self.group_name}")
        await self.async_turn_switch(action="disable", duration=duration_seconds)

    async def async_turn_switch(self, action: str, duration: Any = None, with_update: bool = True) -> None:
        """Turn on/off the service."""

        if action == "enable":
            if f"{self._name}/{self.group_name}" in self.api.cache_remaining_dates:
                del self.api.cache_remaining_dates[f"{self._name}/{self.group_name}"]

            await self.async_turn_group(action="enable")

        if action == "disable":
            if duration is not None:
                until_date: datetime = datetime.now() + timedelta(seconds=duration)
                self.api.cache_remaining_dates[f"{self._name}/{self.group_name}"] = until_date

            await self.async_turn_group(action="disable", with_update=with_update)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the switch Pi-hole V6."""

        if self.entity_description.key == "group":
            clients_group: List[Any] = []
            group_id: int = self.api.cache_groups[self.group_name]["id"]

            for client in self.api.cache_clients:
                if group_id in client["groups"]:
                    clients_group.append(
                        {
                            "client": client["client"],
                            "id": client["id"],
                            "name": client["name"],
                        }
                    )

            return {
                "info": {
                    "name": self.group_name,
                    "id": group_id,
                    "comment": self.api.cache_groups[self.group_name]["comment"],
                },
                "clients": clients_group,
            }


def calculate_duration(duration: Any, name: str) -> int | None:
    """..."""

    duration_seconds: int | None = None

    if isinstance(duration, timedelta):
        duration_seconds = duration.total_seconds()

    if isinstance(duration, int):
        duration_seconds = duration

    if duration is None:
        _LOGGER.debug("Disabling Pi-hole '%s' indefinitely", name)
    else:
        _LOGGER.debug("Disabling Pi-hole '%s' for %d seconds", name, duration_seconds)

    return duration_seconds
