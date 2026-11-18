"""Diagnostics: link state, decoded values and the last raw frames."""

from __future__ import annotations

import dataclasses
import time
from typing import Any

from homeassistant.core import HomeAssistant

from . import AllpowersConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AllpowersConfigEntry
) -> dict[str, Any]:
    device = entry.runtime_data
    return {
        "entry": dict(entry.data),
        "address": device.address,
        "connected": device.connected,
        "available": device.available,
        "seconds_since_last_frame": (
            round(time.monotonic() - device.last_frame, 1) if device.last_frame is not None else None
        ),
        "last_error": device.last_error,
        "status": dataclasses.asdict(device.status) if device.status else None,
        "settings": dataclasses.asdict(device.settings) if device.settings else None,
        "recent_frames": [{"time": t, "hex": h} for t, h in device.recent_frames],
    }
