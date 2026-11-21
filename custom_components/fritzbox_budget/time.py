"""Time platform for the FRITZ!Box Budget integration."""

from __future__ import annotations

from datetime import time as dt_time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DEVICES, DOMAIN
from .coordinator import FritzBoxBudgetCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the time platform."""
    coordinator: FritzBoxBudgetCoordinator = entry.runtime_data
    devices = entry.options.get(CONF_DEVICES, {})
    async_add_entities(
        BudgetUntilTime(coordinator, entry.entry_id, mac) for mac in devices
    )


class BudgetUntilTime(CoordinatorEntity[FritzBoxBudgetCoordinator], TimeEntity):
    """Adjust the remaining time so it lasts until a clock time."""

    _attr_has_entity_name = True
    _attr_translation_key = "until"
    _attr_icon = "mdi:timer-outline"

    def __init__(
        self, coordinator: FritzBoxBudgetCoordinator, entry_id: str, mac: str
    ) -> None:
        super().__init__(coordinator)
        self._mac = mac
        self._attr_unique_id = f"{entry_id}_{mac}_until"
        host = coordinator.hosts.get(mac)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            name=host.name if host else mac,
            manufacturer="AVM",
        )

    @property
    def native_value(self) -> dt_time | None:
        state = self.coordinator.data.get(self._mac)
        return state.target_time if state else None

    @property
    def available(self) -> bool:
        return self._mac in self.coordinator.data

    async def async_set_value(self, value: dt_time) -> None:
        await self.coordinator.async_set_until(self._mac, value)
