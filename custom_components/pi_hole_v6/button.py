"""Support for Pi-hole V6 button entities."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import PiHoleV6ConfigEntry
from .api import API as PiholeAPI
from .entity import PiHoleV6Entity
from .exceptions import ActionExecutionException, ForbiddenException

PARALLEL_UPDATES = 1
_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PiholeV6ButtonEntityDescription(ButtonEntityDescription):
    """Class describing Pi-hole V6 button entities."""


BUTTON_TYPES: tuple[PiholeV6ButtonEntityDescription, ...] = (
    PiholeV6ButtonEntityDescription(
        key="action_flush_arp",
        translation_key="action_flush_arp",
    ),
    PiholeV6ButtonEntityDescription(
        key="action_flush_logs",
        translation_key="action_flush_logs",
    ),
    PiholeV6ButtonEntityDescription(
        key="action_gravity",
        translation_key="action_gravity",
    ),
    PiholeV6ButtonEntityDescription(
        key="action_restartdns",
        translation_key="action_restartdns",
    ),
    PiholeV6ButtonEntityDescription(
        key="action_refresh_data",
        translation_key="action_refresh_data",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PiHoleV6ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    name = entry.data[CONF_NAME]
    hole_data = entry.runtime_data

    entities: list[PiHoleV6Button] = []

    for description in BUTTON_TYPES:
        entities.append(
            PiHoleV6Button(
                hole_data.api,
                hole_data.coordinator,
                name,
                entry.entry_id,
                description,
            )
        )

    async_add_entities(entities)


class PiHoleV6Button(PiHoleV6Entity, ButtonEntity):
    """Representation of a Pi-hole V6 button."""

    entity_description: PiholeV6ButtonEntityDescription

    def __init__(
        self,
        api: PiholeAPI,
        coordinator: DataUpdateCoordinator,
        name: str,
        server_unique_id: str,
        description: PiholeV6ButtonEntityDescription,
    ) -> None:
        """Initialize Pi-hole V6 button."""
        super().__init__(api, coordinator, name, server_unique_id)
        self.entity_description = description
        self._attr_unique_id = f"{self._server_unique_id}/{description.key}"
        self.entity_id = f"button.{name}_{description.key}"
        self._is_enabled = True  # Initial state is enabled

    async def async_press(self) -> None:
        """Press the button."""

        action: str = self.entity_description.key

        try:
            result: dict[str, Any] = {"code": 200}

            match action:
                case "action_flush_arp":
                    result = await self.api.call_action_flush_arp()
                case "action_flush_logs":
                    result = await self.api.call_action_flush_logs()
                case "action_gravity":
                    result = await self.api.call_action_gravity()
                case "action_restartdns":
                    result = await self.api.call_action_restartdns()
                case "action_refresh_data":
                    await self.async_update()
                    self.schedule_update_ha_state(force_refresh=True)

            if result["code"] != 200:
                raise ActionExecutionException()

            _LOGGER.info(f"Action '{action}' just executed correctly for '{self._name}'.")

        except ActionExecutionException:
            _LOGGER.error(f"Unable to launch '{action}' action : %s", result["data"])
        except ForbiddenException:
            _LOGGER.error(
                "To perform the 'flush/arp', 'flush/logs' and 'restartdns' actions, the 'Permit destructive actions via API' option must be enabled in the Pi-hole options."
            )

        self.coordinator.async_update_listeners()

    @property
    def is_enabled(self):
        """Return whether the button is enabled."""
        return self._is_enabled
