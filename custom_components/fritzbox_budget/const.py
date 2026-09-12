"""Constants for the FRITZ!Box Budget integration."""

CONF_HOST = "host"
CONF_SSL = "ssl"
CONF_PORT = "port"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

CONF_DEVICES = "devices"
CONF_BUDGET = "budget"
CONF_EXTENSION_LIMIT = "extension_limit"

DEFAULT_HOST = "fritz.box"
DEFAULT_HTTP_PORT = 49000
DEFAULT_HTTPS_PORT = 49443
DEFAULT_SSL = False
DEFAULT_BUDGET = 120
DEFAULT_EXTENSION_LIMIT = 60

DOMAIN = "fritzbox_budget"

ERROR_AUTH_INVALID = "invalid_auth"
ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_UNKNOWN = "unknown"

REASON_NOT_READY = "not_ready"

# Minutes of the day at which the daily budget counters are reset.
RESET_HOUR = 3
RESET_MINUTE = 0
