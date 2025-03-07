"""Support for turning on and off Pi-hole system."""

from __future__ import annotations

import datetime
import logging
from typing import Any

import voluptuous as vol
from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import PiHoleV6ConfigEntry
from .api import API as PiholeAPI
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
    switches = [
        PiHoleV6Switch(
            hole_data.api,
            hole_data.coordinator,
            name,
            entry.entry_id,
        )
    ]

    for group in hole_data.api.cache_groups:
        description: SwitchEntityDescription = SwitchEntityDescription(
            key="group",
            translation_key="group",
            translation_placeholders={
                "group_name": group,
            },
        )

        switches.append(
            PiHoleV6Group(
                hole_data.api,
                hole_data.coordinator,
                name,
                entry.entry_id,
                group,
                description,
            )
        )

    async_add_entities(switches, True)

    # register service
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_DISABLE,
        {
            vol.Optional(SERVICE_DISABLE_ATTR_DURATION): vol.All(
                cv.time_period_str, cv.positive_timedelta
            ),
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

    async def async_turn_switch(self, action: str, duration: Any = None) -> None:
        """Turn on/off the service."""

        try:
            if action == "enable":
                await self.api.call_blocking_enabled()

            if action == "disable":
                await self.api.call_blocking_disabled(duration)

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

        duration_seconds = None

        if isinstance(duration, datetime.timedelta):
            duration_seconds = duration.total_seconds()

        if isinstance(duration, int):
            duration_seconds = duration

        if duration is None:
            _LOGGER.debug(
                "Disabling Pi-hole '%s' indefinitely",
                self.name,
            )

        else:
            _LOGGER.debug(
                "Disabling Pi-hole '%s' for %d seconds",
                self.name,
                duration_seconds,
            )

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
        group: str,
        description: SwitchEntityDescription,
    ) -> None:
        super().__init__(api, coordinator, name, server_unique_id)
        self.entity_description = description
        self._attr_unique_id = f"{self._server_unique_id}/{name}_group_{group.lower()}"
        self.entity_id = f"switch.{name}_group_{group.lower()}"
        self._group = group

    @property
    def is_on(self) -> bool:
        """Return if the group is on."""
        return self.api.cache_groups[self._group]["enabled"]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the group."""
        await self.async_turn_group(action="enable")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the group."""
        await self.async_turn_group(action="disable")

    async def async_turn_group(self, action: str) -> None:
        """Turn on/off the group."""

        try:
            if action == "enable":
                await self.api.call_group_enable(self._group)

            if action == "disable":
                await self.api.call_group_disable(self._group)

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
            _LOGGER.error(
                "Unable to %s Pi-hole V6 group %s: %s", action, self._group, err
            )

    async def async_service_enable(self) -> None:
        """..."""

    async def async_service_disable(self, duration: Any = None) -> None:
        """..."""
