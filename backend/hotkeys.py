"""Opt-in Windows global media volume key hook -> M60 BLE hardware volume."""

from __future__ import annotations

import asyncio
import ctypes
from ctypes import wintypes
import logging
import sys
import threading
from typing import Callable, Coroutine, Any

logger = logging.getLogger(__name__)

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_NOREPEAT = 0x4000

VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF

HOTKEY_VOL_UP = 1
HOTKEY_VOL_DOWN = 2
HOTKEY_VOL_MUTE = 3


class WindowsVolumeHotkeyBridge:
    """Captures Windows Volume Up/Down/Mute keys when enabled and drives M60 BLE volume."""

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        on_step: Callable[[int], Coroutine[Any, Any, None]],
        on_toggle_mute: Callable[[], Coroutine[Any, Any, None]],
    ) -> None:
        self._loop = loop
        self._on_step = on_step
        self._on_toggle_mute = on_toggle_mute
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._running = False
        self._lock = threading.Lock()
        self.last_error: str | None = None

    @property
    def active(self) -> bool:
        return self._running

    def start(self) -> bool:
        if sys.platform != "win32":
            self.last_error = "Global RegisterHotKey is only supported on Windows."
            return False
        with self._lock:
            if self._running:
                return True
            self.last_error = None
            ready = threading.Event()
            self._thread = threading.Thread(
                target=self._run_loop, args=(ready,), daemon=True, name="M60Hotkeys"
            )
            self._thread.start()
            ready.wait(timeout=2.0)
            return self._running

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                return
            tid = self._thread_id
            self._running = False
        if tid and sys.platform == "win32":
            try:
                ctypes.windll.user32.PostThreadMessageW(tid, WM_QUIT, 0, 0)
            except Exception:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self._thread = None
        self._thread_id = None

    def _run_loop(self, ready: threading.Event) -> None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._thread_id = kernel32.GetCurrentThreadId()

        registered_ids: list[int] = []
        try:
            for hk_id, vk in (
                (HOTKEY_VOL_UP, VK_VOLUME_UP),
                (HOTKEY_VOL_DOWN, VK_VOLUME_DOWN),
                (HOTKEY_VOL_MUTE, VK_VOLUME_MUTE),
            ):
                if user32.RegisterHotKey(None, hk_id, MOD_NOREPEAT, vk):
                    registered_ids.append(hk_id)
                else:
                    logger.warning("RegisterHotKey failed for vk=0x%02X", vk)

            if not registered_ids:
                self.last_error = (
                    "Could not register Windows volume hotkeys (another app may hold them)."
                )
                self._running = False
                ready.set()
                return

            self._running = True
            ready.set()

            msg = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY:
                    hk_id = msg.wParam
                    if hk_id == HOTKEY_VOL_UP:
                        asyncio.run_coroutine_threadsafe(self._on_step(1), self._loop)
                    elif hk_id == HOTKEY_VOL_DOWN:
                        asyncio.run_coroutine_threadsafe(self._on_step(-1), self._loop)
                    elif hk_id == HOTKEY_VOL_MUTE:
                        asyncio.run_coroutine_threadsafe(
                            self._on_toggle_mute(), self._loop
                        )
        except Exception as exc:
            self.last_error = str(exc)
            logger.debug("Hotkey loop error", exc_info=True)
        finally:
            for hk_id in registered_ids:
                try:
                    user32.UnregisterHotKey(None, hk_id)
                except Exception:
                    pass
            self._running = False
            ready.set()
