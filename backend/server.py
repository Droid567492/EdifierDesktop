"""FastAPI REST + WebSocket server for Edifier M60 Desktop Control."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import logging
from pathlib import Path
import sys
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .autostart import is_autostart_enabled, set_autostart
from .ble_client import M60Controller
from .hotkeys import WindowsVolumeHotkeyBridge
from .icon import get_icon_ico_bytes, get_icon_png_bytes
from .presets_store import PresetsStore
from .protocol import ProtocolError
from .usb_audio import UsbAudioManager

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request Models
# ---------------------------------------------------------------------------


class ScanRequest(BaseModel):
    timeout: float = Field(default=6.0, ge=1.0, le=20.0)
    show_all: bool = False


class ConnectRequest(BaseModel):
    address: str


class DemoRequest(BaseModel):
    enabled: bool


class VolumeRequest(BaseModel):
    level: int = Field(ge=0, le=16)


class InputRequest(BaseModel):
    source: str


class PlaybackRequest(BaseModel):
    action: str


class EqPresetRequest(BaseModel):
    preset: str


class CustomEqBandRequest(BaseModel):
    index: int = Field(ge=0, le=5)
    gain_db: float = Field(ge=-3.0, le=3.0)
    freq: int | None = Field(default=None, ge=20, le=20000)
    q_raw: int | None = Field(default=None, ge=1, le=255)


class CustomEqBandItem(BaseModel):
    index: int = Field(ge=0, le=5)
    gain_db: float = Field(ge=-3.0, le=3.0)
    freq: int | None = Field(default=None, ge=20, le=20000)
    q_raw: int | None = Field(default=None, ge=1, le=255)


class CustomEqAllRequest(BaseModel):
    bands: list[CustomEqBandItem]
    name: str | None = None


class SaveEqProfileRequest(BaseModel):
    name: str = Field(min_length=1, max_length=32)
    gains_db: list[float] = Field(min_length=6, max_length=6)
    freqs: list[int] = Field(min_length=6, max_length=6)


class SmartLightRequest(BaseModel):
    timer: str
    sensitivity: str


class PromptToneRequest(BaseModel):
    enabled: bool


class LdacRequest(BaseModel):
    mode: str


class DeviceNameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=35)


class RawHexRequest(BaseModel):
    hex: str
    expect_reply: bool = True
    auto_checksum: bool = False


class UsbVolumeRequest(BaseModel):
    percent: int = Field(ge=0, le=100)


class UsbMuteRequest(BaseModel):
    muted: bool


class HotkeysRequest(BaseModel):
    enabled: bool
    lock_usb_100: bool = True


class AutostartRequest(BaseModel):
    enabled: bool


# ---------------------------------------------------------------------------
# App Factory
# ---------------------------------------------------------------------------


class AppContext:
    def __init__(self, store: PresetsStore | None = None) -> None:
        self.store = store or PresetsStore()
        self.ble = M60Controller()
        self.usb = UsbAudioManager()
        self.hotkeys: WindowsVolumeHotkeyBridge | None = None
        self.ws_clients: set[WebSocket] = set()
        self._last_usb_snapshot: dict[str, Any] = {}
        self._saved_mute_restore_vol: int = 8
        self._usb_poll_task: asyncio.Task[None] | None = None

    async def broadcast(self, event_type: str, data: dict[str, Any]) -> None:
        if not self.ws_clients:
            return
        message = {"type": event_type, "data": data}
        stale: list[WebSocket] = []
        for ws in list(self.ws_clients):
            try:
                await ws.send_json(message)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self.ws_clients.discard(ws)

    async def full_snapshot(self) -> dict[str, Any]:
        usb_state = await self.usb.get_status()
        self._last_usb_snapshot = usb_state
        settings = self.store.get_settings()
        settings["hotkey_active"] = bool(self.hotkeys and self.hotkeys.active)
        settings["hotkey_error"] = self.hotkeys.last_error if self.hotkeys else None
        settings["autostart_enabled"] = is_autostart_enabled()
        settings["autostart_error"] = None
        return {
            "ble_state": self.ble.state.to_dict(),
            "usb_state": usb_state,
            "saved_eq_presets": self.store.list_eq_presets(),
            "settings": settings,
            "recent_logs": self.ble.recent_logs(),
        }

    async def _hotkey_step(self, delta: int) -> None:
        if not self.ble.state.connected:
            return
        try:
            await self.ble.step_volume(delta)
            settings = self.store.get_settings()
            if settings.get("lock_usb_volume_on_sync"):
                usb = await self.usb.get_status()
                if usb.get("connected") and (
                    usb.get("volume_percent") != 100 or usb.get("muted")
                ):
                    usb_new = await self.usb.lock_bit_perfect()
                    self._last_usb_snapshot = usb_new
                    await self.broadcast("usb_state", usb_new)
        except Exception as exc:
            logger.debug("Hotkey step error: %s", exc)

    async def _hotkey_toggle_mute(self) -> None:
        if not self.ble.state.connected:
            return
        try:
            cur = self.ble.state.volume
            if cur > 0:
                self._saved_mute_restore_vol = cur
                await self.ble.set_volume(0)
            else:
                await self.ble.set_volume(max(1, self._saved_mute_restore_vol))
        except Exception as exc:
            logger.debug("Hotkey mute error: %s", exc)


def create_app(
    store: PresetsStore | None = None,
    enable_hotkeys: bool = True,
    static_dir: Path | None = None,
) -> FastAPI:
    ctx = AppContext(store=store)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        loop = asyncio.get_running_loop()

        async def on_ble_event(event_type: str, data: dict[str, Any]) -> None:
            await ctx.broadcast(event_type, data)

        ctx.ble.add_listener(on_ble_event)

        if enable_hotkeys:
            ctx.hotkeys = WindowsVolumeHotkeyBridge(
                loop=loop,
                on_step=ctx._hotkey_step,
                on_toggle_mute=ctx._hotkey_toggle_mute,
            )
            if ctx.store.get_settings().get("hotkey_sync_enabled"):
                ctx.hotkeys.start()

        async def poll_usb() -> None:
            while True:
                try:
                    await asyncio.sleep(3.0)
                    usb_state = await ctx.usb.get_status()
                    if usb_state != ctx._last_usb_snapshot:
                        ctx._last_usb_snapshot = usb_state
                        await ctx.broadcast("usb_state", usb_state)
                except asyncio.CancelledError:
                    break
                except Exception:
                    logger.debug("USB poll error", exc_info=True)

        ctx._usb_poll_task = asyncio.create_task(poll_usb())
        app.state.ctx = ctx
        try:
            yield
        finally:
            if ctx._usb_poll_task:
                ctx._usb_poll_task.cancel()
            if ctx.hotkeys:
                ctx.hotkeys.stop()
            await ctx.ble.disconnect()

    app = FastAPI(title="Edifier M60 Desktop Control", lifespan=lifespan)
    app.state.ctx = ctx

    def _raise_http(exc: Exception) -> None:
        if isinstance(exc, (ValueError, ProtocolError)):
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if isinstance(exc, TimeoutError):
            raise HTTPException(status_code=504, detail=str(exc)) from exc
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # ------------------------------------------------------------------
    # State & BLE Connection Endpoints
    # ------------------------------------------------------------------

    @app.get("/api/state")
    async def get_state() -> dict[str, Any]:
        return await ctx.full_snapshot()

    @app.post("/api/ble/scan")
    async def scan_ble(req: ScanRequest) -> dict[str, Any]:
        try:
            devices = await ctx.ble.scan(timeout=req.timeout, show_all=req.show_all)
            return {"devices": devices}
        except Exception as exc:
            _raise_http(exc)

    @app.post("/api/ble/connect")
    async def connect_ble(req: ConnectRequest) -> dict[str, Any]:
        try:
            state = await ctx.ble.connect(req.address)
            ctx.store.set_last_device(req.address, state.get("device_name"))
            settings = ctx.store.get_settings()
            settings["hotkey_active"] = bool(ctx.hotkeys and ctx.hotkeys.active)
            settings["autostart_enabled"] = is_autostart_enabled()
            await ctx.broadcast("settings", settings)
            return {"ble_state": state}
        except Exception as exc:
            _raise_http(exc)

    @app.post("/api/ble/disconnect")
    async def disconnect_ble() -> dict[str, Any]:
        state = await ctx.ble.disconnect()
        return {"ble_state": state}

    @app.post("/api/ble/refresh")
    async def refresh_ble() -> dict[str, Any]:
        try:
            state = await ctx.ble.refresh_all()
            return {"ble_state": state}
        except Exception as exc:
            _raise_http(exc)

    @app.post("/api/demo")
    async def toggle_demo(req: DemoRequest) -> dict[str, Any]:
        state = await ctx.ble.set_demo_mode(req.enabled)
        return {"ble_state": state}

    # ------------------------------------------------------------------
    # Speaker Control Endpoints
    # ------------------------------------------------------------------

    @app.post("/api/volume")
    async def set_volume(req: VolumeRequest) -> dict[str, Any]:
        try:
            state = await ctx.ble.set_volume(req.level)
            return {"ble_state": state}
        except Exception as exc:
            _raise_http(exc)

    @app.post("/api/input")
    async def set_input(req: InputRequest) -> dict[str, Any]:
        try:
            state = await ctx.ble.set_input(req.source)
            return {"ble_state": state}
        except Exception as exc:
            _raise_http(exc)

    @app.post("/api/playback")
    async def media_playback(req: PlaybackRequest) -> dict[str, Any]:
        try:
            state = await ctx.ble.send_playback(req.action)
            return {"ble_state": state}
        except Exception as exc:
            _raise_http(exc)

    @app.post("/api/eq/preset")
    async def set_eq_preset(req: EqPresetRequest) -> dict[str, Any]:
        try:
            state = await ctx.ble.set_eq_preset(req.preset)
            return {"ble_state": state}
        except Exception as exc:
            _raise_http(exc)

    @app.post("/api/eq/custom/band")
    async def set_custom_eq_band(req: CustomEqBandRequest) -> dict[str, Any]:
        try:
            state = await ctx.ble.set_custom_eq_band(
                index=req.index,
                gain_db=req.gain_db,
                freq=req.freq,
                q_raw=req.q_raw,
            )
            return {"ble_state": state}
        except Exception as exc:
            _raise_http(exc)

    @app.post("/api/eq/custom/all")
    async def set_custom_eq_all(req: CustomEqAllRequest) -> dict[str, Any]:
        try:
            bands_dicts = [b.model_dump(exclude_none=True) for b in req.bands]
            state = await ctx.ble.apply_custom_eq_all(bands_dicts, name=req.name)
            return {"ble_state": state}
        except Exception as exc:
            _raise_http(exc)

    @app.get("/api/eq/saved")
    async def list_saved_eq() -> dict[str, Any]:
        return {"presets": ctx.store.list_eq_presets()}

    @app.post("/api/eq/saved")
    async def save_eq_profile(req: SaveEqProfileRequest) -> dict[str, Any]:
        created = ctx.store.save_eq_preset(req.name, req.gains_db, req.freqs)
        presets = ctx.store.list_eq_presets()
        await ctx.broadcast("saved_eq_presets", {"presets": presets})
        return {"preset": created, "presets": presets}

    @app.delete("/api/eq/saved/{preset_id}")
    async def delete_eq_profile(preset_id: str) -> dict[str, Any]:
        deleted = ctx.store.delete_eq_preset(preset_id)
        if not deleted:
            raise HTTPException(
                status_code=404, detail="Preset not found or is built-in."
            )
        presets = ctx.store.list_eq_presets()
        await ctx.broadcast("saved_eq_presets", {"presets": presets})
        return {"presets": presets}

    @app.post("/api/smart-light")
    async def set_smart_light(req: SmartLightRequest) -> dict[str, Any]:
        try:
            state = await ctx.ble.set_smart_light(req.timer, req.sensitivity)
            return {"ble_state": state}
        except Exception as exc:
            _raise_http(exc)

    @app.post("/api/prompt-tone")
    async def set_prompt_tone(req: PromptToneRequest) -> dict[str, Any]:
        try:
            state = await ctx.ble.set_prompt_tone(req.enabled)
            return {"ble_state": state}
        except Exception as exc:
            _raise_http(exc)

    @app.post("/api/ldac")
    async def set_ldac(req: LdacRequest) -> dict[str, Any]:
        try:
            state = await ctx.ble.set_ldac(req.mode)
            return {"ble_state": state}
        except Exception as exc:
            _raise_http(exc)

    @app.post("/api/device/name")
    async def rename_device(req: DeviceNameRequest) -> dict[str, Any]:
        try:
            state = await ctx.ble.rename_device(req.name)
            return {"ble_state": state}
        except Exception as exc:
            _raise_http(exc)

    @app.post("/api/device/disconnect-bt")
    async def disconnect_bt_audio() -> dict[str, Any]:
        try:
            state = await ctx.ble.disconnect_bt_audio()
            return {"ble_state": state}
        except Exception as exc:
            _raise_http(exc)

    @app.post("/api/raw")
    async def send_raw(req: RawHexRequest) -> dict[str, Any]:
        try:
            return await ctx.ble.send_raw_hex(
                req.hex,
                expect_reply=req.expect_reply,
                auto_checksum=req.auto_checksum,
            )
        except Exception as exc:
            _raise_http(exc)

    # ------------------------------------------------------------------
    # USB-C Audio & Hotkeys Endpoints
    # ------------------------------------------------------------------

    @app.get("/api/usb/status")
    async def get_usb_status() -> dict[str, Any]:
        usb_state = await ctx.usb.get_status(force_pnp=True)
        ctx._last_usb_snapshot = usb_state
        return {"usb_state": usb_state}

    @app.post("/api/usb/volume")
    async def set_usb_volume(req: UsbVolumeRequest) -> dict[str, Any]:
        usb_state = await ctx.usb.set_volume(req.percent)
        ctx._last_usb_snapshot = usb_state
        await ctx.broadcast("usb_state", usb_state)
        return {"usb_state": usb_state}

    @app.post("/api/usb/mute")
    async def set_usb_mute(req: UsbMuteRequest) -> dict[str, Any]:
        usb_state = await ctx.usb.set_muted(req.muted)
        ctx._last_usb_snapshot = usb_state
        await ctx.broadcast("usb_state", usb_state)
        return {"usb_state": usb_state}

    @app.post("/api/usb/bit-perfect")
    async def set_usb_bit_perfect() -> dict[str, Any]:
        usb_state = await ctx.usb.lock_bit_perfect()
        ctx._last_usb_snapshot = usb_state
        await ctx.broadcast("usb_state", usb_state)
        return {"usb_state": usb_state}

    @app.post("/api/settings/hotkeys")
    async def set_hotkeys(req: HotkeysRequest) -> dict[str, Any]:
        settings = ctx.store.set_hotkey_settings(req.enabled, req.lock_usb_100)
        if ctx.hotkeys is not None:
            if req.enabled:
                ctx.hotkeys.start()
            else:
                ctx.hotkeys.stop()
            settings["hotkey_active"] = ctx.hotkeys.active
            settings["hotkey_error"] = ctx.hotkeys.last_error
        else:
            settings["hotkey_active"] = False
            settings["hotkey_error"] = "Hotkeys disabled in this runtime."
        settings["autostart_enabled"] = is_autostart_enabled()
        await ctx.broadcast("settings", settings)
        return {"settings": settings}

    @app.post("/api/settings/autostart")
    async def set_autostart_setting(req: AutostartRequest) -> dict[str, Any]:
        result = set_autostart(req.enabled)
        settings = ctx.store.get_settings()
        settings["hotkey_active"] = bool(ctx.hotkeys and ctx.hotkeys.active)
        settings["hotkey_error"] = ctx.hotkeys.last_error if ctx.hotkeys else None
        settings["autostart_enabled"] = bool(result["enabled"])
        settings["autostart_error"] = result.get("error")
        await ctx.broadcast("settings", settings)
        return {"settings": settings}

    # ------------------------------------------------------------------
    # WebSocket Live Updates
    # ------------------------------------------------------------------

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket) -> None:
        await ws.accept()
        ctx.ws_clients.add(ws)
        try:
            snapshot = await ctx.full_snapshot()
            await ws.send_json({"type": "snapshot", "data": snapshot})
            while True:
                # Keepalive / ignore ping frames
                await ws.receive_text()
        except WebSocketDisconnect:
            pass
        except Exception:
            pass
        finally:
            ctx.ws_clients.discard(ws)

    # ------------------------------------------------------------------
    # App Icons & Web Manifest
    # ------------------------------------------------------------------

    @app.get("/favicon.ico", include_in_schema=False)
    async def serve_favicon() -> Response:
        return Response(
            content=get_icon_ico_bytes(),
            media_type="image/x-icon",
            headers={"Cache-Control": "no-cache"},
        )

    @app.get("/icon.png", include_in_schema=False)
    async def serve_icon_png() -> Response:
        return Response(
            content=get_icon_png_bytes(256),
            media_type="image/png",
            headers={"Cache-Control": "no-cache"},
        )

    @app.get("/manifest.webmanifest", include_in_schema=False)
    async def serve_manifest() -> dict[str, Any]:
        return {
            "name": "Edifier M60 Studio Control",
            "short_name": "Edifier M60",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#0c0e13",
            "theme_color": "#0c0e13",
            "icons": [
                {
                    "src": "/icon.png",
                    "sizes": "256x256",
                    "type": "image/png",
                }
            ],
        }

    # ------------------------------------------------------------------
    # Static Built Frontend Serving
    # ------------------------------------------------------------------

    base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    dist_dir = static_dir or (base_dir / "frontend" / "dist")
    if dist_dir.exists() and (dist_dir / "index.html").exists():
        assets_dir = dist_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/", include_in_schema=False)
        async def serve_index() -> FileResponse:
            return FileResponse(dist_dir / "index.html")

    return app
