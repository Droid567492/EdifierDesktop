"""Persistent local configuration and saved custom EQ profiles (6-band M60 & 9-band M90)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import sys
import threading
import uuid

from .version import APP_VERSION


@dataclass
class SavedEqProfile:
    id: str
    name: str
    gains_db: list[float]
    freqs: list[int]
    model: str = "m60"
    builtin: bool = False


DEFAULT_STARTER_PROFILES: list[dict] = [
    {
        "id": "builtin-flat",
        "name": "Flat Reference",
        "model": "m60",
        "gains_db": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "freqs": [62, 250, 1000, 4000, 8000, 16000],
        "builtin": True,
    },
    {
        "id": "builtin-warm-desk",
        "name": "Warm Nearfield",
        "model": "m60",
        "gains_db": [1.5, 0.5, 0.0, -0.5, 0.5, 0.5],
        "freqs": [62, 250, 1000, 4000, 8000, 16000],
        "builtin": True,
    },
    {
        "id": "builtin-vocal",
        "name": "Vocal & Podcast",
        "model": "m60",
        "gains_db": [-1.0, -0.5, 1.5, 2.0, 1.0, 0.0],
        "freqs": [62, 250, 1000, 4000, 8000, 16000],
        "builtin": True,
    },
    {
        "id": "builtin-punch",
        "name": "Late-Night Punch",
        "model": "m60",
        "gains_db": [2.5, 1.0, 0.0, 1.0, 1.5, 1.0],
        "freqs": [62, 250, 1000, 4000, 8000, 16000],
        "builtin": True,
    },
    {
        "id": "builtin-m90-flat",
        "name": "Flat Reference",
        "model": "m90",
        "gains_db": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "freqs": [62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000],
        "builtin": True,
    },
    {
        "id": "builtin-m90-warm-desk",
        "name": "Warm Nearfield",
        "model": "m90",
        "gains_db": [1.5, 1.0, 0.5, 0.0, 0.0, -0.5, -0.5, 0.5, 0.5],
        "freqs": [62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000],
        "builtin": True,
    },
    {
        "id": "builtin-m90-vocal",
        "name": "Vocal & Podcast",
        "model": "m90",
        "gains_db": [-1.0, -1.0, -0.5, 0.5, 1.5, 2.0, 1.5, 1.0, 0.0],
        "freqs": [62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000],
        "builtin": True,
    },
    {
        "id": "builtin-m90-punch",
        "name": "Late-Night Punch",
        "model": "m90",
        "gains_db": [2.5, 2.0, 1.0, 0.0, 0.0, 0.5, 1.0, 1.5, 1.0],
        "freqs": [62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000],
        "builtin": True,
    },
]


def _default_config_path() -> Path:
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "EdifierM60Desktop" / "config.json"
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        base = Path(xdg) if xdg else (Path.home() / ".config")
        return base / "EdifierM60Desktop" / "config.json"
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
            self._data.setdefault("auto_check_updates", True)
            if not isinstance(self._data.get("dismissed_alerts"), list):
                self._data["dismissed_alerts"] = []
            if "saved_eq_presets" not in self._data or not isinstance(
                self._data["saved_eq_presets"], list
            ):
                self._data["saved_eq_presets"] = [dict(p) for p in DEFAULT_STARTER_PROFILES]
                self._save_locked()
            else:
                changed = False
                existing_ids = set()
                for preset in self._data["saved_eq_presets"]:
                    if isinstance(preset, dict):
                        if "id" in preset:
                            existing_ids.add(preset["id"])
                        if "model" not in preset:
                            preset["model"] = (
                                "m90" if len(preset.get("freqs", [])) == 9 else "m60"
                            )
                            changed = True
                for starter in DEFAULT_STARTER_PROFILES:
                    if starter["id"] not in existing_ids:
                        self._data["saved_eq_presets"].append(dict(starter))
                        changed = True
                if changed:
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

    def _settings_locked(self) -> dict:
        return {
            "last_device_address": self._data.get("last_device_address"),
            "last_device_name": self._data.get("last_device_name"),
            "hotkey_sync_enabled": bool(self._data.get("hotkey_sync_enabled", False)),
            "lock_usb_volume_on_sync": bool(
                self._data.get("lock_usb_volume_on_sync", True)
            ),
            "auto_check_updates": bool(self._data.get("auto_check_updates", True)),
            "dismissed_alerts": list(self._data.get("dismissed_alerts", [])),
            "app_version": APP_VERSION,
            "platform": sys.platform,
        }

    def get_settings(self) -> dict:
        with self._lock:
            return self._settings_locked()

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
            return self._settings_locked()

    def set_auto_check_updates(self, enabled: bool) -> dict:
        with self._lock:
            self._data["auto_check_updates"] = bool(enabled)
            self._save_locked()
            return self._settings_locked()

    def dismiss_alert(self, alert_id: str) -> dict:
        clean = alert_id.strip()
        with self._lock:
            alerts = self._data.setdefault("dismissed_alerts", [])
            if clean and clean not in alerts:
                alerts.append(clean)
                self._save_locked()
            return self._settings_locked()

    def reset_dismissed_alerts(self) -> dict:
        with self._lock:
            self._data["dismissed_alerts"] = []
            self._save_locked()
            return self._settings_locked()

    def list_eq_presets(self) -> list[dict]:
        with self._lock:
            return [dict(p) for p in self._data.get("saved_eq_presets", [])]

    def save_eq_preset(
        self,
        name: str,
        gains_db: list[float],
        freqs: list[int],
        model: str | None = None,
    ) -> dict:
        clean_name = name.strip() or "Custom Profile"
        resolved_model = (
            model.strip().lower()
            if model
            else ("m90" if len(freqs) == 9 or len(gains_db) == 9 else "m60")
        )
        max_bands = 9 if resolved_model == "m90" else 6
        profile = SavedEqProfile(
            id=f"user-{uuid.uuid4().hex[:8]}",
            name=clean_name[:32],
            gains_db=[round(float(g), 1) for g in gains_db[:max_bands]],
            freqs=[int(f) for f in freqs[:max_bands]],
            model=resolved_model,
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
