# Edifier M60 / M90 Desktop Control

> **AI Disclaimer:** This project was built using AI assistance. It is an unofficial community tool for the **Edifier M60** and **Edifier M90** speakers, is not affiliated with or endorsed by Edifier, and is provided as-is without warranty.

A cross-platform (**Windows & Linux**) desktop application to control your **Edifier M60** and **Edifier M90** speakers over **Bluetooth Low Energy (BLE)**, paired with **USB-C** OS audio integration.

## Features

- **Full Edifier M60 & M90 BLE Control Protocol** (auto-detected via GATT service UUID `4809f601-...` for M60 or `48094503-...` for M90):
  - **Hardware Volume**: `0–16` on M60 / `0–50` on M90 with step meter, mute toggle, fine slider, and automatic live sync when changed physically on the speaker
  - **Input Source Switching**:
    - **M60** (group `0x0F`): Bluetooth, USB-C, and AUX
    - **M90** (group `0x1D`): Bluetooth, USB-C, HDMI (ARC), Optical, and AUX
  - **AVRCP Media Playback**: Play, Pause, Next, Previous
  - **EQ Presets**:
    - **M60**: Music, Monitor, Game, Movie, Customized
    - **M90**: Classic, Monitor, Dynamic, Custom
  - **Custom Parametric / Graphic EQ (`0x43` / `0x44` / `0x47`)**:
    - **M60**: Live SVG curve + **6 band faders** (`62 Hz`, `250 Hz`, `1 kHz`, `4 kHz`, `8 kHz`, `16 kHz`, `-3.0 dB` to `+3.0 dB` in `0.5 dB` steps), optional Frequency & Q editing
    - **M90**: Live SVG curve + **9 band faders** (`62 Hz`, `125 Hz`, `250 Hz`, `500 Hz`, `1 kHz`, `2 kHz`, `4 kHz`, `8 kHz`, `16 kHz`, `-3.0 dB` to `+3.0 dB` in `0.5 dB` steps)
    - **Local Saved Profiles**: Built-in starter profiles + custom saved curves stored per speaker model
  - **M60 Smart Light (`0x84` / `0x85`)**: Backlight timer (`5s`, `10s`, `20s`, `Always On`) and proximity sensitivity (`High`, `General`, `Low`)
  - **M90 Hardware Extras**:
    - **Subwoofer Output (`AA ED 13` / `AA ED 14`)**: Low / Medium / High
    - **Bluetooth Multipoint (`0x7C` / `0x7D`)**: On / Off
    - **Auto Power-Save Mode (`0xB1` / `0xB2`)**: On / Off
    - **Timed Power-Off (`0xD1` / `0xD2` / `0xD3`)**: Off, `15m`, `30m`, `60m`, `90m`
    - **Remote Shutdown (`0xCE`)**: Power off the M90 over BLE
  - **Bluetooth Prompt Tone (`0x86` / `0x87`)**: On / Off
  - **LDAC Codec Preference**: M60 (`0x48` / `0x49`) & M90 (`0x91` / `0x92`) — Off, 44.1/48 kHz, 96 kHz
  - **Device Management**: Read firmware, Classic BT MAC, capabilities (`0xD8`), rename speaker (`0xCA`, max 35 UTF-8 bytes), disconnect BT audio (`0xCD`, M60), and two built-in emulators (**Demo Mode: M60** / **Demo Mode: M90**)
- **USB-C Audio Integration (Windows & Linux)**:
  - **Windows**: Automatically detects active `EDIFIER M60` / `EDIFIER M90` USB WASAPI endpoints (`VID 2D99`), controls Windows volume/mute, provides a **100% Bit-Perfect** lock, and offers opt-in global Volume Key sync (`RegisterHotKey`).
  - **Linux**: Detects Edifier USB hardware (`VID 2d99`) via `/sys/bus/usb/devices` and controls the USB audio sink via `pactl` (PipeWire / PulseAudio).
- **Auto-Update & Repo Move Detection**:
  - **Check for Updates** is **ON by default** inside the **3-dot menu** (`⋮`) and checks GitHub Releases automatically on startup.
  - If an update is available, click **Update Now** to download and install it automatically.
  - If the GitHub repository changes name or cannot be found (`301` / `404`), the app alerts you and recommends looking up **Edifier M60 / M90 Desktop Control** on GitHub so you don't mistake a renamed repo for a broken updater.
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
Native packages install to `/opt/edifier-m60-control` with a `/usr/bin/edifier-m60-control` launcher, desktop entry, and icon. Auto-update uses the same package format you installed.

- **Debian / Ubuntu / Mint / Pop!_OS (`edifier-m60-control_*_amd64.deb`)**:
  ```bash
  sudo apt install ./edifier-m60-control_*_amd64.deb
  ```
- **Fedora / RHEL / Alma / Rocky (`edifier-m60-control-*.x86_64.rpm`)**:
  ```bash
  sudo dnf install ./edifier-m60-control-*.x86_64.rpm
  ```
  **openSUSE**:
  ```bash
  sudo zypper install --allow-unsigned-rpm ./edifier-m60-control-*.x86_64.rpm
  ```
- **Arch / EndeavourOS / Manjaro / CachyOS (`edifier-m60-control-*-x86_64.pkg.tar.zst`)**:
  ```bash
  sudo pacman -U ./edifier-m60-control-*-x86_64.pkg.tar.zst
  ```
- **Portable Archive (`edifier-m60-control-v*-linux-x86_64.tar.gz`)**:
  ```bash
  tar -xzf edifier-m60-control-v*-linux-x86_64.tar.gz
  cd edifier-m60-control-v*-linux-x86_64
  ./install.sh   # optional per-user desktop & ~/.local/bin install
  ```
  *Linux notes*: Requires BlueZ (`bluetoothd`) for BLE, `pulseaudio-utils` or `pipewire-pulse` (`pactl`) for USB-C volume sync, and a Chromium-based browser (`chromium` / `google-chrome` / `microsoft-edge`) for `--app` window mode (falls back to default browser otherwise).

## How Bluetooth & USB-C Work on the Edifier M60 / M90

Over **USB-C** (Edifier USB VID `0x2D99`, e.g. `PID 0xA094` on M60), the speakers expose standard **UAC stereo PCM audio** only—Edifier's firmware does not expose ConneX DSP/EQ/input commands over USB HID. Just like the official EDIFIER ConneX phone app, this desktop app sends hardware commands over **BLE concurrently while audio streams over USB-C** (or Bluetooth / HDMI / Optical / AUX).

## Troubleshooting BLE Connection

1. **Close the EDIFIER ConneX phone app**: Both M60 and M90 accept only **one active BLE connection at a time**.
2. **Speaker not showing up when idle**: On some firmware versions (such as M60 `2.4.1` or M90 `2.5.1`), BLE advertising (`0000f600-...` / `00004503-...`) or GATT service exposure (`4809f601-...` / `48094503-...`) can sleep while idle. Wake the speaker by playing audio or toggling Bluetooth/power, then rescan.
3. **Changing LDAC drops Bluetooth**: Writing LDAC (`0x49` on M60, `0x92` on M90) can drop Classic BT and BLE momentarily; on M60 it may also reset smart-light sensitivity to `High`.

## Building from Source

```powershell
# Run backend tests
.\.venv\Scripts\python.exe -m pytest backend\tests -v

# Build Windows portable EXE (and Inno Setup installer if ISCC.exe is installed)
.\build_release.ps1
```

On Linux:
```bash
bash installer/linux/build_linux.sh   # .deb + portable .tar.gz (Debian/Ubuntu host, needs dpkg-deb)
bash installer/linux/build_rpm.sh     # .rpm (Fedora/openSUSE host, needs rpm-build)
bash installer/linux/build_arch.sh    # .pkg.tar.zst (Arch host, needs base-devel/makepkg)
```
Set `PYTHON=/path/to/venv/bin/python` to build with a virtual environment.

## Feature Requests & Bug Reports

Have an idea for a new feature or ran into an issue?

- **[Request a Feature](https://github.com/Droid567492/EdifierDesktop/issues/new?template=feature_request.yml)**
- **[Report a Bug](https://github.com/Droid567492/EdifierDesktop/issues/new?template=bug_report.yml)**
- **[Browse Existing Issues](https://github.com/Droid567492/EdifierDesktop/issues)**

## Acknowledgements & Thanks

This project builds on community reverse-engineering and prior open-source work for Edifier speakers:

- **[`kralonur/edifier-speakers-ble`](https://github.com/kralonur/edifier-speakers-ble)** — Thank you for reverse-engineering and documenting both the Edifier M60 (`docs/edifier-m60-ble.md`) and Edifier M90 (`docs/edifier-m90-ble.md`) BLE protocols (GATT service/characteristic UUIDs, `AA EC` / `BB EC` / `AA ED` / `CC EC` frame structures, opcodes, 6-band and 9-band EQ layouts, Sub Out, multipoint, power-save/timed-off, smart light, LDAC quirks, and firmware behavior) that power this app's communication layer.
- **[`Spectra456/edifier-m60-controller`](https://github.com/Spectra456/edifier-m60-controller)** — Thank you for pioneering the Windows USB-C + BLE hardware volume workflow (using `RegisterHotKey` to drive the speaker hardware amp while keeping Windows USB digital audio at 100%).


