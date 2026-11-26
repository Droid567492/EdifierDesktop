"""Unit tests for Windows startup registry helper (mocked winreg)."""

from __future__ import annotations

from contextlib import contextmanager
import sys
from types import SimpleNamespace

from backend import autostart


class _FakeReg:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    HKEY_CURRENT_USER = "HKCU"
    KEY_READ = 1
    KEY_SET_VALUE = 2
    REG_SZ = 1

    @contextmanager
    def OpenKey(self, root, subkey, _reserved=0, _access=0):
        yield (root, subkey)

    @contextmanager
    def CreateKeyEx(self, root, subkey, _reserved=0, _access=0):
        yield (root, subkey)

    def QueryValueEx(self, key, name):
        full = (f"{key[0]}\\{key[1]}", name)
        if full not in self.values:
            raise FileNotFoundError(name)
        return self.values[full], self.REG_SZ

    def SetValueEx(self, key, name, _reserved, _typ, val):
        full = (f"{key[0]}\\{key[1]}", name)
        self.values[full] = val

    def DeleteValue(self, key, name):
        full = (f"{key[0]}\\{key[1]}", name)
        if full not in self.values:
            raise FileNotFoundError(name)
        del self.values[full]


def test_autostart_enable_and_disable_mocked(monkeypatch) -> None:
    fake = _FakeReg()
    monkeypatch.setitem(sys.modules, "winreg", fake)
    monkeypatch.setattr(sys, "platform", "win32")

    assert autostart.is_autostart_enabled() is False

    res_on = autostart.set_autostart(True)
    assert res_on["enabled"] is True
    assert res_on["error"] is None
    assert "--background" in str(res_on["command"])
    assert autostart.is_autostart_enabled() is True

    res_off = autostart.set_autostart(False)
    assert res_off["enabled"] is False
    assert res_off["error"] is None
    assert autostart.is_autostart_enabled() is False


def test_get_startup_command_frozen(monkeypatch) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\Apps\EdifierM60Control.exe")
    cmd = autostart.get_startup_command()
    assert cmd.endswith('EdifierM60Control.exe" --background')
