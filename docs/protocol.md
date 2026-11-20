# Protocol notes

This integration does not claim independent reverse engineering. Offsets and the status
request come from the public, MIT-licensed
[`madninjaskillz/allpowers-ble`](https://github.com/madninjaskillz/allpowers-ble) library and the
protocol notes of [`dedalodaelus/esphome-allpowers-ble`](https://github.com/dedalodaelus/esphome-allpowers-ble).

## GATT

| UUID | Use |
|---|---|
| `FFF0` | service |
| `FFF1` | notifications (status and settings frames) |
| `FFF2` | writes (status request) |

A VOLIX P300 (Jieli chip, manufacturer ID `0x05D6`) also exposes `FF03` and `AE00`/`AE01`/`AE02`
(vendor firmware-update channel); they are not used.

## Frames

```text
A5 65 .. .. .. LL CC [LL payload bytes] XX
```

`LL` = payload length, `CC` = command, total length `8 + LL`, `XX` = XOR of all previous bytes.

### Status request (write to FFF2 every 20 s, verbatim)

```text
A5 65 B1 00 01 06 01 00 00 00 00 00
```

### Command 0x01: status

| Offset | Meaning |
|---|---|
| 7 bit 0 / bit 1 / bit 4 | DC / AC / light on |
| 8 | battery % (0–100) |
| 9–10 | input power, W, big-endian (P300 fw 1.0: after a charge it repeats the last value; trust it only while 13–14 = 5994) |
| 11–12 | output power, W, big-endian |
| 13–14 | remaining time, minutes, big-endian; 5994 (99:54) while charging |

### Command 0x03: settings

| Offset | Meaning |
|---|---|
| 7 bit 0 | ECO |
| 7 bits 1–2 | work mode: 0 mute, 1 standard, 2 fast |
| 7 bit 4 | car charger socket |
| 8 | ECO shutdown, hours |
| 9–10 | time to full charge, minutes, big-endian; 5994 (99:54) while not charging (P300: `000a` = 10 min with the screen at ~11 min) |
| 11 / 12 | hardware / firmware version (hex digits read as `major.minor`) |

Real frame from a VOLIX P300 (standard mode, ECO off, 1 h, versions 1.0/1.0):
`a565b1000106030201176a10100b`.

## Known firmware behaviour (VOLIX P300, firmware 1.0)

- After a full charge the station stops charging and runs the load from the battery down to ~88 %. Then it
  enters a pass-through/maintenance mode: the screen shows a charging animation, an input power that follows
  the output (~7 W for a 5-6 W load) and a remaining time computed from the net drain (9.9 days).
- In that mode the status frame keeps sending a remaining-time estimate (not 5994) and an input power that has
  nothing to do with the screen (seen: 141 W, fixed for hours). The official ALLPOWERS app shows the same
  141 W, so the value on the screen is not sent over Bluetooth.
- Therefore input power is only meaningful while bytes 13-14 = 5994 (a real charge); the integration
  reports 0 W otherwise (0.3.5).
