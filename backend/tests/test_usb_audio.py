"""Unit tests for strict Edifier M60 USB-C endpoint and PnP filtering."""

from types import SimpleNamespace

from backend.usb_audio import (
    PKEY_DEV_INSTANCE,
    PKEY_ENUMERATOR,
    PKEY_HW_ID,
    PKEY_IFACE_PATH,
    filter_m60_usb_pnp_items,
    is_m60_usb_audio_device,
    parse_linux_pactl_sinks,
    parse_linux_pactl_volume,
)


def _fake_dev(
    *,
    name: str,
    dev_id: str = "{0.0.0.00000000}.{3dd9ad2e-2844-42d8-ad57-c61c29c1034e}",
    state: int = 1,
    enumerator: str = "USB",
    instance: str = "",
    hw_id: str = "",
    iface_path: str = "",
):
    return SimpleNamespace(
        FriendlyName=name,
        id=dev_id,
        state=SimpleNamespace(value=state),
        properties={
            PKEY_ENUMERATOR: enumerator,
            PKEY_DEV_INSTANCE: instance,
            PKEY_HW_ID: hw_id,
            PKEY_IFACE_PATH: iface_path,
        },
    )


def test_rejects_bluetooth_m60_endpoint() -> None:
    bt_dev = _fake_dev(
        name="Speakers (2- EDIFIER M60)",
        state=1,
        enumerator="BTHENUM",
        instance=r"{1}.BTHENUM\{0000110B-0000-1000-8000-00805F9B34FB}_LOCALMFG&005D\9&EF4FDBF&0",
    )
    assert is_m60_usb_audio_device(bt_dev) is False


def test_rejects_other_usb_c_dock_audio() -> None:
    dock_dev = _fake_dev(
        name="Speakers (USB-C Dock Audio)",
        state=1,
        enumerator="USB",
        instance=r"{1}.USB\VID_17E9&PID_6006&MI_00\7&1234&0&0000",
        hw_id=r"USB\VID_17E9&PID_6006&REV_0100&MI_00",
        iface_path=r"\\?\usb#vid_17e9&pid_6006&mi_00#7&1234",
    )
    assert is_m60_usb_audio_device(dock_dev) is False


def test_rejects_unplugged_or_capture_m60() -> None:
    unplugged = _fake_dev(
        name="Speakers (EDIFIER M60)",
        state=4,  # NotPresent
        enumerator="USB",
        instance=r"{1}.USB\VID_2D99&PID_A094&MI_00\7&13437E1E&0&0000",
    )
    assert is_m60_usb_audio_device(unplugged) is False

    capture = _fake_dev(
        name="Microphone (EDIFIER M60)",
        dev_id="{0.0.1.00000000}.{11111111-1111-1111-1111-111111111111}",
        state=1,
        enumerator="USB",
        instance=r"{1}.USB\VID_2D99&PID_A094&MI_00\7&13437E1E&0&0000",
    )
    assert is_m60_usb_audio_device(capture) is False


def test_accepts_active_real_m60_usb_endpoint() -> None:
    real_usb = _fake_dev(
        name="Speakers (EDIFIER M60)",
        state=1,
        enumerator="USB",
        instance=r"{1}.USB\VID_2D99&PID_A094&MI_00\7&13437E1E&0&0000",
        hw_id=r"USB\VID_2D99&PID_A094&REV_0100&MI_00",
        iface_path=r"{2}.\\?\usb#vid_2d99&pid_a094&mi_00#7&13437e1e&0&0000#{6994ad04}",
    )
    assert is_m60_usb_audio_device(real_usb) is True


def test_pnp_filter_rejects_bt_and_other_docks() -> None:
    rows = [
        {
            "Status": "OK",
            "Class": "Bluetooth",
            "FriendlyName": "EDIFIER M60",
            "InstanceId": r"BTHENUM\DEV_6C162961E663\8&1234",
        },
        {
            "Status": "OK",
            "Class": "AudioEndpoint",
            "FriendlyName": "Speakers (EDIFIER M60)",
            "InstanceId": r"SWD\MMDEVAPI\{0.0.0.00000000}.{3DD9AD2E}",
        },
        {
            "Status": "OK",
            "Class": "USB",
            "FriendlyName": "USB-C Dock Audio",
            "InstanceId": r"USB\VID_17E9&PID_6006\1234",
        },
        {
            "Status": "Error",
            "Class": "MEDIA",
            "FriendlyName": "EDIFIER M60",
            "InstanceId": r"USB\VID_2D99&PID_A094&MI_00\7&13437E1E&0&0000",
        },
    ]
    present, name, ifaces = filter_m60_usb_pnp_items(rows)
    assert present is False
    assert name is None
    assert ifaces == []

    rows.append(
        {
            "Status": "OK",
            "Class": "MEDIA",
            "FriendlyName": "EDIFIER M60",
            "InstanceId": r"USB\VID_2D99&PID_A094&MI_00\7&13437E1E&0&0000",
        }
    )
    present, name, ifaces = filter_m60_usb_pnp_items(rows)
    assert present is True
    assert name == "EDIFIER M60"
    assert len(ifaces) == 1


def test_linux_pactl_sink_and_volume_parsers() -> None:
    sinks_out = (
        "42\talsa_output.pci-0000_00_1f.3.analog-stereo\tPipeWire\ts32le 2ch 48000Hz\tSUSPENDED\n"
        "58\tbluez_output.6C_16_29_61_E6_63.1\tPipeWire\ts16le 2ch 48000Hz\tRUNNING\n"
        "61\talsa_output.usb-bestechnic_EDIFIER_M60-00.analog-stereo\tPipeWire\ts24le 2ch 96000Hz\tRUNNING\n"
    )
    assert (
        parse_linux_pactl_sinks(sinks_out)
        == "alsa_output.usb-bestechnic_EDIFIER_M60-00.analog-stereo"
    )

    # Without USB sink present, Bluetooth sink must NOT match
    bt_only = "58\tbluez_output.6C_16_29_61_E6_63.1\tPipeWire\ts16le 2ch 48000Hz\tRUNNING\n"
    assert parse_linux_pactl_sinks(bt_only) is None

    vol_out = "Volume: front-left: 49152 /  75% / -7.50 dB,   front-right: 49152 /  75% / -7.50 dB"
    assert parse_linux_pactl_volume(vol_out, "Mute: no") == (75, False)
    assert parse_linux_pactl_volume(vol_out, "Mute: yes") == (75, True)


def test_accepts_m90_usb_and_rejects_m90_bluetooth() -> None:
    m90_usb = _fake_dev(
        name="Speakers (EDIFIER M90)",
        state=1,
        enumerator="USB",
        instance=r"{1}.USB\VID_2D99&PID_A095&MI_00\7&12345&0&0000",
        hw_id=r"USB\VID_2D99&PID_A095&REV_0100&MI_00",
    )
    assert is_m60_usb_audio_device(m90_usb) is True

    m90_bt = _fake_dev(
        name="Speakers (EDIFIER M90)",
        state=1,
        enumerator="BTHENUM",
        instance=r"{1}.BTHENUM\{0000110B-0000-1000-8000-00805F9B34FB}\9&1234",
    )
    assert is_m60_usb_audio_device(m90_bt) is False

    linux_m90 = "72\talsa_output.usb-EDIFIER_M90-00.analog-stereo\tPipeWire\ts24le 2ch 96000Hz\tRUNNING\n"
    assert parse_linux_pactl_sinks(linux_m90) == "alsa_output.usb-EDIFIER_M90-00.analog-stereo"
