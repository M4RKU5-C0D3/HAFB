"""The FRITZ!Box Budget integration for Home Assistant.

Controls internet access of devices (parental control) with a daily time
budget computed in Home Assistant. One config entry equals one FRITZ!Box.
"""

from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .api import FritzBoxClient
from .config_flow import FritzBoxBudgetOptionsFlow
from .const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    DOMAIN,
)
from .coordinator import FritzBoxBudgetCoordinator

PLATFORMS: list[Platform] = [Platform.SWITCH, Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type FritzBoxBudgetConfigEntry = ConfigEntry[FritzBoxBudgetCoordinator]

SERVICE_EXTEND_TIME = "extend_time"
SERVICE_ATTR_DEVICE = "device"
SERVICE_ATTR_MINUTES = "minutes"

_EXTEND_TIME_SCHEMA = vol.Schema(
    {
        vol.Required(SERVICE_ATTR_DEVICE): cv.string,
        vol.Required(SERVICE_ATTR_MINUTES): vol.All(
            vol.Coerce(int), vol.In([15, 30, 60])
        ),
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the FRITZ!Box Budget integration."""
    hass.config_entries.async_register_options_flow(DOMAIN, FritzBoxBudgetOptionsFlow)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: FritzBoxBudgetConfigEntry
) -> bool:
    """Set up a config entry."""
    client = FritzBoxClient(
        host=entry.data[CONF_HOST],
        port=entry.data.get(CONF_PORT),
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        use_tls=entry.data.get(CONF_SSL, False),
    )
    coordinator = FritzBoxBudgetCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await _async_register_services(hass, coordinator)
    return True


async def _async_register_services(
    hass: HomeAssistant, coordinator: FritzBoxBudgetCoordinator
) -> None:
    """Register the extend_time service for a config entry."""

    async def extend_time(call: ServiceCall) -> None:
        mac = call.data[SERVICE_ATTR_DEVICE]
        minutes = call.data[SERVICE_ATTR_MINUTES]
        await coordinator.async_extend_time(mac, minutes)

    hass.services.async_register(
        DOMAIN, SERVICE_EXTEND_TIME, extend_time, schema=_EXTEND_TIME_SCHEMA
    )


async def async_unload_entry(
    hass: HomeAssistant, entry: FritzBoxBudgetConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def async_reload_entry(
    hass: HomeAssistant, entry: FritzBoxBudgetConfigEntry
) -> None:
    """Reload a config entry after options changed."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
