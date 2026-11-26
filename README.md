# Edifier M60 Desktop Control

A Windows desktop application to control your **Edifier M60** speakers from PC over **Bluetooth Low Energy (BLE)**, paired with **USB-C** Windows audio integration.

## Features

- **Full Edifier M60 BLE Control Protocol**:
  - **Hardware Volume (0–16)** with step meter, mute toggle, and fine slider
  - **Input Source Switching**: Bluetooth, USB-C, and AUX (with M60 group `0x0F` and settling refresh)
  - **AVRCP Media Playback**: Play, Pause, Next, Previous
  - **EQ Presets**: Music, Monitor, Game, Movie, Customized
  - **6-Band Custom EQ (`0x43` / `0x44` / `0x47`)**: Live SVG curve + 6 band faders (62 Hz, 250 Hz, 1 kHz, 4 kHz, 8 kHz, 16 kHz, -3.0 dB to +3.0 dB in 0.5 dB steps), optional Frequency & Q editing, plus local saved custom EQ profiles
  - **Smart Light (`0x84` / `0x85`)**: Backlight timer (`5s`, `10s`, `20s`, `Always On`) and proximity sensitivity (`High`, `General`, `Low`)
  - **Bluetooth Prompt Tone (`0x86` / `0x87`)**: On / Off
  - **LDAC Codec Preference (`0x48` / `0x49`)**: Default/Off, 44.1/48 kHz, 96 kHz (with safety confirmation)
  - **Device Management**: Read firmware, Classic BT MAC, capabilities (`0xD8`), rename speaker (`0xCA`, max 35 UTF-8 bytes), disconnect BT audio (`0xCD`)
  - **Diagnostics & Raw Frame Inspector**: Live `TX`/`RX` hex frame stream and raw hex sender
- **USB-C Audio Integration**:
  - Automatically detects the `EDIFIER M60` Windows WASAPI playback endpoint and USB hardware (`VID 2D99 / PID A094`)
  - Controls Windows USB volume & mute, plus one-click **100% Bit-Perfect** lock
  - Opt-in **Windows Volume Key Sync** (`RegisterHotKey` for Volume Up/Down/Mute) that drives the M60's 0–16 hardware amp directly while optionally locking Windows USB digital volume at 100%
- **System Tray + Native App Window + Start with Windows**: Launches in an Edge/Chrome `--app` window with a matching speaker taskbar/tray icon, quick system-tray controls, and an optional **Start with Windows** toggle (starts quietly in the system tray at login)
- **3-Dot Overflow Menu**: Keeps **Demo Mode** and **Diagnostics** (live BLE frame log & raw hex sender) neatly tucked out of the way when not needed

## How Bluetooth & USB-C Work on the Edifier M60

Over **USB-C** (`VID 0x2D99`, `PID 0xA094`), the Edifier M60 exposes standard **UAC1 stereo PCM audio** only—Edifier's firmware does not expose ConneX DSP/EQ/input commands over USB HID. Just like the official EDIFIER ConneX phone app, this desktop app sends hardware commands over **BLE concurrently while audio streams over USB-C** (or Bluetooth / AUX).

## Quick Launch & Portable EXE

- **Portable Executable**: Download `EdifierM60Control.exe` from the GitHub Releases page and run it directly — no Python or Node installation required.
- **From Source**: Double-click **`EdifierM60.vbs`** (no console window), run **`launch.bat`**, or run `.\.venv\Scripts\python.exe -m backend.app`.
- **Start with Windows**: Toggle **Start with Windows** in the app's bottom Settings card or from the system tray right-click menu. It launches quietly in the system tray (`--background`).

## Building the Portable EXE

```powershell
.\build_release.ps1
```

Outputs `dist\EdifierM60Control.exe`.

## Troubleshooting BLE Connection

1. **Close the EDIFIER ConneX phone app**: The M60 only accepts **one active BLE connection at a time**.
2. **Speaker not showing up when idle**: On some M60 firmware versions (such as `2.4.1`), BLE advertising or GATT service exposure (`4809f601-1a48-11e9-ab14-d663bd873d93`) can sleep while idle. Wake the speaker by playing audio or toggling Bluetooth/power, then rescan.
3. **Changing LDAC drops Bluetooth**: Writing LDAC (`0x49`) can drop both Classic BT and BLE momentarily and reset smart-light sensitivity to `High`. Reconnect from Windows Bluetooth / the app's Connect modal afterward.

## Development & Tests

```powershell
# Run backend protocol & API tests
.\.venv\Scripts\python.exe -m pytest backend/tests -v

# Build production frontend bundle
cd frontend
npm run build
```
