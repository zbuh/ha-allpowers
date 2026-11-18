"""Persistent BLE session with one ALLPOWERS station (push: the station notifies)."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections import deque
from collections.abc import Callable
from typing import Any

from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak_retry_connector import (
    BLEAK_RETRY_EXCEPTIONS,
    BleakClientWithServiceCache,
    establish_connection,
)
from homeassistant.components import bluetooth
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from .const import (
    DEFAULT_UPDATE_INTERVAL,
    KEEPALIVE_SECONDS,
    NOTIFY_UUID,
    RETRY_MAX_SECONDS,
    RETRY_MIN_SECONDS,
    WAIT_ADVERTISEMENT_SECONDS,
    WATCHDOG_SECONDS,
    WRITE_UUID,
)
from .protocol import (
    CMD_SETTINGS,
    CMD_STATUS,
    STATUS_REQUEST,
    Frame,
    FrameBuffer,
    Settings,
    Status,
    decode_settings,
    decode_status,
)

_LOGGER = logging.getLogger(__name__)

CONNECT_ERRORS = (BleakError, TimeoutError, *BLEAK_RETRY_EXCEPTIONS)


class AllpowersDevice:
    """Keeps one GATT connection open, requests status every 20 s and decodes frames.

    The station accepts a single BLE connection: while Home Assistant is connected
    the ALLPOWERS phone app cannot connect.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        name: str,
        on_address_change: Callable[[str], None] | None = None,
        update_interval: float = DEFAULT_UPDATE_INTERVAL,
    ) -> None:
        self.hass = hass
        self.address = address
        self.name = name
        self._on_address_change = on_address_change
        self.update_interval = update_interval
        self.status: Status | None = None
        self.settings: Settings | None = None
        self.connected = False
        self.last_frame: float | None = None
        self.recent_frames: deque[tuple[float, str]] = deque(maxlen=20)
        self.last_error: str | None = None
        self._listeners: list[Callable[[], None]] = []
        self._buffer = FrameBuffer()
        self._wake = asyncio.Event()
        self._disconnected = asyncio.Event()
        self._stopping = False
        self._task: asyncio.Task | None = None
        self._client: BleakClientWithServiceCache | None = None
        self._last_publish = 0.0
        self._pending_publish: CALLBACK_TYPE | None = None

    # ------------------------------------------------------------------ state

    @property
    def available(self) -> bool:
        return (
            self.connected
            and self.last_frame is not None
            and time.monotonic() - self.last_frame < WATCHDOG_SECONDS
        )

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    @callback
    def _notify(self) -> None:
        if self._pending_publish is not None:
            self._pending_publish()
            self._pending_publish = None
        self._last_publish = time.monotonic()
        for listener in list(self._listeners):
            listener()

    @callback
    def _publish_throttled(self) -> None:
        """Publish now, or once update_interval seconds have passed since the last publish."""
        if self._pending_publish is not None:
            return
        wait = self.update_interval - (time.monotonic() - self._last_publish)
        if wait <= 0:
            self._notify()
            return

        @callback
        def _flush(_now: Any) -> None:
            self._pending_publish = None
            self._notify()

        self._pending_publish = async_call_later(self.hass, wait, _flush)

    @callback
    def _set_connected(self, connected: bool) -> None:
        if connected != self.connected:
            self.connected = connected
            self._notify()

    @callback
    def handle_frame(self, frame: Frame) -> None:
        self.last_frame = time.monotonic()
        if self.last_error is not None:
            _LOGGER.info("%s: receiving data again", self.name)
            self.last_error = None
        self.recent_frames.append((time.time(), frame.raw.hex()))
        if frame.command == CMD_STATUS:
            if (status := decode_status(frame)) is not None:
                self.status = status
        elif frame.command == CMD_SETTINGS:
            if (settings := decode_settings(frame)) is not None:
                self.settings = settings
        else:
            _LOGGER.debug("%s: unhandled command 0x%02x: %s", self.name, frame.command, frame.raw.hex())
        self._publish_throttled()

    @callback
    def handle_notification(self, _sender: Any, data: bytearray) -> None:
        for frame in self._buffer.feed(bytes(data)):
            self.handle_frame(frame)

    @callback
    def wake(self) -> None:
        """An advertisement was seen: retry now instead of waiting."""
        self._wake.set()

    # -------------------------------------------------------------- lifecycle

    def start(self) -> None:
        self._stopping = False
        self._task = self.hass.async_create_background_task(self._run(), f"allpowers {self.address}")

    async def stop(self) -> None:
        self._stopping = True
        self._wake.set()
        self._disconnected.set()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        client, self._client = self._client, None
        if client is not None:
            with contextlib.suppress(*CONNECT_ERRORS):
                await client.disconnect()
        if self._pending_publish is not None:
            self._pending_publish()
            self._pending_publish = None
        self._set_connected(False)

    # ------------------------------------------------------------- connection

    @callback
    def _find_ble_device(self) -> BLEDevice | None:
        if ble := bluetooth.async_ble_device_from_address(self.hass, self.address, connectable=True):
            return ble
        # Some stations advertise a random address that changes after a reboot:
        # fall back to the advertised name.
        for info in bluetooth.async_discovered_service_info(self.hass, connectable=True):
            if info.name == self.name and info.address != self.address:
                _LOGGER.info("%s: address changed %s -> %s", self.name, self.address, info.address)
                self.address = info.address
                if self._on_address_change is not None:
                    self._on_address_change(info.address)
                return info.device
        return None

    async def _run(self) -> None:
        delay = RETRY_MIN_SECONDS
        while not self._stopping:
            ble = self._find_ble_device()
            if ble is None:
                self._set_connected(False)
                self._wake.clear()
                with contextlib.suppress(TimeoutError):
                    async with asyncio.timeout(WAIT_ADVERTISEMENT_SECONDS):
                        await self._wake.wait()
                continue
            try:
                await self._session(ble)
            except CONNECT_ERRORS as err:
                message = f"{type(err).__name__}: {err}"
                if message != self.last_error:
                    _LOGGER.warning("%s: %s", self.name, message)
                self.last_error = message
            except Exception:  # keep the loop alive whatever the BLE stack raises
                _LOGGER.exception("%s: unexpected error in the BLE session", self.name)
                self.last_error = "unexpected error"
            finally:
                self._set_connected(False)
            if self._stopping:
                return
            # A session that delivered data retries soon; failed attempts back off.
            delay = RETRY_MIN_SECONDS if self.last_frame is not None else min(delay * 2, RETRY_MAX_SECONDS)
            await asyncio.sleep(delay)

    async def _session(self, ble: BLEDevice) -> None:
        """One connection, until it drops or the watchdog fires."""
        self._disconnected.clear()
        client = await establish_connection(
            BleakClientWithServiceCache,
            ble,
            self.name,
            disconnected_callback=lambda _client: self._disconnected.set(),
            ble_device_callback=lambda: self._find_ble_device() or ble,
        )
        self._client = client
        started = time.monotonic()
        self.last_frame = None
        self._buffer = FrameBuffer()
        try:
            await client.start_notify(NOTIFY_UUID, self.handle_notification)
            self._set_connected(True)
            while not self._stopping:
                await client.write_gatt_char(WRITE_UUID, STATUS_REQUEST, response=False)
                with contextlib.suppress(TimeoutError):
                    async with asyncio.timeout(KEEPALIVE_SECONDS):
                        await self._disconnected.wait()
                if self._disconnected.is_set():
                    raise BleakError("disconnected by the station")
                last = self.last_frame or started
                if time.monotonic() - last > WATCHDOG_SECONDS:
                    raise TimeoutError(f"no data for {WATCHDOG_SECONDS} s, reconnecting")
        finally:
            self._client = None
            with contextlib.suppress(*CONNECT_ERRORS):
                await client.disconnect()
