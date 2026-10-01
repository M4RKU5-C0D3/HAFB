"""Button platform for the FRITZ!Box Budget integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DEVICES, DOMAIN, EXTENSION_MINUTES
from .coordinator import FritzBoxBudgetCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the button platform."""
    coordinator: FritzBoxBudgetCoordinator = entry.runtime_data
    devices = entry.options.get(CONF_DEVICES, {})
    entities = [
        ExtensionButton(coordinator, entry.entry_id, mac, minutes)
        for mac in devices
        for minutes in EXTENSION_MINUTES
    ]
    async_add_entities(entities)


class ExtensionButton(CoordinatorEntity[FritzBoxBudgetCoordinator], ButtonEntity):
    """Button granting a fixed time extension."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FritzBoxBudgetCoordinator,
        entry_id: str,
        mac: str,
        minutes: int,
    ) -> None:
        super().__init__(coordinator)
        self._mac = mac
        self._minutes = minutes
        self._attr_unique_id = f"{entry_id}_{mac}_extend_{minutes}"
        self._attr_translation_key = f"extend_{minutes}"
        host = coordinator.hosts.get(mac)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            name=host.name if host else mac,
            manufacturer="AVM",
        )

    @property
    def available(self) -> bool:
        return self._mac in self.coordinator.data

    async def async_press(self) -> None:
        await self.coordinator.async_extend_time(self._mac, self._minutes)