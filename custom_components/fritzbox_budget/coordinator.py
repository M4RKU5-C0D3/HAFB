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
    CONF_EXTENSION_LIMIT,
    DEFAULT_BUDGET,
    DEFAULT_EXTENSION_LIMIT,
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
    extension_limit: int = DEFAULT_EXTENSION_LIMIT
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

    def _device_config(self, mac: str) -> tuple[int, int]:
        """Return (budget, extension_limit) for a configured device."""
        devices = self.entry.options.get(CONF_DEVICES, {})
        cfg = devices.get(mac, {})
        return (
            int(cfg.get(CONF_BUDGET, DEFAULT_BUDGET)),
            int(cfg.get(CONF_EXTENSION_LIMIT, DEFAULT_EXTENSION_LIMIT)),
        )

    def load_state(self, mac: str, state: DeviceState) -> None:
        """Restore a previously persisted budget state for a device."""
        budget, limit = self._device_config(mac)
        state.budget = budget
        state.extension_limit = limit
        self.data[mac] = state

    def restore_or_create(self, mac: str, name: str = "") -> DeviceState:
        """Return an existing stored state or create a fresh one."""
        if mac not in self.data:
            budget, limit = self._device_config(mac)
            self.data[mac] = DeviceState(
                mac=mac, name=name, budget=budget, extension_limit=limit
            )
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

        for mac in configured:
            host = self.hosts.get(mac)
            state = self.restore_or_create(mac, host.name if host else "")
            if host is not None:
                state.name = host.name
                state.ip = host.ip
                state.online = host.active
            else:
                state.online = False

            if state.online and state.ip:
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

        if state.wan_access:
            elapsed_minutes = (now - state.last_eval).total_seconds() / 60.0
            if elapsed_minutes > 0:
                state.used_today += elapsed_minutes
        state.last_eval = now

        if self._is_locked(state) and not state.lock_applied and state.ip:
            self.hass.async_add_executor_job(self.client.set_wan_access, state.ip, False)
            state.lock_applied = True

    @staticmethod
    def _is_locked(state: DeviceState) -> bool:
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
        """Grant extra minutes to a device, honoring the daily limit."""
        state = self.data.get(mac)
        if state is None:
            return False
        available = max(0, state.extension_limit - state.granted_extension)
        if available == 0:
            return False
        grant = min(minutes, available)
        state.granted_extension += grant
        state.lock_applied = False
        if state.ip and (state.wan_access is False or state.remaining <= 0):
            await self.hass.async_add_executor_job(
                self.client.set_wan_access, state.ip, True
            )
        await self.async_request_refresh()
        return True
