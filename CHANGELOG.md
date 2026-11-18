# Changelog

## 0.3.0 (2026-11-18)

- **Controls**: switches for AC output, DC output, light and ECO mode; selects for work mode
  (mute/standard/fast) and ECO shutdown time (1/2/4/6 h). Each command only succeeds once the
  station reports the new state (5 s), otherwise the action raises an error.
- Settings are written read-modify-write: every bit not being changed is copied from the latest
  settings frame.
- The read-only binary sensors (AC/DC/light/ECO) and the work-mode/ECO-time sensors are replaced by
  the switches and selects; delete the old entities from the entity list.

## 0.2.0 (2026-11-18)

- **Update interval option** (default 15 s, 1–300 s, *Configure* on the integration). The station
  notifies about twice a second; publishing every frame flooded the recorder with state changes.
  Connection changes are still shown immediately. Applies without a reload.

## 0.1.0 (2026-11-18)

First release, read-only.

- Bluetooth discovery of stations advertising `VOLIX*` or `AP S*`.
- Persistent BLE session through Home Assistant's Bluetooth stack (local adapters and
  ESPHome Bluetooth proxies), status request every 20 s, reconnect when no valid frame
  arrives for 60 s.
- Sensors: battery, input power, output power, remaining time; diagnostic work mode and
  ECO shutdown time.
- Binary sensors: AC output, DC output, light; diagnostic ECO mode and Bluetooth connection.
- Firmware/hardware versions on the device page; diagnostics with the last raw frames.
- Follows stations whose random BLE address changes after a reboot (matched by name).
