"""USB-C UAC audio endpoint detection & volume control for Edifier M60 / M90."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field
import logging
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any

logger = logging.getLogger(__name__)

EDIFIER_USB_VID = "2D99"
EDIFIER_M60_USB_PID = "A094"

PKEY_ENUMERATOR = "{A45C254E-DF1C-4EFD-8020-67D146A850E0} 24"
PKEY_DEV_INSTANCE = "{B3F8FA53-0004-438E-9003-51A46E139BFC} 2"
PKEY_HW_ID = "{80F111C3-B103-42E1-AFB6-DB7A6FA8BE1F} 0"
PKEY_IFACE_PATH = "{233164C8-1B2C-4C7D-BC68-B671687A2567} 1"


@dataclass
class UsbAudioStatus:
    connected: bool = False
    device_name: str | None = None
    device_id: str | None = None
    is_default: bool = False
    volume_percent: int | None = None
    muted: bool | None = None
    usb_hardware_present: bool = False
    usb_vid_pid: str | None = None
    usb_pnp_name: str | None = None
    hid_interfaces: list[dict[str, str]] = field(default_factory=list)
    protocol_note: str = (
        "Edifier M60 / M90 USB-C exposes standard UAC stereo PCM audio (VID 2D99). "
        "EQ, input switching, and speaker settings are controlled over BLE concurrently while USB-C plays audio."
    )
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _matches_m60(name: str) -> bool:
    low = name.lower()
    return (
        ("edifier" in low and ("m60" in low or "m90" in low))
        or "edifier m60" in low
        or "edifier m90" in low
    )


def _matches_edifier_speaker(name: str) -> bool:
    return _matches_m60(name)


def is_m60_usb_audio_device(dev: Any) -> bool:
    """Return True only when a pycaw AudioDevice is an active USB-C Edifier M60 render endpoint."""
    state = getattr(dev, "state", None)
    state_val = getattr(state, "value", state)
    if state_val != 1:
        return False

    dev_id = getattr(dev, "id", None)
    if dev_id is not None and not str(dev_id).startswith("{0.0.0."):
        return False

    friendly = str(getattr(dev, "FriendlyName", "") or "")
    props = getattr(dev, "properties", None)
    if not isinstance(props, dict):
        props = {}

    enumerator = str(props.get(PKEY_ENUMERATOR) or "").strip().upper()
    hw_parts = [
        str(props.get(PKEY_DEV_INSTANCE) or ""),
        str(props.get(PKEY_HW_ID) or ""),
        str(props.get(PKEY_IFACE_PATH) or ""),
    ]
    hw_blob = " ".join(hw_parts).lower()

    if enumerator != "USB":
        return False
    if any(bt in hw_blob for bt in ("bthenum", "bthle", "bluetooth")):
        return False

    if "vid_2d99" in hw_blob and (
        "pid_a094" in hw_blob
        or "m90" in friendly.lower()
        or "m60" in friendly.lower()
        or "edifier" in friendly.lower()
    ):
        return True

    return _matches_m60(friendly)


is_edifier_usb_audio_device = is_m60_usb_audio_device


def filter_m60_usb_pnp_items(
    items: list[dict[str, Any]],
) -> tuple[bool, str | None, list[dict[str, str]]]:
    """Filter Windows PnP query rows to active Edifier M60 / M90 USB devices only."""
    pnp_name: str | None = None
    interfaces: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        iid = str(item.get("InstanceId") or "")
        status = str(item.get("Status") or "")
        iid_upper = iid.upper()
        if not iid_upper.startswith(f"USB\\VID_{EDIFIER_USB_VID}&"):
            continue
        fname = str(item.get("FriendlyName") or "")
        low_fname = fname.lower()
        if (
            f"PID_{EDIFIER_M60_USB_PID}" not in iid_upper
            and "edifier" not in low_fname
            and "m90" not in low_fname
            and "m60" not in low_fname
        ):
            continue
        if status.upper() != "OK":
            continue
        cls = str(item.get("Class") or "")
        if fname and pnp_name is None:
            pnp_name = fname
        interfaces.append(
            {
                "class": cls,
                "name": fname,
                "instance_id": iid,
                "status": status,
            }
        )
    return len(interfaces) > 0, pnp_name, interfaces


filter_edifier_usb_pnp_items = filter_m60_usb_pnp_items


def _probe_usb_pnp_windows() -> tuple[bool, str | None, list[dict[str, str]]]:
    """Query Windows PnP devices for Edifier M60 / M90 VID_2D99 (non-blocking best effort)."""
    try:
        ps_cmd = (
            "Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | "
            "Where-Object { $_.InstanceId -match '^USB\\\\VID_2D99&' -and $_.Status -eq 'OK' } | "
            "Select-Object Status, Class, FriendlyName, InstanceId | ConvertTo-Json -Compress"
        )
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=3,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return False, None, []
        import json

        raw = json.loads(proc.stdout)
        items = raw if isinstance(raw, list) else [raw]
        return filter_m60_usb_pnp_items(items)
    except Exception:
        return False, None, []


def _get_endpoint_and_status_sync(include_pnp: bool = False) -> UsbAudioStatus:
    """Inspect OS audio playback endpoints (Windows WASAPI or Linux PipeWire/Pulse)."""
    if sys.platform.startswith("linux"):
        return _get_linux_usb_status_sync(include_pnp=include_pnp)
    if sys.platform != "win32":
        return UsbAudioStatus()

    status = UsbAudioStatus()
    if include_pnp:
        present, pnp_name, interfaces = _probe_usb_pnp_windows()
        status.usb_hardware_present = present
        status.usb_pnp_name = pnp_name
        status.hid_interfaces = interfaces
        if present:
            status.usb_vid_pid = f"{EDIFIER_USB_VID}:{EDIFIER_M60_USB_PID}"

    com_initialized = False
    try:
        import comtypes
        from ctypes import POINTER, cast
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        comtypes.CoInitialize()
        com_initialized = True

        default_id: str | None = None
        try:
            default_dev = AudioUtilities.GetSpeakers()
            if default_dev is not None:
                default_id = getattr(default_dev, "id", None)
                if default_id is None and hasattr(default_dev, "GetId"):
                    default_id = default_dev.GetId()
        except Exception:
            default_id = None

        all_devices = AudioUtilities.GetAllDevices()
        for dev in all_devices:
            if not is_m60_usb_audio_device(dev):
                continue
            friendly = getattr(dev, "FriendlyName", "") or ""
            dev_id = getattr(dev, "id", None)

            status.connected = True
            status.device_name = friendly
            status.device_id = dev_id
            status.is_default = bool(default_id and dev_id == default_id)

            try:
                endpoint = getattr(dev, "EndpointVolume", None)
                if endpoint is None and hasattr(dev, "_dev"):
                    iface = dev._dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                    endpoint = cast(iface, POINTER(IAudioEndpointVolume))
                if endpoint is not None:
                    scalar = endpoint.GetMasterVolumeLevelScalar()
                    status.volume_percent = int(round(float(scalar) * 100))
                    status.muted = bool(endpoint.GetMute())
            except Exception as exc:
                status.error = f"Could not read endpoint volume: {exc}"
            break

        if status.connected and status.usb_vid_pid is None and status.usb_hardware_present:
            status.usb_vid_pid = f"{EDIFIER_USB_VID}:{EDIFIER_M60_USB_PID}"
    except Exception as exc:
        status.error = f"WASAPI inspection unavailable: {exc}"
    finally:
        if com_initialized:
            try:
                import comtypes

                comtypes.CoUninitialize()
            except Exception:
                pass

    return status


def parse_linux_pactl_sinks(output: str) -> str | None:
    """Return the pactl sink name for an Edifier M60 / M90 USB-C sink (never Bluetooth)."""
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        sink_name = parts[1].strip()
        low = sink_name.lower()
        if "bluez" in low or "bluetooth" in low:
            continue
        if not ("alsa_output.usb-" in low or "usb-" in low):
            continue
        if (
            ("edifier" in low and ("m60" in low or "m90" in low))
            or "2d99" in low
            or "bestechnic" in low
        ):
            return sink_name
    return None


def parse_linux_pactl_volume(
    vol_output: str, mute_output: str
) -> tuple[int | None, bool | None]:
    """Parse `pactl get-sink-volume` and `pactl get-sink-mute` outputs."""
    pct: int | None = None
    m = re.search(r"(\d+)\s*%", vol_output)
    if m:
        pct = max(0, min(100, int(m.group(1))))
    muted: bool | None = None
    ml = mute_output.lower()
    if "yes" in ml:
        muted = True
    elif "no" in ml:
        muted = False
    return pct, muted


def _probe_usb_sysfs_linux() -> tuple[bool, str | None, list[dict[str, str]]]:
    usb_root = Path("/sys/bus/usb/devices")
    if not usb_root.exists():
        return False, None, []
    interfaces: list[dict[str, str]] = []
    pnp_name: str | None = None
    try:
        for dev_dir in usb_root.iterdir():
            vid_file = dev_dir / "idVendor"
            pid_file = dev_dir / "idProduct"
            if not vid_file.exists() or not pid_file.exists():
                continue
            vid = vid_file.read_text(encoding="utf-8", errors="ignore").strip().upper()
            pid = pid_file.read_text(encoding="utf-8", errors="ignore").strip().upper()
            if vid == EDIFIER_USB_VID:
                prod_file = dev_dir / "product"
                prod = (
                    prod_file.read_text(encoding="utf-8", errors="ignore").strip()
                    if prod_file.exists()
                    else "EDIFIER USB"
                )
                low_prod = prod.lower()
                if (
                    pid != EDIFIER_M60_USB_PID
                    and "edifier" not in low_prod
                    and "m60" not in low_prod
                    and "m90" not in low_prod
                ):
                    continue
                if pnp_name is None:
                    pnp_name = prod
                interfaces.append(
                    {
                        "class": "USB",
                        "name": prod,
                        "instance_id": f"USB\\VID_{vid}&PID_{pid}\\{dev_dir.name}",
                        "status": "OK",
                    }
                )
    except OSError:
        return False, None, []
    return len(interfaces) > 0, pnp_name, interfaces


def _get_linux_usb_status_sync(include_pnp: bool = False) -> UsbAudioStatus:
    status = UsbAudioStatus()
    if include_pnp:
        present, pnp_name, ifaces = _probe_usb_sysfs_linux()
        status.usb_hardware_present = present
        status.usb_pnp_name = pnp_name
        status.hid_interfaces = ifaces
        if present:
            status.usb_vid_pid = f"{EDIFIER_USB_VID}:{EDIFIER_M60_USB_PID}"

    if not shutil.which("pactl"):
        return status
    try:
        sinks_proc = subprocess.run(
            ["pactl", "list", "short", "sinks"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if sinks_proc.returncode != 0:
            return status
        sink_name = parse_linux_pactl_sinks(sinks_proc.stdout)
        if not sink_name:
            return status

        status.connected = True
        status.device_name = sink_name
        status.device_id = sink_name
        if status.usb_vid_pid is None and status.usb_hardware_present:
            status.usb_vid_pid = f"{EDIFIER_USB_VID}:{EDIFIER_M60_USB_PID}"

        def_proc = subprocess.run(
            ["pactl", "get-default-sink"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if def_proc.returncode == 0:
            status.is_default = def_proc.stdout.strip() == sink_name

        vol_proc = subprocess.run(
            ["pactl", "get-sink-volume", sink_name],
            capture_output=True,
            text=True,
            timeout=2,
        )
        mute_proc = subprocess.run(
            ["pactl", "get-sink-mute", sink_name],
            capture_output=True,
            text=True,
            timeout=2,
        )
        pct, muted = parse_linux_pactl_volume(vol_proc.stdout, mute_proc.stdout)
        status.volume_percent = pct
        status.muted = muted
    except Exception as exc:
        status.error = f"PipeWire/Pulse inspection failed: {exc}"
    return status


def _set_linux_usb_volume_sync(
    volume_percent: int | None = None, muted: bool | None = None
) -> UsbAudioStatus:
    if shutil.which("pactl"):
        try:
            sinks_proc = subprocess.run(
                ["pactl", "list", "short", "sinks"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            sink_name = parse_linux_pactl_sinks(sinks_proc.stdout)
            if sink_name:
                if volume_percent is not None:
                    clamped = max(0, min(100, int(volume_percent)))
                    subprocess.run(
                        ["pactl", "set-sink-volume", sink_name, f"{clamped}%"],
                        capture_output=True,
                        timeout=2,
                    )
                if muted is not None:
                    subprocess.run(
                        ["pactl", "set-sink-mute", sink_name, "1" if muted else "0"],
                        capture_output=True,
                        timeout=2,
                    )
        except Exception as exc:
            logger.warning("Failed to update Linux M60 USB sink: %s", exc)
    return _get_linux_usb_status_sync(include_pnp=False)


def _set_endpoint_volume_sync(
    volume_percent: int | None = None, muted: bool | None = None
) -> UsbAudioStatus:
    if sys.platform.startswith("linux"):
        return _set_linux_usb_volume_sync(volume_percent, muted)
    if sys.platform != "win32":
        return UsbAudioStatus()

    com_initialized = False
    try:
        import comtypes
        from ctypes import POINTER, cast
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        comtypes.CoInitialize()
        com_initialized = True

        for dev in AudioUtilities.GetAllDevices():
            if not is_m60_usb_audio_device(dev):
                continue

            endpoint = getattr(dev, "EndpointVolume", None)
            if endpoint is None and hasattr(dev, "_dev"):
                iface = dev._dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                endpoint = cast(iface, POINTER(IAudioEndpointVolume))
            if endpoint is None:
                raise RuntimeError("M60 endpoint volume interface unavailable.")

            if volume_percent is not None:
                clamped = max(0, min(100, int(volume_percent)))
                endpoint.SetMasterVolumeLevelScalar(clamped / 100.0, None)
            if muted is not None:
                endpoint.SetMute(1 if muted else 0, None)
            break
    except Exception as exc:
        logger.warning("Failed to update Windows M60 USB endpoint: %s", exc)
    finally:
        if com_initialized:
            try:
                import comtypes

                comtypes.CoUninitialize()
            except Exception:
                pass
    return _get_endpoint_and_status_sync(include_pnp=False)


class UsbAudioManager:
    """Async wrapper around Windows WASAPI & USB-C device checks."""

    def __init__(self) -> None:
        self._last_pnp_check: tuple[bool, str | None, list[dict[str, str]]] = (
            False,
            None,
            [],
        )
        self._pnp_counter = 0

    async def get_status(self, force_pnp: bool = False) -> dict[str, Any]:
        include_pnp = force_pnp or (self._pnp_counter % 4 == 0)
        self._pnp_counter += 1
        status = await asyncio.to_thread(_get_endpoint_and_status_sync, include_pnp)
        if include_pnp:
            self._last_pnp_check = (
                status.usb_hardware_present,
                status.usb_pnp_name,
                status.hid_interfaces,
            )
        else:
            present, pnp_name, interfaces = self._last_pnp_check
            status.usb_hardware_present = present
            status.usb_pnp_name = pnp_name
            status.hid_interfaces = interfaces
            if present:
                status.usb_vid_pid = f"{EDIFIER_USB_VID}:{EDIFIER_M60_USB_PID}"
        return status.to_dict()

    async def set_volume(self, percent: int) -> dict[str, Any]:
        status = await asyncio.to_thread(_set_endpoint_volume_sync, percent, None)
        present, pnp_name, interfaces = self._last_pnp_check
        status.usb_hardware_present = present
        status.usb_pnp_name = pnp_name
        status.hid_interfaces = interfaces
        if present:
            status.usb_vid_pid = f"{EDIFIER_USB_VID}:{EDIFIER_M60_USB_PID}"
        return status.to_dict()

    async def set_muted(self, muted: bool) -> dict[str, Any]:
        status = await asyncio.to_thread(_set_endpoint_volume_sync, None, muted)
        present, pnp_name, interfaces = self._last_pnp_check
        status.usb_hardware_present = present
        status.usb_pnp_name = pnp_name
        status.hid_interfaces = interfaces
        if present:
            status.usb_vid_pid = f"{EDIFIER_USB_VID}:{EDIFIER_M60_USB_PID}"
        return status.to_dict()

    async def lock_bit_perfect(self) -> dict[str, Any]:
        """Set Windows M60 USB endpoint to 100% and unmuted for clean digital output."""
        status = await asyncio.to_thread(_set_endpoint_volume_sync, 100, False)
        present, pnp_name, interfaces = self._last_pnp_check
        status.usb_hardware_present = present
        status.usb_pnp_name = pnp_name
        status.hid_interfaces = interfaces
        if present:
            status.usb_vid_pid = f"{EDIFIER_USB_VID}:{EDIFIER_M60_USB_PID}"
        return status.to_dict()
