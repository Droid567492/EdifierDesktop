"""Cross-platform login autostart integration (Windows Registry & Linux XDG)."""

from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Any

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE_NAME = "EdifierM60Control"
LINUX_DESKTOP_FILENAME = "edifier-m60-control.desktop"


def _linux_autostart_file() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else (Path.home() / ".config")
    return base / "autostart" / LINUX_DESKTOP_FILENAME


def get_startup_command() -> str:
    """Return the command line registered for login autostart."""
    if getattr(sys, "frozen", False):
        exe_path = Path(sys.executable).resolve()
        return f'"{exe_path}" --background'

    py_exe = Path(sys.executable).resolve()
    if sys.platform == "win32":
        pythonw = py_exe.with_name("pythonw.exe")
        runner = pythonw if pythonw.exists() else py_exe
    else:
        runner = py_exe
    app_script = (Path(__file__).resolve().parent / "app.py").resolve()
    return f'"{runner}" "{app_script}" --background'


def is_autostart_enabled() -> bool:
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_READ
            ) as key:
                val, _ = winreg.QueryValueEx(key, RUN_VALUE_NAME)
                return bool(str(val).strip())
        except FileNotFoundError:
            return False
        except OSError:
            return False

    if sys.platform.startswith("linux"):
        return _linux_autostart_file().exists()

    return False


def set_autostart(enabled: bool) -> dict[str, Any]:
    if sys.platform == "win32":
        try:
            import winreg

            if enabled:
                cmd = get_startup_command()
                with winreg.CreateKeyEx(
                    winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE
                ) as key:
                    winreg.SetValueEx(key, RUN_VALUE_NAME, 0, winreg.REG_SZ, cmd)
                return {"enabled": True, "command": cmd, "error": None}

            try:
                with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE
                ) as key:
                    winreg.DeleteValue(key, RUN_VALUE_NAME)
            except FileNotFoundError:
                pass
            return {"enabled": False, "command": None, "error": None}
        except OSError as exc:
            return {
                "enabled": is_autostart_enabled(),
                "command": None,
                "error": str(exc),
            }

    if sys.platform.startswith("linux"):
        desktop_file = _linux_autostart_file()
        try:
            if enabled:
                cmd = get_startup_command()
                desktop_file.parent.mkdir(parents=True, exist_ok=True)
                content = (
                    "[Desktop Entry]\n"
                    "Type=Application\n"
                    "Name=Edifier M60 / M90 Studio Control\n"
                    "Comment=Control Edifier M60 / M90 speakers over Bluetooth LE and USB-C\n"
                    f"Exec={cmd}\n"
                    "Icon=edifier-m60-control\n"
                    "Terminal=false\n"
                    "X-GNOME-Autostart-enabled=true\n"
                )
                desktop_file.write_text(content, encoding="utf-8")
                return {"enabled": True, "command": cmd, "error": None}

            if desktop_file.exists():
                desktop_file.unlink()
            return {"enabled": False, "command": None, "error": None}
        except OSError as exc:
            return {
                "enabled": is_autostart_enabled(),
                "command": None,
                "error": str(exc),
            }

    return {
        "enabled": False,
        "command": None,
        "error": "Start at login is not supported on this OS.",
    }
