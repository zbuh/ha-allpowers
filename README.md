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
| Time to full charge | minutes, while charging (unknown otherwise) |
| Remaining time | as estimated by the station; median of the last 10 minutes, unknown while charging, shown in hours (stored in minutes) |
| AC output / DC output / Light | switches (no light switch on models without one, e.g. VOLIX P300) |
| ECO mode | switch (configuration) |
| Work mode | select: mute / standard / fast (configuration) |
| ECO shutdown after | select: 1 / 2 / 4 / 6 h (configuration) |
| Bluetooth connection | diagnostic: fresh data from the station |

Firmware and hardware versions appear on the device page. *Download diagnostics* includes the
last raw frames, useful when reporting a new model.

Every command is **confirmed**: the action only succeeds once the station reports the new
state (within 5 s), otherwise it raises an error instead of failing silently.

> ⚠️ If the station is the UPS of your Home Assistant server, the switch of the output that
> feeds the server turns the server off. Hide it from dashboards and voice assistants.

## Supported models

| Model | Status |
|---|---|
| VOLIX P300 | tested (firmware 1.0) |
| Other models advertising `VOLIX…` or `AP S…` | expected to work (same protocol), untested |

## Installation

Install **ALLPOWERS (Bluetooth)** from the Marketplace/HACS (custom repository
`https://github.com/zbuh/ha-allpowers`, category *Integration*), restart Home Assistant, and the
station shows up as a discovered device. Otherwise use *Add integration → ALLPOWERS*.

## Options

| Option | Default | |
|---|---|---|
| Update interval | 15 s | The station sends data about twice a second; entities are updated at most this often, to keep the recorder database small. |

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
