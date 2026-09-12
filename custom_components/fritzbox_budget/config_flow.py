"""Config flow to configure the FRITZ!Box Budget integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.helpers.selector import (
    BooleanSelector,
    BooleanSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import (
    FritzBoxAuthError,
    FritzBoxClient,
    FritzBoxConnectionError,
    FritzBoxInfo,
)
from .const import (
    CONF_BUDGET,
    CONF_DEVICES,
    CONF_EXTENSION_LIMIT,
    CONF_SSL,
    DEFAULT_BUDGET,
    DEFAULT_EXTENSION_LIMIT,
    DEFAULT_HOST,
    DOMAIN,
    ERROR_AUTH_INVALID,
    ERROR_CANNOT_CONNECT,
    ERROR_UNKNOWN,
)

_LOGGER = logging.getLogger(__name__)

_AUTH_EXCEPTIONS = (FritzBoxAuthError,)


class FritzBoxBudgetConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for FRITZ!Box Budget."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the FRITZ!Box Budget flow."""
        self._info: FritzBoxInfo | None = None

    @staticmethod
    def _port_from_input(user_input: dict[str, Any]) -> int | None:
        port = user_input.get(CONF_PORT)
        return int(port) if port else None

    def _build_client(self, user_input: dict[str, Any]) -> FritzBoxClient:
        return FritzBoxClient(
            host=user_input[CONF_HOST],
            port=self._port_from_input(user_input),
            username=user_input[CONF_USERNAME],
            password=user_input[CONF_PASSWORD],
            use_tls=user_input[CONF_SSL],
        )

    async def _async_connect(
        self, client: FritzBoxClient
    ) -> tuple[FritzBoxInfo | None, str | None]:
        """Try to connect; return (info, error key)."""
        try:
            info = await self.hass.async_add_executor_job(client.connect)
            return info, None
        except _AUTH_EXCEPTIONS:
            return None, ERROR_AUTH_INVALID
        except FritzBoxConnectionError as err:
            _LOGGER.warning("Failed to connect to FRITZ!Box: %s", err)
            return None, ERROR_CANNOT_CONNECT
        except Exception:
            _LOGGER.exception("Unexpected error while connecting to FRITZ!Box")
            return None, ERROR_UNKNOWN

    def _show_form(
        self,
        user_input: dict[str, Any] | None,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        user_input = user_input or {}
        use_tls = user_input.get(CONF_SSL, False)
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_HOST, default=user_input.get(CONF_HOST, DEFAULT_HOST)
                ): str,
                vol.Required(
                    CONF_USERNAME, default=user_input.get(CONF_USERNAME, "")
                ): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(CONF_SSL, default=use_tls): BooleanSelector(
                    BooleanSelectorConfig()
                ),
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors or {}
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        if user_input is None:
            return self._show_form(user_input)

        client = self._build_client(user_input)
        info, error = await self._async_connect(client)

        if error is not None:
            return self._show_form(user_input, {"base": error})

        self._info = info

        await self.async_set_unique_id(info.serial)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=info.model,
            data={
                CONF_HOST: user_input[CONF_HOST],
                CONF_PORT: self._port_from_input(user_input),
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
                CONF_SSL: user_input[CONF_SSL],
            },
        )


class FritzBoxBudgetOptionsFlow(OptionsFlow):
    """Options flow to select managed devices and their budgets."""

    VERSION = 1

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the options flow."""
        self._entry = entry
        self.selected: dict[str, dict[str, int]] = {}

    @property
    def _coordinator(self):
        """Return the runtime coordinator."""
        return self.hass.data[DOMAIN][self._entry.entry_id]

    def _host_options(self) -> list[dict[str, str]]:
        coordinator = self._coordinator
        return [
            {"label": f"{host.name} ({host.mac})", "value": host.mac}
            for host in coordinator.hosts.values()
        ]

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user select which devices to manage."""
        if user_input is not None:
            selected = user_input[CONF_DEVICES]
            devices = {}
            existing = self._entry.options.get(CONF_DEVICES, {})
            for mac in selected:
                devices[mac] = {
                    CONF_BUDGET: existing.get(mac, {}).get(CONF_BUDGET, DEFAULT_BUDGET),
                    CONF_EXTENSION_LIMIT: existing.get(mac, {}).get(
                        CONF_EXTENSION_LIMIT, DEFAULT_EXTENSION_LIMIT
                    ),
                }
            self.selected = devices
            return await self.async_step_configure()

        schema = vol.Schema(
            {
                vol.Required(CONF_DEVICES): SelectSelector(
                    SelectSelectorConfig(
                        options=self._host_options(),
                        multiple=True,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

    async def async_step_configure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure budget and extension limit for each selected device."""
        if user_input is not None:
            devices = {}
            for mac in self.selected:
                devices[mac] = {
                    CONF_BUDGET: user_input[f"budget_{mac}"],
                    CONF_EXTENSION_LIMIT: user_input[f"limit_{mac}"],
                }
            return self.async_create_entry(title="", data={CONF_DEVICES: devices})

        coordinator = self._coordinator
        schema: dict[vol.Marker, Any] = {}
        for mac in self.selected:
            name = coordinator.hosts.get(mac).name if mac in coordinator.hosts else mac
            selected = self.selected[mac]
            schema[
                vol.Required(
                    f"budget_{mac}",
                    default=selected[CONF_BUDGET],
                    description={"suffix": name},
                )
            ] = vol.Coerce(int)
            schema[
                vol.Required(
                    f"limit_{mac}",
                    default=selected[CONF_EXTENSION_LIMIT],
                    description={"suffix": name},
                )
            ] = vol.Coerce(int)

        return self.async_show_form(
            step_id="configure",
            data_schema=vol.Schema(schema),
        )
