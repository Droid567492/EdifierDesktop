# Edifier M60 Desktop Control

> **AI Disclaimer:** This project was built using AI assistance. It is an unofficial community tool for the **Edifier M60** speakers, is not affiliated with or endorsed by Edifier, and is provided as-is without warranty.

A cross-platform (**Windows & Linux**) desktop application to control your **Edifier M60** speakers over **Bluetooth Low Energy (BLE)**, paired with **USB-C** OS audio integration.

## Features

- **Full Edifier M60 BLE Control Protocol**:
  - **Hardware Volume (0–16)** with step meter, mute toggle, fine slider, and automatic live sync when changed physically on the speaker
  - **Input Source Switching**: Bluetooth, USB-C, and AUX (with M60 group `0x0F` and settling refresh)
  - **AVRCP Media Playback**: Play, Pause, Next, Previous
  - **EQ Presets**: Music, Monitor, Game, Movie, Customized
  - **6-Band Custom EQ (`0x43` / `0x44` / `0x47`)**: Live SVG curve + 6 band faders (62 Hz, 250 Hz, 1 kHz, 4 kHz, 8 kHz, 16 kHz, -3.0 dB to +3.0 dB in 0.5 dB steps), optional Frequency & Q editing, plus local saved custom EQ profiles
  - **Smart Light (`0x84` / `0x85`)**: Backlight timer (`5s`, `10s`, `20s`, `Always On`) and proximity sensitivity (`High`, `General`, `Low`)
  - **Bluetooth Prompt Tone (`0x86` / `0x87`)**: On / Off
  - **LDAC Codec Preference (`0x48` / `0x49`)**: Default/Off, 44.1/48 kHz, 96 kHz
  - **Device Management**: Read firmware, Classic BT MAC, capabilities (`0xD8`), rename speaker (`0xCA`, max 35 UTF-8 bytes), disconnect BT audio (`0xCD`)
- **USB-C Audio Integration (Windows & Linux)**:
  - **Windows**: Automatically detects the active `EDIFIER M60` WASAPI endpoint (`VID 2D99 / PID A094`), controls Windows volume/mute, provides a **100% Bit-Perfect** lock, and offers opt-in global Volume Key sync (`RegisterHotKey`).
  - **Linux**: Detects USB hardware (`2d99:a094`) via `/sys/bus/usb/devices` and controls the USB audio sink via `pactl` (PipeWire / PulseAudio).
- **Auto-Update & Repo Move Detection**:
  - **Check for Updates** is **ON by default** inside the **3-dot menu** (`⋮`) and checks GitHub Releases automatically on startup.
  - If an update is available, click **Update Now** to download and install it automatically.
  - If the GitHub repository changes name or cannot be found (`301` / `404`), the app alerts you and recommends looking up **Edifier M60 Desktop Control** on GitHub so you don't mistake a renamed repo for a broken updater.
- **Universal "Don't show again" Alerts**:
  - Every alert banner and confirmation modal includes a **Don't show again** option (and you can restore hidden alerts anytime from the **3-dot menu**).
- **System Tray, Matching Taskbar Icon & Start at Login**:
  - Launches in a Chromium/Edge `--app` window with a matching speaker icon and system tray controls.
  - Includes **Start with Windows** (Registry `HKCU\...\Run`) / **Start at Login** (Linux XDG `~/.config/autostart/`), launching quietly in the system tray (`--background`).

## Installation

Download the package for your OS from the [Releases](https://github.com/Droid567492/EdifierDesktop/releases) page:

### Windows
- **Installer (`EdifierM60Control-v*-win64-setup.exe`)**: Standard Windows installer with Start Menu/Desktop shortcuts, uninstaller, and optional Start with Windows.
- **Portable (`EdifierM60Control-v*-win64-portable.exe`)**: Single portable `.exe` — run directly with no installation required.

### Linux (x86_64)
- **Debian / Ubuntu (`edifier-m60-control_*_amd64.deb`)**:
  ```bash
  sudo apt install ./edifier-m60-control_*_amd64.deb
  ```
- **Portable Archive (`edifier-m60-control-v*-linux-x86_64.tar.gz`)**:
  ```bash
  tar -xzf edifier-m60-control-v*-linux-x86_64.tar.gz
  cd edifier-m60-control-v*-linux-x86_64
  ./install.sh   # optional per-user desktop & ~/.local/bin install
  ```
  *Linux notes*: Requires BlueZ (`bluetoothd`) for BLE, `pulseaudio-utils` or `pipewire-pulse` (`pactl`) for USB-C volume sync, and a Chromium-based browser (`chromium` / `google-chrome` / `microsoft-edge`) for `--app` window mode (falls back to default browser otherwise).

## How Bluetooth & USB-C Work on the Edifier M60

Over **USB-C** (`VID 0x2D99`, `PID 0xA094`), the Edifier M60 exposes standard **UAC1 stereo PCM audio** only—Edifier's firmware does not expose ConneX DSP/EQ/input commands over USB HID. Just like the official EDIFIER ConneX phone app, this desktop app sends hardware commands over **BLE concurrently while audio streams over USB-C** (or Bluetooth / AUX).

## Troubleshooting BLE Connection

1. **Close the EDIFIER ConneX phone app**: The M60 only accepts **one active BLE connection at a time**.
2. **Speaker not showing up when idle**: On some M60 firmware versions (such as `2.4.1`), BLE advertising or GATT service exposure (`4809f601-1a48-11e9-ab14-d663bd873d93`) can sleep while idle. Wake the speaker by playing audio or toggling Bluetooth/power, then rescan.
3. **Changing LDAC drops Bluetooth**: Writing LDAC (`0x49`) can drop both Classic BT and BLE momentarily and reset smart-light sensitivity to `High`.

## Building from Source

```powershell
# Run backend tests
.\.venv\Scripts\python.exe -m pytest backend\tests -v

# Build Windows portable EXE (and Inno Setup installer if ISCC.exe is installed)
.\build_release.ps1
```

On Linux:
```bash
bash installer/linux/build_linux.sh
```

## Feature Requests & Bug Reports

Have an idea for a new feature or ran into an issue?

- **[Request a Feature](https://github.com/Droid567492/EdifierDesktop/issues/new?template=feature_request.yml)**
- **[Report a Bug](https://github.com/Droid567492/EdifierDesktop/issues/new?template=bug_report.yml)**
- **[Browse Existing Issues](https://github.com/Droid567492/EdifierDesktop/issues)**

## Acknowledgements & Thanks

This project builds on community reverse-engineering and prior open-source work for the Edifier M60:

- **[`kralonur/edifier-speakers-ble`](https://github.com/kralonur/edifier-speakers-ble)** — Thank you for reverse-engineering and documenting the Edifier M60 BLE protocol (`docs/edifier-m60-ble.md`: GATT service/characteristic UUIDs, `AA EC` / `BB EC` frame structure, opcodes, 6-band EQ layout, smart light, LDAC quirks, and firmware behavior) that powers this app's communication layer.
- **[`Spectra456/edifier-m60-controller`](https://github.com/Spectra456/edifier-m60-controller)** — Thank you for pioneering the Windows USB-C + BLE hardware volume workflow (using `RegisterHotKey` to drive the M60's 0–16 hardware amp while keeping Windows USB digital audio at 100%).


