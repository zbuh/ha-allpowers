# Changelog

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
