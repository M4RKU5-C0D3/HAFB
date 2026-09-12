"""Sensor platform for the FRITZ!Box Budget integration."""

from __future__ import annotations

from homeassistant.components.sensor import RestoreSensor
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DEVICES, DOMAIN
from .coordinator import DeviceState, FritzBoxBudgetCoordinator

ATTR_USED_TODAY = "used_today"
ATTR_BUDGET = "budget"
ATTR_GRANTED_EXTENSION = "granted_extension"
ATTR_EXTENSION_LIMIT = "extension_limit"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator: FritzBoxBudgetCoordinator = entry.runtime_data
    devices = entry.options.get(CONF_DEVICES, {})
    async_add_entities(
        BudgetRemainingSensor(coordinator, entry.entry_id, mac) for mac in devices
    )


class BudgetRemainingSensor(
    CoordinatorEntity[FritzBoxBudgetCoordinator], RestoreSensor
):
    """Remaining time budget (minutes) for a device."""

    _attr_has_entity_name = True
    _attr_translation_key = "remaining_time"
    _attr_native_unit_of_measurement = "min"

    def __init__(
        self, coordinator: FritzBoxBudgetCoordinator, entry_id: str, mac: str
    ) -> None:
        super().__init__(coordinator)
        self._mac = mac
        self._attr_unique_id = f"{entry_id}_{mac}_remaining_time"
        host = coordinator.hosts.get(mac)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            name=host.name if host else mac,
            manufacturer="AVM",
        )

    @property
    def device_state(self) -> DeviceState:
        return self.coordinator.data[self._mac]

    @property
    def native_value(self) -> int:
        return round(self.device_state.remaining)

    @property
    def available(self) -> bool:
        return self._mac in self.coordinator.data

    @property
    def extra_state_attributes(self) -> dict[str, int | float]:
        state = self.device_state
        return {
            ATTR_USED_TODAY: round(state.used_today, 1),
            ATTR_BUDGET: state.budget,
            ATTR_GRANTED_EXTENSION: state.granted_extension,
            ATTR_EXTENSION_LIMIT: state.extension_limit,
        }

    async def async_added_to_hass(self) -> None:
        """Restore the previously persisted budget counters."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is None or last_state.attributes is None:
            return
        state = DeviceState(mac=self._mac)
        state.used_today = float(
            last_state.attributes.get(ATTR_USED_TODAY, 0) or 0
        )
        state.granted_extension = int(
            last_state.attributes.get(ATTR_GRANTED_EXTENSION, 0) or 0
        )
        state.budget = int(last_state.attributes.get(ATTR_BUDGET, 120) or 120)
        state.extension_limit = int(
            last_state.attributes.get(ATTR_EXTENSION_LIMIT, 60) or 60
        )
        self.coordinator.load_state(self._mac, state)
