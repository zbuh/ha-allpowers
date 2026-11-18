# ALLPOWERS power stations for Home Assistant (Bluetooth)

Local, push-based integration for **ALLPOWERS** portable power stations that talk over
Bluetooth LE, such as the **VOLIX P300**. It uses Home Assistant's own Bluetooth stack, so a
local adapter or an ESPHome Bluetooth proxy near the station is all you need: no cloud, no
ESP32 firmware.

Typical use: the station is the UPS of your Home Assistant server, and you want to know when
the server is running on battery and for how long it can last.

## What you get

| Entity | Notes |
|---|---|
| Battery | % |
| Input power / Output power | W |
| Remaining time | minutes, as estimated by the station |
| AC output / DC output / Light | on/off (read-only) |
| Work mode, ECO shutdown time, ECO mode | diagnostic, from the station's settings |
| Bluetooth connection | diagnostic: fresh data from the station |

Firmware and hardware versions appear on the device page. *Download diagnostics* includes the
last raw frames, useful when reporting a new model.

**Read-only on purpose.** Turning outputs off is not offered: on a station used as a UPS, a
mistaken "AC off" would cut power to the very server running Home Assistant.

## Supported models

| Model | Status |
|---|---|
| VOLIX P300 | protocol confirmed (GATT layout and a real settings frame); live test in progress |
| Other models advertising `VOLIX…` or `AP S…` | expected to work (same protocol), untested |

## Installation

Install **ALLPOWERS (Bluetooth)** from the Marketplace/HACS (custom repository
`https://github.com/zbuh/ha-allpowers`, category *Integration*), restart Home Assistant, and the
station shows up as a discovered device. Otherwise use *Add integration → ALLPOWERS*.

## Important: one connection at a time

The station accepts a single Bluetooth connection. While Home Assistant is connected, the
ALLPOWERS phone app cannot connect (and vice versa). To use the app, disable the integration
entry temporarily.

## How it works

The integration keeps one GATT connection open, subscribes to notifications on `FFF1` and
writes a status request to `FFF2` every 20 s. If no valid frame arrives for 60 s it reconnects.
Protocol details and credits: [docs/protocol.md](docs/protocol.md).

## Credits

Protocol knowledge from [madninjaskillz/allpowers-ble](https://github.com/madninjaskillz/allpowers-ble)
and [dedalodaelus/esphome-allpowers-ble](https://github.com/dedalodaelus/esphome-allpowers-ble) (both MIT).
Not affiliated with ALLPOWERS.

## Development

```bash
uv venv -p 3.14 && uv pip install -r requirements_test.txt
.venv/bin/python -m pytest -q
uvx ruff check . && uvx ruff format --check .
```
