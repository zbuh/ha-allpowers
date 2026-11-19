"""Constants."""

from __future__ import annotations

DOMAIN = "allpowers"
MANUFACTURER = "ALLPOWERS"

# Advertised names of supported stations (also listed in manifest.json).
LOCAL_NAME_PREFIXES = ("VOLIX", "AP S")

SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"
WRITE_UUID = "0000fff2-0000-1000-8000-00805f9b34fb"

CONF_UPDATE_INTERVAL = "update_interval"
# The station notifies about twice a second; entities update at most this often (option).
DEFAULT_UPDATE_INTERVAL = 15
MIN_UPDATE_INTERVAL = 1
MAX_UPDATE_INTERVAL = 300
KEEPALIVE_SECONDS = 20  # status request period
WATCHDOG_SECONDS = 60  # reconnect when no valid frame arrives for this long
RETRY_MIN_SECONDS = 5
RETRY_MAX_SECONDS = 120
WAIT_ADVERTISEMENT_SECONDS = 60


# Models known to have no built-in light (the protocol does not say; the light bit just stays 0).
NO_LIGHT_PREFIXES = ("VOLIX P300",)


def is_supported_name(name: str | None) -> bool:
    return bool(name) and name.startswith(LOCAL_NAME_PREFIXES)


def has_light(name: str) -> bool:
    return not name.startswith(NO_LIGHT_PREFIXES)
