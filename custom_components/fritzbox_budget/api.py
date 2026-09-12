"""API client for the FRITZ!Box Budget integration.

Communicates with a FRITZ!Box via the TR-064 protocol using the
`fritzconnection` library. All blocking library calls must be executed
through ``hass.async_add_executor_job`` and are never made from the
event loop directly.
"""

from __future__ import annotations

from dataclasses import dataclass

from fritzconnection import FritzConnection
from fritzconnection.core.exceptions import (
    FritzAuthorizationError,
    FritzConnectionException,
    FritzSecurityError,
)
from fritzconnection.lib.fritzhosts import FritzHosts

from .const import (
    DEFAULT_HOST,
    DEFAULT_HTTP_PORT,
    DEFAULT_HTTPS_PORT,
    DEFAULT_SSL,
)


class FritzBoxConnectionError(Exception):
    """Raised when the FRITZ!Box cannot be reached."""


class FritzBoxAuthError(FritzBoxConnectionError):
    """Raised when authentication against the FRITZ!Box fails."""


class FritzBoxInfo:
    """Immutable snapshot of device information read from the router."""

    def __init__(self, model: str, serial: str) -> None:
        self.model = model
        self.serial = serial


FRITZ_AUTH_EXCEPTIONS = (FritzAuthorizationError, FritzSecurityError)


@dataclass
class Host:
    """A device registered with the FRITZ!Box."""

    name: str
    mac: str
    ip: str
    active: bool


class FritzBoxClient:
    """Async wrapper around a blocking FRITZ!Box TR-064 connection."""

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int | None = None,
        username: str = "",
        password: str = "",
        use_tls: bool = DEFAULT_SSL,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._use_tls = use_tls
        self._connection: FritzConnection | None = None

    def _effective_port(self) -> int | None:
        if self._port is not None:
            return self._port
        return DEFAULT_HTTPS_PORT if self._use_tls else DEFAULT_HTTP_PORT

    def connect(self) -> FritzBoxInfo:
        """Connect to the router and read its device info.

        Must be run from an executor thread. Returns an immutable info
        snapshot (model name and serial number) on success.
        """
        try:
            connection = FritzConnection(
                address=self._host,
                port=self._effective_port(),
                user=self._username,
                password=self._password,
                use_tls=self._use_tls,
                timeout=60.0,
                pool_maxsize=30,
                redact_debug_log=True,
            )
        except FRITZ_AUTH_EXCEPTIONS as err:
            raise FritzBoxAuthError from err
        except FritzConnectionException as err:
            raise FritzBoxConnectionError from err

        info = connection.call_action("DeviceInfo:1", "GetInfo")
        self._connection = connection
        return FritzBoxInfo(
            model=info["NewModelName"],
            serial=info["NewSerialNumber"],
        )

    def _get_connection(self) -> FritzConnection:
        """Return the active connection, raising if not connected."""
        if self._connection is None:
            raise FritzBoxConnectionError("Not connected to the FRITZ!Box")
        return self._connection

    def get_hosts(self) -> list[Host]:
        """Return the list of devices registered with the router.

        Must be run from an executor thread.
        """
        try:
            fh = FritzHosts(fc=self._get_connection())
            entries = fh.get_hosts_info()
        except FRITZ_AUTH_EXCEPTIONS as err:
            raise FritzBoxAuthError from err
        except FritzConnectionException as err:
            raise FritzBoxConnectionError from err

        hosts: list[Host] = []
        for entry in entries:
            mac = entry.get("mac") or ""
            if not mac:
                continue
            hosts.append(
                Host(
                    name=entry.get("name") or mac,
                    mac=mac.upper(),
                    ip=entry.get("ip") or "",
                    active=bool(entry.get("status")),
                )
            )
        return hosts

    def get_wan_access(self, ip: str) -> bool | None:
        """Return whether the device at ``ip`` currently has internet access.

        Returns ``None`` if the device cannot be addressed (e.g. no IP or an
        error occurred). Must be run from an executor thread.
        """
        if not ip:
            return None
        try:
            result = self._get_connection().call_action(
                "X_AVM-DE_HostFilter:1", "GetWANAccessByIP", NewIPv4Address=ip
            )
        except FritzConnectionException:
            return None
        wan_access = result.get("NewWANAccess")
        if wan_access == "granted":
            return True
        if wan_access == "denied":
            return False
        return None

    def set_wan_access(self, ip: str, enabled: bool) -> bool:
        """Enable or disable internet access for the device at ``ip``.

        The FRITZ!Box applies the change asynchronously. Returns ``True`` if
        the command was accepted. Must be run from an executor thread.
        """
        if not ip:
            return False
        try:
            self._get_connection().call_action(
                "X_AVM-DE_HostFilter:1",
                "DisallowWANAccessByIP",
                NewIPv4Address=ip,
                NewDisallow=not enabled,
            )
        except FritzConnectionException:
            return False
        return True
