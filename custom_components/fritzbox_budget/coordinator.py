"""Coordinator for the FRITZ!Box Budget integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import FritzBoxClient, Host
from .const import (
    CONF_BUDGET,
    CONF_DEVICES,
    CONF_HOLIDAY_MODE,
    DEFAULT_BUDGET,
    DEFAULT_HOLIDAY_MODE,
    DOMAIN,
    RESET_HOUR,
)

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=15)


@dataclass
class DeviceState:
    """Runtime budget + access state for a single device."""

    mac: str
    name: str = ""
    ip: str = ""
    online: bool = False
    wan_access: bool | None = None

    budget: int = DEFAULT_BUDGET
    granted_extension: int = 0
    used_today: float = 0.0
    date: str = field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d")  # noqa: DTZ005
    )
    last_eval: datetime = field(default_factory=datetime.now)
    lock_applied: bool = False

    @property
    def allowance(self) -> float:
        """Total allowed minutes (budget + granted extensions)."""
        return self.budget + self.granted_extension

    @property
    def remaining(self) -> float:
        """Remaining minutes before the device gets locked."""
        return max(0.0, self.allowance - self.used_today)


class FritzBoxBudgetCoordinator(DataUpdateCoordinator[dict[str, DeviceState]]):
    """Poll the FRITZ!Box and track the per-device time budget."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: FritzBoxClient,
    ) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL)
        self.entry = entry
        self.client = client
        self.hosts: dict[str, Host] = {}
        self.data = {}
        self.holiday_mode: bool = self.entry.options.get(
            CONF_HOLIDAY_MODE, DEFAULT_HOLIDAY_MODE
        )

    def _device_config(self, mac: str) -> int:
        """Return the configured daily budget for a device."""
        devices = self.entry.options.get(CONF_DEVICES, {})
        cfg = devices.get(mac, {})
        return int(cfg.get(CONF_BUDGET, DEFAULT_BUDGET))

    def load_state(self, mac: str, state: DeviceState) -> None:
        """Restore a previously persisted budget state for a device."""
        state.budget = self._device_config(mac)
        self.data[mac] = state

    def restore_or_create(self, mac: str, name: str = "") -> DeviceState:
        """Return an existing stored state or create a fresh one."""
        if mac not in self.data:
            self.data[mac] = DeviceState(mac=mac, name=name)
            self.data[mac].budget = self._device_config(mac)
        return self.data[mac]

    async def _async_update_data(self) -> dict[str, DeviceState]:
        """Fetch host/access state and advance the budget counters.

        On connection/auth errors the previously known state is kept so that
        entities remain available.
        """
        try:
            hosts = await self.hass.async_add_executor_job(self.client.get_hosts)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Failed to fetch host list, keeping last state: %s", err)
            return self.data

        self.hosts = {h.mac: h for h in hosts}
        configured = self.entry.options.get(CONF_DEVICES, {})

        self.holiday_mode = self.entry.options.get(
            CONF_HOLIDAY_MODE, self.holiday_mode
        )

        for mac in configured:
            host = self.hosts.get(mac)
            state = self.restore_or_create(mac, host.name if host else "")
            if host is not None:
                state.name = host.name
                state.ip = host.ip
                state.online = host.active
            else:
                state.online = False

            if state.ip:
                state.wan_access = await self.hass.async_add_executor_job(
                    self.client.get_wan_access, state.ip
                )
            else:
                state.wan_access = None

            self._tick(state)

        return self.data

    def _tick(self, state: DeviceState) -> None:
        """Advance the used-time counter and enforce the lock for a device."""
        now = datetime.now()  # noqa: DTZ005
        if now.hour < RESET_HOUR:
            period_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            period_date = now.strftime("%Y-%m-%d")

        if state.date != period_date:
            was_locked = state.lock_applied
            state.date = period_date
            state.used_today = 0.0
            state.granted_extension = 0
            state.last_eval = now
            if was_locked and state.ip:
                self.hass.async_add_executor_job(
                    self.client.set_wan_access, state.ip, True
                )
                state.lock_applied = False
            return

        if state.wan_access and state.online:
            elapsed_minutes = (now - state.last_eval).total_seconds() / 60.0
            if elapsed_minutes > 0:
                state.used_today += elapsed_minutes
        state.last_eval = now

        if self._is_locked(state) and not state.lock_applied and state.ip:
            self.hass.async_add_executor_job(self.client.set_wan_access, state.ip, False)
            state.lock_applied = True

    def _is_locked(self, state: DeviceState) -> bool:
        if self.holiday_mode:
            return False
        return state.remaining <= 0

    async def async_turn_wan(self, mac: str, enabled: bool) -> None:
        """Turn WAN access on/off for a device, bypassing the budget lock."""
        state = self.data[mac]
        if not state.ip:
            return
        ok = await self.hass.async_add_executor_job(
            self.client.set_wan_access, state.ip, enabled
        )
        if ok:
            if enabled and state.remaining > 0:
                state.lock_applied = False
            await self.async_request_refresh()

    async def async_extend_time(self, mac: str, minutes: int) -> bool:
        """Grant extra minutes to a device.

        If time remains, the granted minutes are simply added (delaying the
        shutdown). If the budget is exhausted, internet access is re-enabled
        and the remaining time is set to the requested minutes.
        """
        state = self.data.get(mac)
        if state is None:
            return False
        if state.remaining > 0:
            state.granted_extension += minutes
        else:
            state.granted_extension = max(
                0, minutes + state.used_today - state.budget
            )
            if state.ip:
                await self.hass.async_add_executor_job(
                    self.client.set_wan_access, state.ip, True
                )
        state.lock_applied = False
        await self.async_request_refresh()
        return True

    async def async_set_holiday_mode(self, enabled: bool) -> None:
        """Enable or disable holiday mode and persist it in options."""
        self.holiday_mode = enabled
        options = dict(self.entry.options)
        options[CONF_HOLIDAY_MODE] = enabled
        self.hass.config_entries.async_update_entry(self.entry, options=options)
