"""Async Edifier M60 / M90 BLE controller (real Bleak hardware + Demo Mode simulator)."""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any, Awaitable, Callable

from bleak import BleakClient, BleakScanner

from .protocol import (
    HEADER_MAGIC_ED,
    M60_CONNEX_ADVERTISING_SERVICE_UUID,
    M60_GATT_SERVICE_UUID,
    M60_INPUT_GROUP,
    M60_NOTIFY_CHAR_UUID,
    M60_WRITE_CHAR_UUID,
    M90_CONNEX_ADVERTISING_SERVICE_UUID,
    M90_GATT_SERVICE_UUID,
    M90_INPUT_GROUP,
    MAX_VOLUME,
    MODEL_M60,
    MODEL_M90,
    VALID_ALL_HEADERS,
    CustomEqState,
    EqBand,
    EqPreset,
    Frame,
    FrameReassembler,
    InputSource,
    LdacMode,
    M90EqPreset,
    M90InputSource,
    Opcode,
    PlaybackAction,
    ProtocolError,
    SmartLightSensitivity,
    SmartLightTimer,
    SubOutLevel,
    cmd_cancel_timed_off,
    cmd_disconnect_bt_audio,
    cmd_playback,
    cmd_power_off_device,
    cmd_query_a2dp_state,
    cmd_query_audio_decoding,
    cmd_query_capabilities,
    cmd_query_classic_mac,
    cmd_query_codec_m90,
    cmd_query_custom_eq,
    cmd_query_eq_preset,
    cmd_query_firmware,
    cmd_query_input,
    cmd_query_ldac,
    cmd_query_multipoint,
    cmd_query_name,
    cmd_query_power_save,
    cmd_query_prompt_tone,
    cmd_query_smart_light,
    cmd_query_sub_out,
    cmd_query_timed_off,
    cmd_query_volume,
    cmd_set_codec_m90,
    cmd_set_custom_eq_band,
    cmd_set_custom_eq_meta,
    cmd_set_eq_preset,
    cmd_set_input,
    cmd_set_ldac,
    cmd_set_multipoint,
    cmd_set_name,
    cmd_set_power_save,
    cmd_set_prompt_tone,
    cmd_set_smart_light,
    cmd_set_sub_out,
    cmd_set_timed_off,
    cmd_set_volume,
    decode_a2dp_state,
    decode_audio_decoding,
    decode_capabilities,
    decode_classic_mac,
    decode_codec_m90,
    decode_custom_eq,
    decode_eq_preset,
    decode_firmware,
    decode_input,
    decode_ldac,
    decode_multipoint,
    decode_name,
    decode_power_save,
    decode_prompt_tone,
    decode_smart_light,
    decode_sub_out,
    decode_timed_off,
    decode_volume,
    default_custom_eq_bands,
    describe_frame,
    max_volume_for_model,
    normalize_model,
    parse_frame,
)
from .simulator import SimulatedM60Device

logger = logging.getLogger(__name__)


@dataclass
class SpeakerState:
    connected: bool = False
    connecting: bool = False
    demo_mode: bool = False
    model: str = MODEL_M60
    address: str | None = None
    device_name: str = "EDIFIER M60"
    firmware: str | None = None
    classic_mac: str | None = None
    capabilities: dict | None = None
    input_source: str = "bluetooth"
    input_settling: bool = False
    volume: int = 0
    max_volume: int = MAX_VOLUME
    eq_preset: str = "music"
    custom_eq: CustomEqState = field(
        default_factory=lambda: CustomEqState(bands=default_custom_eq_bands())
    )
    ldac_mode: str = "disabled"
    prompt_tone: bool = True
    smart_light_timer: str = "10s"
    smart_light_sensitivity: str = "general"
    sub_out_level: str = "medium"
    multipoint: bool = False
    power_save: bool = False
    timed_off_minutes: int = 0
    a2dp_state_code: int | None = None
    a2dp_state: str = "unknown"
    audio_decoding_code: int | None = None
    audio_decoding: str = "Unknown"
    notice: str | None = None
    last_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "connected": self.connected,
            "connecting": self.connecting,
            "demo_mode": self.demo_mode,
            "model": self.model,
            "address": self.address,
            "device_name": self.device_name,
            "firmware": self.firmware,
            "classic_mac": self.classic_mac,
            "capabilities": self.capabilities,
            "input_source": self.input_source,
            "input_settling": self.input_settling,
            "volume": self.volume,
            "max_volume": self.max_volume,
            "eq_preset": self.eq_preset,
            "custom_eq": self.custom_eq.to_dict(),
            "ldac_mode": self.ldac_mode,
            "prompt_tone": self.prompt_tone,
            "smart_light_timer": self.smart_light_timer,
            "smart_light_sensitivity": self.smart_light_sensitivity,
            "sub_out_level": self.sub_out_level,
            "multipoint": self.multipoint,
            "power_save": self.power_save,
            "timed_off_minutes": self.timed_off_minutes,
            "a2dp_state_code": self.a2dp_state_code,
            "a2dp_state": self.a2dp_state,
            "audio_decoding_code": self.audio_decoding_code,
            "audio_decoding": self.audio_decoding,
            "notice": self.notice,
            "last_error": self.last_error,
        }


EventCallback = Callable[[str, dict[str, Any]], Awaitable[None]]


class M60Controller:
    """Manages BLE GATT connection, protocol state sync, and Demo Mode."""

    def __init__(self) -> None:
        self.state = SpeakerState()
        self._client: BleakClient | None = None
        self._sim: SimulatedM60Device | None = None
        self._reassembler = FrameReassembler(allowed_headers=VALID_ALL_HEADERS)
        self._cmd_lock = asyncio.Lock()
        self._pending: dict[tuple[int, int], asyncio.Future[Frame]] = {}
        self._frame_logs: deque[dict[str, Any]] = deque(maxlen=200)
        self._listeners: set[EventCallback] = set()
        self._settle_task: asyncio.Task[None] | None = None
        self._poll_task: asyncio.Task[None] | None = None
        self._poll_cycle: int = 0
        self._loop: asyncio.AbstractEventLoop | None = None

    def add_listener(self, cb: EventCallback) -> None:
        self._listeners.add(cb)

    def remove_listener(self, cb: EventCallback) -> None:
        self._listeners.discard(cb)

    def recent_logs(self) -> list[dict[str, Any]]:
        return list(self._frame_logs)

    async def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        for cb in list(self._listeners):
            try:
                await cb(event_type, payload)
            except Exception:
                logger.debug("Listener error ignored", exc_info=True)

    async def _emit_state(self) -> None:
        await self._emit("ble_state", self.state.to_dict())

    def _record_log(self, direction: str, raw: bytes, summary: str) -> dict[str, Any]:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "direction": direction,
            "hex": raw.hex(" ").upper(),
            "summary": summary,
        }
        self._frame_logs.append(entry)
        return entry

    # ------------------------------------------------------------------
    # Discovery & Connection
    # ------------------------------------------------------------------

    async def scan(
        self, timeout: float = 6.0, show_all: bool = False
    ) -> list[dict[str, Any]]:
        """Scan for Edifier M60 / M90 BLE peripherals."""
        discovered = await BleakScanner.discover(timeout=timeout, return_adv=True)
        results: list[dict[str, Any]] = []
        for address, pair in discovered.items():
            device, adv = pair
            name = (adv.local_name or device.name or "").strip()
            uuids = [u.lower() for u in (adv.service_uuids or [])]
            low_name = name.lower()
            is_m90 = (
                "m90" in low_name
                or M90_CONNEX_ADVERTISING_SERVICE_UUID in uuids
                or M90_GATT_SERVICE_UUID in uuids
            )
            is_m60 = (
                "m60" in low_name
                or M60_CONNEX_ADVERTISING_SERVICE_UUID in uuids
                or M60_GATT_SERVICE_UUID in uuids
            )
            is_edifier = "edifier" in low_name or is_m60 or is_m90
            if not show_all and not is_edifier:
                continue
            detected_model = (
                MODEL_M90 if is_m90 else (MODEL_M60 if is_m60 else None)
            )
            results.append(
                {
                    "address": address,
                    "name": name or "(Unnamed BLE device)",
                    "rssi": adv.rssi,
                    "service_uuids": uuids,
                    "is_edifier": is_edifier,
                    "model": detected_model,
                }
            )
        results.sort(
            key=lambda d: (not d["is_edifier"], -(d["rssi"] if d["rssi"] is not None else -999))
        )
        return results

    async def set_demo_mode(
        self, enabled: bool, model: str = MODEL_M60
    ) -> dict[str, Any]:
        if enabled:
            m = normalize_model(model)
            await self.disconnect()
            self._sim = SimulatedM60Device(model=m)
            self.state = SpeakerState(
                connected=True,
                demo_mode=True,
                model=m,
                address=f"DEMO:{m.upper()}:00:00:01",
                device_name=f"EDIFIER {m.upper()}",
                max_volume=max_volume_for_model(m),
                eq_preset="classic" if m == MODEL_M90 else "music",
                custom_eq=CustomEqState(
                    format_byte=0x10 if m == MODEL_M90 else 0x03,
                    bands=default_custom_eq_bands(m),
                ),
                notice=f"Demo Mode active — interacting with an in-memory Edifier {m.upper()} emulator.",
            )
            await self.refresh_all()
            return self.state.to_dict()

        if self.state.demo_mode:
            self._sim = None
            self.state = SpeakerState()
            await self._emit_state()
        return self.state.to_dict()

    async def connect(self, address: str) -> dict[str, Any]:
        clean_addr = address.strip()
        if not clean_addr:
            raise ValueError("Bluetooth address is required.")

        await self.disconnect()
        self._sim = None
        self.state = SpeakerState(
            connected=False,
            connecting=True,
            address=clean_addr,
            notice=f"Connecting to {clean_addr}...",
        )
        await self._emit_state()

        loop = asyncio.get_running_loop()
        self._loop = loop

        def on_disconnected(_client: BleakClient) -> None:
            loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self._handle_unexpected_disconnect())
            )

        client = BleakClient(
            clean_addr, timeout=15.0, disconnected_callback=on_disconnected
        )
        try:
            await client.connect()
            services = client.services
            m90_service = services.get_service(M90_GATT_SERVICE_UUID)
            m60_service = services.get_service(M60_GATT_SERVICE_UUID)
            if m90_service is not None:
                service = m90_service
                detected_model = MODEL_M90
            elif m60_service is not None:
                service = m60_service
                detected_model = MODEL_M60
            else:
                await client.disconnect()
                raise RuntimeError(
                    "Connected to device, but neither Edifier M60 (4809f601-...) "
                    "nor Edifier M90 (48094503-...) GATT service was exposed. Close the "
                    "EDIFIER ConneX phone app (only 1 BLE connection is allowed) or wake "
                    "the speaker by playing audio."
                )
            notify_char = service.get_characteristic(M60_NOTIFY_CHAR_UUID)
            write_char = service.get_characteristic(M60_WRITE_CHAR_UUID)
            if notify_char is None or write_char is None:
                await client.disconnect()
                raise RuntimeError(
                    "Edifier GATT control characteristics (48090001/48090002) not found."
                )

            self._client = client
            self._reassembler.clear()
            await client.start_notify(M60_NOTIFY_CHAR_UUID, self._on_ble_notify)

            self.state.connected = True
            self.state.connecting = False
            self.state.demo_mode = False
            self.state.model = detected_model
            self.state.max_volume = max_volume_for_model(detected_model)
            self.state.device_name = (
                "EDIFIER M90" if detected_model == MODEL_M90 else "EDIFIER M60"
            )
            self.state.eq_preset = (
                "classic" if detected_model == MODEL_M90 else "music"
            )
            self.state.custom_eq = CustomEqState(
                format_byte=0x10 if detected_model == MODEL_M90 else 0x03,
                bands=default_custom_eq_bands(detected_model),
            )
            self.state.last_error = None
            self.state.notice = (
                f"Connected to Edifier {detected_model.upper()} over BLE."
            )
            await self._emit_state()
            await self.refresh_all()
            self._poll_cycle = 0
            self._poll_task = asyncio.create_task(self._poll_loop())
            return self.state.to_dict()
        except Exception as exc:
            try:
                if client.is_connected:
                    await client.disconnect()
            except Exception:
                pass
            self._client = None
            self.state.connected = False
            self.state.connecting = False
            self.state.last_error = str(exc)
            self.state.notice = None
            await self._emit_state()
            raise

    async def disconnect(self) -> dict[str, Any]:
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
        self._poll_task = None
        if self._settle_task and not self._settle_task.done():
            self._settle_task.cancel()
        self._cancel_all_pending()

        if self._client is not None:
            client = self._client
            self._client = None
            try:
                if client.is_connected:
                    try:
                        await client.stop_notify(M60_NOTIFY_CHAR_UUID)
                    except Exception:
                        pass
                    await client.disconnect()
            except Exception:
                logger.debug("Error during BLE disconnect", exc_info=True)

        self._sim = None
        self.state = SpeakerState()
        await self._emit_state()
        return self.state.to_dict()

    async def _handle_unexpected_disconnect(self) -> None:
        if self._client is None and not self.state.connected:
            return
        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
        self._poll_task = None
        self._client = None
        self._cancel_all_pending()
        self.state.connected = False
        self.state.connecting = False
        self.state.notice = (
            "BLE connection closed. If you switched LDAC or disconnected BT audio, "
            "reconnect once the speaker finishes restarting its link."
        )
        await self._emit_state()

    def _cancel_all_pending(self) -> None:
        for fut in self._pending.values():
            if not fut.done():
                fut.cancel()
        self._pending.clear()

    # ------------------------------------------------------------------
    # Low-Level Transport & Frame Dispatch
    # ------------------------------------------------------------------

    def _schedule_coro(self, coro: Any) -> None:
        try:
            running = asyncio.get_running_loop()
            running.create_task(coro)
            return
        except RuntimeError:
            pass
        if self._loop is not None and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(lambda: asyncio.create_task(coro))

    def _on_ble_notify(self, _sender: Any, data: bytearray) -> None:
        raw = bytes(data)
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if self._loop is not None and running is not self._loop and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._handle_notify_bytes, raw)
            return
        self._handle_notify_bytes(raw)

    def _handle_notify_bytes(self, raw: bytes) -> None:
        frames = self._reassembler.feed(raw)
        for frame in frames:
            self._process_incoming_frame(frame)

    def _process_incoming_frame(self, frame: Frame) -> None:
        entry = self._record_log("RX", frame.raw, describe_frame(frame))
        self._schedule_coro(self._emit("frame_log", entry))
        before = self.state.to_dict()
        key = (frame.magic, frame.opcode)
        is_unsolicited = key not in self._pending
        self._apply_frame_to_state(frame, unsolicited=is_unsolicited)
        fut = self._pending.pop(key, None)
        if fut is not None and not fut.done():
            fut.set_result(frame)
        elif self.state.to_dict() != before:
            self._schedule_coro(self._emit_state())

    def _apply_frame_to_state(self, frame: Frame, unsolicited: bool = False) -> None:
        op = frame.opcode
        p = frame.payload
        try:
            if frame.magic == HEADER_MAGIC_ED:
                if op in (Opcode.QUERY_SUB_OUT, Opcode.SET_SUB_OUT) and p:
                    self.state.sub_out_level = decode_sub_out(p).label
                return

            if op == Opcode.QUERY_NAME and p:
                self.state.device_name = decode_name(p)
            elif op == Opcode.QUERY_FIRMWARE and p:
                self.state.firmware = decode_firmware(p)
            elif op == Opcode.QUERY_CLASSIC_MAC and p:
                self.state.classic_mac = decode_classic_mac(p)
            elif op == Opcode.QUERY_CAPABILITIES and p:
                self.state.capabilities = decode_capabilities(p)
            elif (
                op in (Opcode.QUERY_INPUT, Opcode.SET_INPUT)
                and len(p) >= 2
                and p[0] in (M60_INPUT_GROUP, M90_INPUT_GROUP)
            ):
                self.state.input_source = decode_input(p, self.state.model).label
            elif op in (Opcode.QUERY_VOLUME, Opcode.SET_VOLUME):
                if len(p) >= 2:
                    max_v, cur_v = decode_volume(p)
                    self.state.max_volume = max_v or max_volume_for_model(self.state.model)
                    self.state.volume = cur_v
                elif unsolicited and len(p) == 1 and 0 <= p[0] <= self.state.max_volume:
                    self.state.volume = int(p[0])
            elif op == Opcode.QUERY_EQ_PRESET and p:
                self.state.eq_preset = decode_eq_preset(p, self.state.model).label
            elif op == Opcode.SET_EQ_PRESET and unsolicited and len(p) == 1:
                try:
                    self.state.eq_preset = decode_eq_preset(p, self.state.model).label
                except ValueError:
                    pass
            elif op == Opcode.QUERY_CUSTOM_EQ and len(p) >= 2:
                self.state.custom_eq = decode_custom_eq(p)
            elif op == Opcode.QUERY_LDAC and p:
                self.state.ldac_mode = decode_ldac(p).label
            elif op == Opcode.QUERY_CODEC_M90 and p:
                self.state.ldac_mode = decode_codec_m90(p).label
            elif op == Opcode.SET_CODEC_M90 and len(p) >= 2 and p[0] == 0x0F:
                try:
                    self.state.ldac_mode = LdacMode(p[1]).label
                except ValueError:
                    pass
            elif op == Opcode.QUERY_PROMPT_TONE and p:
                self.state.prompt_tone = decode_prompt_tone(p)
            elif op in (Opcode.QUERY_SMART_LIGHT, Opcode.SET_SMART_LIGHT) and len(p) >= 3:
                timer, sens = decode_smart_light(p)
                self.state.smart_light_timer = timer.label
                self.state.smart_light_sensitivity = sens.label
            elif op == Opcode.QUERY_MULTIPOINT and p:
                self.state.multipoint = decode_multipoint(p)
            elif op == Opcode.QUERY_POWER_SAVE and p:
                self.state.power_save = decode_power_save(p)
            elif op == Opcode.QUERY_TIMED_OFF and p:
                self.state.timed_off_minutes = decode_timed_off(p)
            elif op == Opcode.QUERY_A2DP_STATE and p:
                code, label = decode_a2dp_state(p)
                self.state.a2dp_state_code = code
                self.state.a2dp_state = label
            elif op == Opcode.QUERY_AUDIO_DECODING and p:
                code, label = decode_audio_decoding(p)
                self.state.audio_decoding_code = code
                self.state.audio_decoding = label
        except Exception:
            logger.debug("Could not decode frame opcode 0x%02X", op, exc_info=True)

    async def _send_frame(
        self,
        raw_frame: bytes,
        expect_reply: bool = True,
        timeout: float = 4.0,
        log_frame: bool = True,
    ) -> Frame | None:
        if not self.state.connected:
            raise RuntimeError("Speaker is not connected over BLE.")

        req = parse_frame(raw_frame)
        async with self._cmd_lock:
            if log_frame:
                log_entry = self._record_log("TX", raw_frame, describe_frame(req))
                await self._emit("frame_log", log_entry)

            if self.state.demo_mode and self._sim is not None:
                replies = self._sim.handle_request(raw_frame)
                last_frame: Frame | None = None
                for reply_bytes in replies:
                    for frame in self._reassembler.feed(reply_bytes):
                        if log_frame:
                            rx_entry = self._record_log(
                                "RX", frame.raw, describe_frame(frame)
                            )
                            await self._emit("frame_log", rx_entry)
                        self._apply_frame_to_state(frame)
                        last_frame = frame
                return last_frame

            if self._client is None or not self._client.is_connected:
                raise RuntimeError("BLE client is disconnected.")

            loop = asyncio.get_running_loop()
            fut: asyncio.Future[Frame] | None = None
            pending_key = (req.magic, req.opcode)
            if expect_reply:
                prev = self._pending.pop(pending_key, None)
                if prev and not prev.done():
                    prev.cancel()
                fut = loop.create_future()
                self._pending[pending_key] = fut

            await self._client.write_gatt_char(
                M60_WRITE_CHAR_UUID, raw_frame, response=False
            )

            if not expect_reply or fut is None:
                return None

            try:
                return await asyncio.wait_for(fut, timeout=timeout)
            except asyncio.TimeoutError as exc:
                self._pending.pop(pending_key, None)
                raise TimeoutError(
                    f"Timed out waiting for speaker reply to opcode 0x{req.opcode:02X}"
                ) from exc

    # ------------------------------------------------------------------
    # State Refresh & High-Level Commands
    # ------------------------------------------------------------------

    async def refresh_all(self) -> dict[str, Any]:
        if not self.state.connected:
            return self.state.to_dict()

        queries = [
            cmd_query_name(),
            cmd_query_firmware(),
            cmd_query_classic_mac(),
            cmd_query_capabilities(),
            cmd_query_input(),
            cmd_query_volume(),
            cmd_query_eq_preset(),
            cmd_query_custom_eq(),
            cmd_query_prompt_tone(),
            cmd_query_a2dp_state(),
            cmd_query_audio_decoding(),
        ]
        if self.state.model == MODEL_M90:
            queries.extend(
                [
                    cmd_query_codec_m90(),
                    cmd_query_sub_out(),
                    cmd_query_multipoint(),
                    cmd_query_power_save(),
                    cmd_query_timed_off(),
                ]
            )
        else:
            queries.extend(
                [
                    cmd_query_ldac(),
                    cmd_query_smart_light(),
                ]
            )
        for q in queries:
            try:
                await self._send_frame(q, expect_reply=True, timeout=3.0)
            except Exception as exc:
                logger.warning("Query failed (%s): %s", q.hex(" ").upper(), exc)
        await self._emit_state()
        return self.state.to_dict()

    async def sync_fast_state(self) -> bool:
        """Poll fast-changing speaker registers to catch physical button changes."""
        if (
            not self.state.connected
            or self.state.input_settling
            or self._cmd_lock.locked()
        ):
            return False

        before = self.state.to_dict()
        queries = [
            cmd_query_volume(),
            cmd_query_input(),
            cmd_query_eq_preset(),
            cmd_query_audio_decoding(),
        ]
        if self._poll_cycle % 5 == 0:
            queries.append(cmd_query_a2dp_state())
            if self.state.model == MODEL_M90:
                queries.extend(
                    [
                        cmd_query_sub_out(),
                        cmd_query_multipoint(),
                        cmd_query_power_save(),
                        cmd_query_timed_off(),
                    ]
                )
            else:
                queries.append(cmd_query_smart_light())
        self._poll_cycle += 1

        for q in queries:
            if not self.state.connected:
                return False
            try:
                await self._send_frame(
                    q, expect_reply=True, timeout=2.0, log_frame=False
                )
            except Exception:
                logger.debug("Background sync query failed", exc_info=True)

        if self.state.to_dict() != before:
            await self._emit_state()
            return True
        return False

    async def _poll_loop(self) -> None:
        try:
            while self.state.connected and not self.state.demo_mode:
                await asyncio.sleep(2.0)
                if self.state.connected and not self.state.demo_mode:
                    await self.sync_fast_state()
        except asyncio.CancelledError:
            pass

    async def set_volume(self, level: int) -> dict[str, Any]:
        max_v = self.state.max_volume or max_volume_for_model(self.state.model)
        clamped = max(0, min(max_v, int(level)))
        await self._send_frame(
            cmd_set_volume(clamped, max_volume=max_v), expect_reply=True
        )
        self.state.volume = clamped
        await self._emit_state()
        return self.state.to_dict()

    async def step_volume(self, delta: int) -> dict[str, Any]:
        return await self.set_volume(self.state.volume + delta)

    async def set_input(self, source: str) -> dict[str, Any]:
        src = (
            M90InputSource.from_str(source)
            if self.state.model == MODEL_M90
            else InputSource.from_str(source)
        )
        await self._send_frame(
            cmd_set_input(src, model=self.state.model), expect_reply=True
        )
        self.state.input_source = src.label
        self.state.input_settling = not self.state.demo_mode
        self.state.notice = (
            f"Switched input to {src.label.upper()}."
            if self.state.demo_mode
            else f"Switching input to {src.label.upper()} (settling ~2.5s)..."
        )
        await self._emit_state()

        if self.state.demo_mode:
            await self._send_frame(cmd_query_input(), expect_reply=True)
            await self._send_frame(cmd_query_audio_decoding(), expect_reply=True)
            await self._send_frame(cmd_query_a2dp_state(), expect_reply=True)
            await self._emit_state()
        else:
            if self._settle_task and not self._settle_task.done():
                self._settle_task.cancel()
            self._settle_task = asyncio.create_task(self._delayed_input_requery())
        return self.state.to_dict()

    async def _delayed_input_requery(self) -> None:
        try:
            await asyncio.sleep(2.6)
            if self.state.connected:
                await self._send_frame(cmd_query_input(), expect_reply=True)
                await self._send_frame(cmd_query_audio_decoding(), expect_reply=True)
                await self._send_frame(cmd_query_a2dp_state(), expect_reply=True)
                self.state.input_settling = False
                self.state.notice = None
                await self._emit_state()
        except asyncio.CancelledError:
            pass
        except Exception:
            self.state.input_settling = False
            await self._emit_state()

    async def send_playback(self, action: str) -> dict[str, Any]:
        act = PlaybackAction.from_str(action)
        await self._send_frame(cmd_playback(act), expect_reply=False)
        return self.state.to_dict()

    async def set_eq_preset(self, preset: str) -> dict[str, Any]:
        if self.state.model == MODEL_M90:
            eq: EqPreset | M90EqPreset = M90EqPreset.from_str(preset)
            is_custom = eq == M90EqPreset.CUSTOM
        else:
            eq = EqPreset.from_str(preset)
            is_custom = eq == EqPreset.CUSTOMIZED
        await self._send_frame(cmd_set_eq_preset(eq), expect_reply=True)
        self.state.eq_preset = eq.label
        await self._send_frame(cmd_query_eq_preset(), expect_reply=True)
        if is_custom:
            await self._send_frame(cmd_query_custom_eq(), expect_reply=True)
        await self._emit_state()
        return self.state.to_dict()

    async def _ensure_customized_preset(self) -> None:
        target = (
            M90EqPreset.CUSTOM if self.state.model == MODEL_M90 else EqPreset.CUSTOMIZED
        )
        if self.state.eq_preset != target.label:
            await self._send_frame(cmd_set_eq_preset(target), expect_reply=True)
            self.state.eq_preset = target.label

    async def set_custom_eq_band(
        self,
        index: int,
        gain_db: float,
        freq: int | None = None,
        q_raw: int | None = None,
    ) -> dict[str, Any]:
        max_idx = 8 if self.state.model == MODEL_M90 else 5
        if not 0 <= index <= max_idx:
            raise ValueError(
                f"{self.state.model.upper()} custom EQ supports band indices 0..{max_idx}"
            )
        await self._ensure_customized_preset()
        if not self.state.custom_eq.bands or len(self.state.custom_eq.bands) <= max_idx:
            self.state.custom_eq.bands = default_custom_eq_bands(self.state.model)
        current = self.state.custom_eq.bands[index]
        updated = EqBand.from_db(
            index=index,
            freq=current.freq if freq is None else int(freq),
            gain_db=gain_db,
            q_raw=current.q_raw if q_raw is None else int(q_raw),
            filter_raw=current.filter_raw,
        )
        await self._send_frame(
            cmd_set_custom_eq_band(updated, model=self.state.model), expect_reply=True
        )
        self.state.custom_eq.bands[index] = updated
        await self._emit_state()
        return self.state.to_dict()

    async def apply_custom_eq_all(
        self,
        bands: list[dict[str, Any]],
        name: str | None = None,
    ) -> dict[str, Any]:
        max_idx = 8 if self.state.model == MODEL_M90 else 5
        await self._ensure_customized_preset()
        if not self.state.custom_eq.bands or len(self.state.custom_eq.bands) <= max_idx:
            self.state.custom_eq.bands = default_custom_eq_bands(self.state.model)
        for item in bands:
            idx = int(item["index"])
            if not 0 <= idx <= max_idx:
                continue
            cur = self.state.custom_eq.bands[idx]
            updated = EqBand.from_db(
                index=idx,
                freq=int(item.get("freq", cur.freq)),
                gain_db=float(item["gain_db"]),
                q_raw=int(item.get("q_raw", cur.q_raw)),
                filter_raw=cur.filter_raw,
            )
            await self._send_frame(
                cmd_set_custom_eq_band(updated, model=self.state.model),
                expect_reply=True,
            )
            self.state.custom_eq.bands[idx] = updated
        if name is not None:
            await self._send_frame(cmd_set_custom_eq_meta(name), expect_reply=True)
            self.state.custom_eq.name = name
        await self._send_frame(cmd_query_custom_eq(), expect_reply=True)
        await self._emit_state()
        return self.state.to_dict()

    async def set_smart_light(self, timer: str, sensitivity: str) -> dict[str, Any]:
        if self.state.model == MODEL_M90:
            raise ValueError("Smart Touch Light settings apply only to Edifier M60.")
        t = SmartLightTimer.from_str(timer)
        s = SmartLightSensitivity.from_str(sensitivity)
        await self._send_frame(cmd_set_smart_light(t, s), expect_reply=True)
        self.state.smart_light_timer = t.label
        self.state.smart_light_sensitivity = s.label
        await self._emit_state()
        return self.state.to_dict()

    async def set_prompt_tone(self, enabled: bool) -> dict[str, Any]:
        await self._send_frame(cmd_set_prompt_tone(enabled), expect_reply=True)
        self.state.prompt_tone = bool(enabled)
        await self._emit_state()
        return self.state.to_dict()

    async def set_ldac(self, mode: str) -> dict[str, Any]:
        m = LdacMode.from_str(mode)
        self.state.ldac_mode = m.label
        if self.state.model == MODEL_M90:
            try:
                await self._send_frame(
                    cmd_set_codec_m90(m), expect_reply=True, timeout=3.0
                )
                await self._send_frame(
                    cmd_query_codec_m90(), expect_reply=True, timeout=2.0
                )
                self.state.notice = (
                    "M90 LDAC codec preference sent. Note: changing LDAC mode may restart "
                    "the speaker's Bluetooth link."
                )
            except Exception:
                self.state.notice = (
                    "M90 LDAC command sent. Reconnect Bluetooth if the link restarted."
                )
            await self._emit_state()
            return self.state.to_dict()

        try:
            await self._send_frame(cmd_set_ldac(m), expect_reply=True, timeout=3.0)
            await self._send_frame(cmd_query_ldac(), expect_reply=True, timeout=2.0)
            # Writing LDAC may reset smart-light sensitivity on M60.
            await self._send_frame(cmd_query_smart_light(), expect_reply=True, timeout=2.0)
            self.state.notice = (
                "LDAC preference updated. Note: smart-light sensitivity may reset after LDAC changes."
            )
        except Exception:
            # M60 documentation explicitly notes 0x49 can drop BLE/Classic without ACK despite storing.
            self.state.notice = (
                "LDAC command sent. The M60 may drop Bluetooth briefly to apply the codec; "
                "reconnect via Bluetooth if the link closed."
            )
        await self._emit_state()
        return self.state.to_dict()

    async def set_sub_out(self, level: str) -> dict[str, Any]:
        if self.state.model != MODEL_M90:
            raise ValueError("Sub Out level control is only supported on Edifier M90.")
        lvl = SubOutLevel.from_str(level)
        await self._send_frame(cmd_set_sub_out(lvl), expect_reply=True)
        self.state.sub_out_level = lvl.label
        await self._emit_state()
        return self.state.to_dict()

    async def set_multipoint(self, enabled: bool) -> dict[str, Any]:
        if self.state.model != MODEL_M90:
            raise ValueError("Bluetooth multipoint is only supported on Edifier M90.")
        await self._send_frame(cmd_set_multipoint(enabled), expect_reply=True)
        await self._send_frame(cmd_query_multipoint(), expect_reply=True)
        await self._emit_state()
        return self.state.to_dict()

    async def set_power_save(self, enabled: bool) -> dict[str, Any]:
        if self.state.model != MODEL_M90:
            raise ValueError("Power-save mode is only supported on Edifier M90.")
        await self._send_frame(cmd_set_power_save(enabled), expect_reply=True)
        await self._send_frame(cmd_query_power_save(), expect_reply=True)
        await self._emit_state()
        return self.state.to_dict()

    async def set_timed_off(self, minutes: int) -> dict[str, Any]:
        if self.state.model != MODEL_M90:
            raise ValueError("Timed power-off is only supported on Edifier M90.")
        mins = max(0, int(minutes))
        if mins == 0:
            await self._send_frame(cmd_cancel_timed_off(), expect_reply=True)
        else:
            await self._send_frame(cmd_set_timed_off(mins), expect_reply=True)
        await self._send_frame(cmd_query_timed_off(), expect_reply=True)
        await self._emit_state()
        return self.state.to_dict()

    async def power_off_device(self) -> dict[str, Any]:
        if self.state.model != MODEL_M90:
            raise ValueError("Remote BLE shutdown (0xCE) is only supported on Edifier M90.")
        try:
            await self._send_frame(cmd_power_off_device(), expect_reply=False)
        except Exception:
            pass
        if self.state.demo_mode:
            self.state.notice = (
                "Sent M90 shutdown command (0xCE) to emulator. On real hardware, the speaker powers off immediately."
            )
            await self._emit_state()
            return self.state.to_dict()
        state = await self.disconnect()
        state["notice"] = "Sent shutdown command (0xCE) to Edifier M90."
        return state

    async def rename_device(self, name: str) -> dict[str, Any]:
        frame = cmd_set_name(name)
        await self._send_frame(frame, expect_reply=True)
        await self._send_frame(cmd_query_name(), expect_reply=True)
        await self._emit_state()
        return self.state.to_dict()

    async def disconnect_bt_audio(self) -> dict[str, Any]:
        try:
            await self._send_frame(cmd_disconnect_bt_audio(), expect_reply=False)
        except Exception:
            pass
        self.state.a2dp_state = "closed"
        self.state.a2dp_state_code = 0x03
        self.state.notice = (
            "Sent Bluetooth audio disconnect (0xCD). Reconnect from OS Bluetooth settings when needed."
        )
        await self._emit_state()
        return self.state.to_dict()

    async def send_raw_hex(
        self, hex_str: str, expect_reply: bool = True, auto_checksum: bool = False
    ) -> dict[str, Any]:
        cleaned = hex_str.replace(",", " ").strip()
        raw = bytes.fromhex(cleaned)
        if auto_checksum:
            if len(raw) < 5:
                raise ProtocolError(
                    "Need at least 5 bytes (AA EC OP LEN_HI LEN_LO) to append checksum."
                )
            raw = raw + bytes([sum(raw) & 0xFF])
        reply = await self._send_frame(raw, expect_reply=expect_reply, timeout=3.0)
        await self._emit_state()
        return {
            "sent_hex": raw.hex(" ").upper(),
            "reply_hex": reply.hex_str if reply else None,
        }
