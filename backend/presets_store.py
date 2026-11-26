"""Persistent local configuration and saved custom 6-band EQ profiles."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import threading
import uuid


@dataclass
class SavedEqProfile:
    id: str
    name: str
    gains_db: list[float]
    freqs: list[int]
    builtin: bool = False


DEFAULT_STARTER_PROFILES: list[dict] = [
    {
        "id": "builtin-flat",
        "name": "Flat Reference",
        "gains_db": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "freqs": [62, 250, 1000, 4000, 8000, 16000],
        "builtin": True,
    },
    {
        "id": "builtin-warm-desk",
        "name": "Warm Nearfield",
        "gains_db": [1.5, 0.5, 0.0, -0.5, 0.5, 0.5],
        "freqs": [62, 250, 1000, 4000, 8000, 16000],
        "builtin": True,
    },
    {
        "id": "builtin-vocal",
        "name": "Vocal & Podcast",
        "gains_db": [-1.0, -0.5, 1.5, 2.0, 1.0, 0.0],
        "freqs": [62, 250, 1000, 4000, 8000, 16000],
        "builtin": True,
    },
    {
        "id": "builtin-punch",
        "name": "Late-Night Punch",
        "gains_db": [2.5, 1.0, 0.0, 1.0, 1.5, 1.0],
        "freqs": [62, 250, 1000, 4000, 8000, 16000],
        "builtin": True,
    },
]


def _default_config_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "EdifierM60Desktop" / "config.json"
    return Path.cwd() / "data" / "config.json"


class PresetsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or _default_config_path()
        self._lock = threading.Lock()
        self._data: dict = {}
        self._load()

    def _load(self) -> None:
        with self._lock:
            if self.path.exists():
                try:
                    self._data = json.loads(self.path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    self._data = {}
            if not isinstance(self._data, dict):
                self._data = {}
            self._data.setdefault("last_device_address", None)
            self._data.setdefault("last_device_name", None)
            self._data.setdefault("hotkey_sync_enabled", False)
            self._data.setdefault("lock_usb_volume_on_sync", True)
            if "saved_eq_presets" not in self._data or not isinstance(
                self._data["saved_eq_presets"], list
            ):
                self._data["saved_eq_presets"] = [dict(p) for p in DEFAULT_STARTER_PROFILES]
                self._save_locked()

    def _save_locked(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(self._data, indent=2), encoding="utf-8"
            )
        except OSError:
            # Fallback to workspace-local data dir if LocalAppData is unavailable.
            fallback = Path.cwd() / "data" / "config.json"
            if fallback != self.path:
                fallback.parent.mkdir(parents=True, exist_ok=True)
                fallback.write_text(
                    json.dumps(self._data, indent=2), encoding="utf-8"
                )
                self.path = fallback

    def get_settings(self) -> dict:
        with self._lock:
            return {
                "last_device_address": self._data.get("last_device_address"),
                "last_device_name": self._data.get("last_device_name"),
                "hotkey_sync_enabled": bool(self._data.get("hotkey_sync_enabled", False)),
                "lock_usb_volume_on_sync": bool(
                    self._data.get("lock_usb_volume_on_sync", True)
                ),
            }

    def set_last_device(self, address: str, name: str | None = None) -> None:
        with self._lock:
            self._data["last_device_address"] = address
            if name:
                self._data["last_device_name"] = name
            self._save_locked()

    def set_hotkey_settings(self, enabled: bool, lock_usb_100: bool) -> dict:
        with self._lock:
            self._data["hotkey_sync_enabled"] = bool(enabled)
            self._data["lock_usb_volume_on_sync"] = bool(lock_usb_100)
            self._save_locked()
            return {
                "last_device_address": self._data.get("last_device_address"),
                "last_device_name": self._data.get("last_device_name"),
                "hotkey_sync_enabled": self._data["hotkey_sync_enabled"],
                "lock_usb_volume_on_sync": self._data["lock_usb_volume_on_sync"],
            }

    def list_eq_presets(self) -> list[dict]:
        with self._lock:
            return [dict(p) for p in self._data.get("saved_eq_presets", [])]

    def save_eq_preset(
        self, name: str, gains_db: list[float], freqs: list[int]
    ) -> dict:
        clean_name = name.strip() or "Custom Profile"
        profile = SavedEqProfile(
            id=f"user-{uuid.uuid4().hex[:8]}",
            name=clean_name[:32],
            gains_db=[round(float(g), 1) for g in gains_db[:6]],
            freqs=[int(f) for f in freqs[:6]],
            builtin=False,
        )
        with self._lock:
            presets = self._data.setdefault("saved_eq_presets", [])
            presets.append(asdict(profile))
            self._save_locked()
        return asdict(profile)

    def delete_eq_preset(self, preset_id: str) -> bool:
        with self._lock:
            presets = self._data.get("saved_eq_presets", [])
            new_presets = [
                p
                for p in presets
                if not (p.get("id") == preset_id and not p.get("builtin", False))
            ]
            changed = len(new_presets) != len(presets)
            if changed:
                self._data["saved_eq_presets"] = new_presets
                self._save_locked()
            return changed
