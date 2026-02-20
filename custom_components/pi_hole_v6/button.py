"""Support for Pi-hole V6 button entities."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription

from .entity import PiHoleV6Entity
from .exceptions import ActionExecutionError, ForbiddenError
from .helper import create_entity_id_name

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

    from . import PiHoleV6ConfigEntry
    from .api import Api as PiholeAPI

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
    PiholeV6ButtonEntityDescription(
        key="action_ftl_purge_diagnosis_messages",
        translation_key="action_ftl_purge_diagnosis_messages",
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 # pylint: disable=unused-argument
    entry: PiHoleV6ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Pi-hole V6 button entities.

    Args:
        hass (HomeAssistant): The Home Assistant instance (unused).
        entry (PiHoleV6ConfigEntry): The config entry providing runtime data.
        async_add_entities (AddConfigEntryEntitiesCallback): Callback to register new entities.

    Returns:
        None

    """

    hole_data = entry.runtime_data

    entities: list[PiHoleV6Button] = []

    entities = [
        PiHoleV6Button(
            hole_data.api,
            hole_data.coordinator,
            entry.entry_id,
            description,
        )
        for description in BUTTON_TYPES
    ]

    async_add_entities(entities)


class PiHoleV6Button(PiHoleV6Entity, ButtonEntity):
    """Representation of a Pi-hole V6 button."""

    entity_description: PiholeV6ButtonEntityDescription

    def __init__(
        self,
        api: PiholeAPI,
        coordinator: DataUpdateCoordinator[None],
        server_unique_id: str,
        description: PiholeV6ButtonEntityDescription,
    ) -> None:
        """Initialize Pi-hole V6 button.

        Args:
            api (PiholeAPI): The Pi-hole API client instance.
            coordinator (DataUpdateCoordinator[None]): The data update coordinator.
            server_unique_id (str): A unique identifier for the server entry.
            description (PiholeV6ButtonEntityDescription): The entity description.

        Returns:
            None

        """
        name: str = coordinator.name
        super().__init__(api, coordinator, name, server_unique_id)
        self.entity_description = description  # pyright: ignore[reportIncompatibleVariableOverride]
        self._attr_unique_id = f"{self._server_unique_id}/{description.key}"
        self._is_enabled = True  # Initial state is enabled

        raw_name: str = f"button.{name}_{description.key}"
        self.entity_id = create_entity_id_name(raw_name)

    async def async_press(self) -> None:
        """Press the button.

        Returns:
            None

        """

        action: str = self.entity_description.key
        result: dict[str, Any] = {"code": 200}

        try:
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
                    await self.api.call_blocking_status()
                    await self.async_update()
                    self.schedule_update_ha_state(force_refresh=True)
                case "action_ftl_purge_diagnosis_messages":
                    await self.api.call_action_ftl_purge_diagnosis_messages()
                    self.schedule_update_ha_state(force_refresh=True)
                case _:
                    pass

            if result["code"] != 200:
                raise ActionExecutionError  # noqa: TRY301

            _LOGGER.info("Action '%s' just executed correctly for '%s'", action, self._name)

        except ActionExecutionError:
            _LOGGER.exception("Unable to launch '%s' action : %s", action, result["data"])
        except ForbiddenError:
            _LOGGER.exception(
                "To perform the 'flush/arp', 'flush/logs' and 'restartdns' actions, the 'Permit destructive actions via API' option must be enabled in the Pi-hole options"
            )

        self.coordinator.async_update_listeners()

    @property
    def is_enabled(self) -> bool:
        """Return whether the button is enabled.

        Returns:
            bool: True if the button is enabled, False otherwise.

        """
        return self._is_enabled
