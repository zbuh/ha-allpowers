# Changelog

## 0.3.2 (2026-11-19)

- **Remaining time** is the median of the readings received during each update interval instead of
  the last one. The station divides its energy by the instantaneous load, so with a small load the
  value jumped +-150 min every few seconds (seen: 1476-2151 min within an hour at 5-6 W).
- Remaining time is shown in hours with one decimal (31.2 h) on new installs. Existing entities keep
  their unit: change it to hours in the entity settings. Statistics stay in minutes.

## 0.3.1 (2026-11-19)

- No light switch on models without a built-in light (the protocol does not say; known list, for now
  the VOLIX P300). A light switch created by 0.3.0 for such a model is removed automatically.
- Known P300 behaviour (firmware 1.0): after a charge the input power reported over Bluetooth can stay
  at its last value (seen: 44 W for 11 h with the screen at 0 W) until the station is unplugged. This
  is what the station sends; the integration reports it as is.

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
