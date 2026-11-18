"""Constants."""

from __future__ import annotations

DOMAIN = "allpowers"
MANUFACTURER = "ALLPOWERS"

# Advertised names of supported stations (also listed in manifest.json).
LOCAL_NAME_PREFIXES = ("VOLIX", "AP S")

SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"
WRITE_UUID = "0000fff2-0000-1000-8000-00805f9b34fb"

KEEPALIVE_SECONDS = 20  # status request period
WATCHDOG_SECONDS = 60  # reconnect when no valid frame arrives for this long
RETRY_MIN_SECONDS = 5
RETRY_MAX_SECONDS = 120
WAIT_ADVERTISEMENT_SECONDS = 60


def is_supported_name(name: str | None) -> bool:
    return bool(name) and name.startswith(LOCAL_NAME_PREFIXES)
