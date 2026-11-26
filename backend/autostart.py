"""Windows 'Start with Windows' registry integration (HKCU\\...\\Run)."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE_NAME = "EdifierM60Control"


def get_startup_command() -> str:
    """Return the command line registered in Windows Startup."""
    if getattr(sys, "frozen", False):
        exe_path = Path(sys.executable).resolve()
        return f'"{exe_path}" --background'

    py_exe = Path(sys.executable).resolve()
    pythonw = py_exe.with_name("pythonw.exe")
    runner = pythonw if pythonw.exists() else py_exe
    app_script = (Path(__file__).resolve().parent / "app.py").resolve()
    return f'"{runner}" "{app_script}" --background'


def is_autostart_enabled() -> bool:
    if sys.platform != "win32":
        return False
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


def set_autostart(enabled: bool) -> dict[str, Any]:
    if sys.platform != "win32":
        return {
            "enabled": False,
            "command": None,
            "error": "Start with Windows is only supported on Windows.",
        }
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
