"""Support for update entities of a Pi-hole system."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.update import UpdateEntity, UpdateEntityDescription
from homeassistant.const import CONF_NAME, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import PiHoleV6ConfigEntry
from .api import API as ClientAPI
from .entity import PiHoleV6Entity


@dataclass(frozen=True)
class PiHoleV6UpdateEntityDescription(UpdateEntityDescription):
    """Describes PiHoleV6 update entity."""

    installed_version: Callable[[dict], str | None] = lambda api: None
    latest_version: Callable[[dict], str | None] = lambda api: None
    release_base_url: str | None = None
    title: str | None = None


# entity_registry_enabled_default=False,

UPDATE_ENTITY_TYPES: tuple[PiHoleV6UpdateEntityDescription, ...] = (
    PiHoleV6UpdateEntityDescription(
        key="core_update_available",
        translation_key="core_update_available",
        title="Pi-hole Core",
        entity_category=EntityCategory.DIAGNOSTIC,
        installed_version=lambda versions: versions.get("core").get("local", {}).get("version", None),
        latest_version=lambda versions: versions.get("core").get("remote", {}).get("version", None),
        release_base_url="https://github.com/pi-hole/pi-hole/releases/tag",
    ),
    PiHoleV6UpdateEntityDescription(
        key="web_update_available",
        translation_key="web_update_available",
        title="Pi-hole Web interface",
        entity_category=EntityCategory.DIAGNOSTIC,
        installed_version=lambda versions: versions.get("web").get("local", {}).get("version", None),
        latest_version=lambda versions: versions.get("web").get("remote", {}).get("version", None),
        release_base_url="https://github.com/pi-hole/AdminLTE/releases/tag",
    ),
    PiHoleV6UpdateEntityDescription(
        key="ftl_update_available",
        translation_key="ftl_update_available",
        title="Pi-hole FTL",
        entity_category=EntityCategory.DIAGNOSTIC,
        installed_version=lambda versions: versions.get("ftl").get("local", {}).get("version", None),
        latest_version=lambda versions: versions.get("ftl").get("remote", {}).get("version", None),
        release_base_url="https://github.com/pi-hole/FTL/releases/tag",
    ),
    PiHoleV6UpdateEntityDescription(
        key="docker_update_available",
        translation_key="docker_update_available",
        title="Pi-hole Docker",
        entity_category=EntityCategory.DIAGNOSTIC,
        installed_version=lambda versions: versions.get("docker").get("local", None),
        latest_version=lambda versions: versions.get("docker").get("remote", None),
        release_base_url="https://github.com/pi-hole/docker-pi-hole/releases/tag",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PiHoleV6ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Pi-hole update entities."""
    name = entry.data[CONF_NAME]
    hole_data = entry.runtime_data

    async_add_entities(
        PiHoleV6UpdateEntity(
            hole_data.api,
            hole_data.coordinator,
            name,
            entry.entry_id,
            description,
        )
        for description in UPDATE_ENTITY_TYPES
    )


class PiHoleV6UpdateEntity(PiHoleV6Entity, UpdateEntity):
    """Representation of a Pi-hole update entity."""

    entity_description: PiHoleV6UpdateEntityDescription

    def __init__(
        self,
        api: ClientAPI,
        coordinator: DataUpdateCoordinator[None],
        name: str,
        server_unique_id: str,
        description: PiHoleV6UpdateEntityDescription,
    ) -> None:
        """Initialize a Pi-hole update entity."""
        super().__init__(api, coordinator, name, server_unique_id)
        self.entity_description = description
        self._attr_unique_id = f"{self._server_unique_id}/{description.key}"
        self.entity_id = f"update.{name}_{description.key}"

        enabled_value: bool = self.get_entity_registry_enabled_value()
        self.entity_registry_enabled_default = enabled_value
        self._attr_title = description.title

        if enabled_value is False:
            self._attr_title = description.title + " (only for information, please check other update entities)"

    def get_entity_registry_enabled_value(self) -> bool:
        """..."""

        try:
            if (
                self.api.cache_padd["version"]["docker"]["local"] is None
                and self.entity_description.key != "docker_update_available"
            ):
                return True

            if (
                self.api.cache_padd["version"]["docker"]["local"] is not None
                and self.entity_description.key == "docker_update_available"
            ):
                return True

        except Exception:
            pass

        return False

    @property
    def installed_version(self) -> str | None:
        """Version installed and in use."""
        versions: dict[str, Any] = self.api.cache_padd["version"]
        if isinstance(versions, dict):
            return self.entity_description.installed_version(versions)
        return None

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        versions: dict[str, Any] = self.api.cache_padd["version"]
        if isinstance(versions, dict):
            return self.entity_description.latest_version(versions)
        return None

    @property
    def release_url(self) -> str | None:
        """URL to the full release notes of the latest version available."""
        return f"{self.entity_description.release_base_url}/{self.latest_version}"
