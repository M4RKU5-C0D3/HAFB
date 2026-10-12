"""Switch platform for the FRITZ!Box Budget integration."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DEVICES, DOMAIN
from .coordinator import DeviceState, FritzBoxBudgetCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    coordinator: FritzBoxBudgetCoordinator = entry.runtime_data
    devices = entry.options.get(CONF_DEVICES, {})
    entities = [
        FritzBoxWanSwitch(coordinator, entry.entry_id, mac) for mac in devices
    ]
    entities.append(FritzBoxHolidayModeSwitch(coordinator, entry.entry_id))
    async_add_entities(entities)


class FritzBoxWanSwitch(
    CoordinatorEntity[FritzBoxBudgetCoordinator], SwitchEntity
):
    """Switch controlling internet access for a device."""

    _attr_has_entity_name = True
    _attr_translation_key = "internet"

    def __init__(
        self, coordinator: FritzBoxBudgetCoordinator, entry_id: str, mac: str
    ) -> None:
        super().__init__(coordinator)
        self._mac = mac
        self._attr_unique_id = f"{entry_id}_{mac}_internet"
        host = coordinator.hosts.get(mac)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            name=host.name if host else mac,
            manufacturer="AVM",
        )

    @property
    def device_state(self) -> DeviceState:
        """Return the runtime state for the managed device."""
        return self.coordinator.data[self._mac]

    @property
    def is_on(self) -> bool:
        return bool(self.device_state.wan_access)

    @property
    def available(self) -> bool:
        state = self.coordinator.data.get(self._mac)
        return state is not None and state.wan_access is not None

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_turn_wan(self._mac, True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_turn_wan(self._mac, False)


class FritzBoxHolidayModeSwitch(
    CoordinatorEntity[FritzBoxBudgetCoordinator], SwitchEntity, RestoreEntity
):
    """Switch controlling holiday mode for all managed devices."""

    _attr_has_entity_name = True
    _attr_translation_key = "holiday_mode"

    def __init__(
        self, coordinator: FritzBoxBudgetCoordinator, entry_id: str
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_holiday_mode"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="FRITZ!Box Budget",
            manufacturer="AVM",
        )

    @property
    def is_on(self) -> bool:
        return self.coordinator.holiday_mode

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_holiday_mode(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_holiday_mode(False)

    async def async_added_to_hass(self) -> None:
        """Restore previous state if available."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            await self.coordinator.async_set_holiday_mode(last_state.state == "on")
