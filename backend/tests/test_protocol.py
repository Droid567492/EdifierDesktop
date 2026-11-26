"""Unit tests verifying exact Edifier M60 BLE protocol bytes & frame reassembly."""

import pytest

from backend.protocol import (
    HEADER_MAGIC_ED,
    HEADER_SETTER_ALT_ACK,
    HEADER_SPEAKER_REPLY,
    M90_DEFAULT_BAND_FREQS,
    M90_MAX_VOLUME,
    MODEL_M90,
    EqBand,
    EqPreset,
    FrameReassembler,
    InputSource,
    LdacMode,
    M90EqPreset,
    M90InputSource,
    Opcode,
    PlaybackAction,
    ProtocolError,
    SmartLightSensitivity,
    SmartLightTimer,
    SubOutLevel,
    build_frame,
    cmd_cancel_timed_off,
    cmd_disconnect_bt_audio,
    cmd_playback,
    cmd_power_off_device,
    cmd_query_a2dp_state,
    cmd_query_audio_decoding,
    cmd_query_capabilities,
    cmd_query_classic_mac,
    cmd_query_codec_m90,
    cmd_query_custom_eq,
    cmd_query_eq_preset,
    cmd_query_firmware,
    cmd_query_input,
    cmd_query_ldac,
    cmd_query_multipoint,
    cmd_query_name,
    cmd_query_power_save,
    cmd_query_prompt_tone,
    cmd_query_smart_light,
    cmd_query_sub_out,
    cmd_query_timed_off,
    cmd_query_volume,
    cmd_set_codec_m90,
    cmd_set_custom_eq_band,
    cmd_set_custom_eq_meta,
    cmd_set_eq_preset,
    cmd_set_input,
    cmd_set_ldac,
    cmd_set_multipoint,
    cmd_set_name,
    cmd_set_power_save,
    cmd_set_prompt_tone,
    cmd_set_smart_light,
    cmd_set_sub_out,
    cmd_set_timed_off,
    cmd_set_volume,
    decode_a2dp_state,
    decode_audio_decoding,
    decode_capabilities,
    decode_classic_mac,
    decode_codec_m90,
    decode_custom_eq,
    decode_eq_preset,
    decode_firmware,
    decode_input,
    decode_ldac,
    decode_multipoint,
    decode_name,
    decode_power_save,
    decode_prompt_tone,
    decode_smart_light,
    decode_sub_out,
    decode_timed_off,
    decode_volume,
    parse_frame,
)


def hx(s: str) -> bytes:
    return bytes.fromhex(s)


def test_exact_query_vectors() -> None:
    assert cmd_query_capabilities() == hx("AA EC D8 00 00 6E")
    assert cmd_query_name() == hx("AA EC C9 00 00 5F")
    assert cmd_query_firmware() == hx("AA EC C6 00 00 5C")
    assert cmd_query_classic_mac() == hx("AA EC C8 00 00 5E")
    assert cmd_query_input() == hx("AA EC 61 00 00 F7")
    assert cmd_query_volume() == hx("AA EC 66 00 00 FC")
    assert cmd_query_eq_preset() == hx("AA EC D5 00 00 6B")
    assert cmd_query_custom_eq() == hx("AA EC 43 00 00 D9")
    assert cmd_query_ldac() == hx("AA EC 48 00 00 DE")
    assert cmd_query_prompt_tone() == hx("AA EC 86 00 00 1C")
    assert cmd_query_smart_light() == hx("AA EC 84 00 00 1A")
    assert cmd_query_a2dp_state() == hx("AA EC C3 00 00 59")
    assert cmd_query_audio_decoding() == hx("AA EC 68 00 00 FE")
    assert cmd_disconnect_bt_audio() == hx("AA EC CD 00 00 63")


def test_exact_setter_vectors() -> None:
    # Input sources (M60 uses group 0x0F)
    assert cmd_set_input(InputSource.BLUETOOTH) == hx("AA EC 62 00 02 0F 01 0A")
    assert cmd_set_input(InputSource.USB) == hx("AA EC 62 00 02 0F 02 0B")
    assert cmd_set_input(InputSource.AUX) == hx("AA EC 62 00 02 0F 03 0C")

    # Volume (0..16)
    assert cmd_set_volume(0) == hx("AA EC 67 00 01 00 FE")
    assert cmd_set_volume(16) == hx("AA EC 67 00 01 10 0E")
    with pytest.raises(ProtocolError):
        cmd_set_volume(17)

    # Playback AVRCP
    assert cmd_playback(PlaybackAction.PLAY) == hx("AA EC C2 00 01 00 59")
    assert cmd_playback(PlaybackAction.PAUSE) == hx("AA EC C2 00 01 01 5A")
    assert cmd_playback(PlaybackAction.NEXT) == hx("AA EC C2 00 01 04 5D")
    assert cmd_playback(PlaybackAction.PREVIOUS) == hx("AA EC C2 00 01 05 5E")

    # EQ Presets
    assert cmd_set_eq_preset(EqPreset.MUSIC) == hx("AA EC C4 00 01 00 5B")
    assert cmd_set_eq_preset(EqPreset.MONITOR) == hx("AA EC C4 00 01 01 5C")
    assert cmd_set_eq_preset(EqPreset.GAME) == hx("AA EC C4 00 01 02 5D")
    assert cmd_set_eq_preset(EqPreset.MOVIE) == hx("AA EC C4 00 01 03 5E")
    assert cmd_set_eq_preset(EqPreset.CUSTOMIZED) == hx("AA EC C4 00 01 04 5F")

    # Custom EQ band 0 -> 62 Hz, +0.5 dB (code 0x07), Q=0x07
    band0 = EqBand.from_db(index=0, freq=62, gain_db=0.5, q_raw=0x07)
    assert cmd_set_custom_eq_band(band0) == hx("AA EC 44 00 06 00 00 00 3E 07 07 2C")
    band0_zero = EqBand.from_db(index=0, freq=62, gain_db=0.0, q_raw=0x07)
    assert cmd_set_custom_eq_band(band0_zero) == hx("AA EC 44 00 06 00 00 00 3E 06 07 2B")

    # LDAC
    assert cmd_set_ldac(LdacMode.DISABLED) == hx("AA EC 49 00 01 00 E0")
    assert cmd_set_ldac(LdacMode.KHZ_48) == hx("AA EC 49 00 01 01 E1")
    assert cmd_set_ldac(LdacMode.KHZ_96) == hx("AA EC 49 00 01 02 E2")

    # Prompt tone
    assert cmd_set_prompt_tone(False) == hx("AA EC 87 00 03 02 01 00 23")
    assert cmd_set_prompt_tone(True) == hx("AA EC 87 00 03 02 01 01 24")

    # Smart light
    assert cmd_set_smart_light(
        SmartLightTimer.SEC_10, SmartLightSensitivity.GENERAL
    ) == hx("AA EC 85 00 03 03 01 01 23")


def test_rename_validation_and_alt_ack() -> None:
    with pytest.raises(ProtocolError):
        cmd_set_name("")
    with pytest.raises(ProtocolError):
        cmd_set_name("A" * 36)
    # Multi-byte UTF-8 boundary check (36 bytes must fail)
    with pytest.raises(ProtocolError):
        cmd_set_name("é" * 18)

    ack = parse_frame(hx("CC EC CA 00 01 01 84"))
    assert ack.direction == HEADER_SETTER_ALT_ACK
    assert ack.opcode == Opcode.SET_NAME
    assert ack.payload == b"\x01"


def test_reply_decoders() -> None:
    name_frame = parse_frame(hx("BB EC C9 00 0B 45 44 49 46 49 45 52 20 4D 36 30 46"))
    assert decode_name(name_frame.payload) == "EDIFIER M60"

    fw_frame = parse_frame(hx("BB EC C6 00 03 02 04 01 77"))
    assert decode_firmware(fw_frame.payload) == "2.4.1"

    mac_frame = parse_frame(build_frame(Opcode.QUERY_CLASSIC_MAC, hx("11 22 33 44 55 66"), HEADER_SPEAKER_REPLY))
    assert decode_classic_mac(mac_frame.payload) == "11:22:33:44:55:66"

    caps_frame = parse_frame(
        build_frame(
            Opcode.QUERY_CAPABILITIES,
            hx("00 00 01 04 01 01 01 00 00 00 01 01 0A 13 01 00 00 20 04 03 04 30"),
            HEADER_SPEAKER_REPLY,
        )
    )
    caps = decode_capabilities(caps_frame.payload)
    assert caps["eq_profile"] == 19
    assert caps["ldac_flag"] == 4

    assert decode_input(parse_frame(hx("BB EC 61 00 02 0F 01 1A")).payload) == InputSource.BLUETOOTH
    assert decode_input(parse_frame(hx("BB EC 61 00 02 0F 02 1B")).payload) == InputSource.USB
    assert decode_input(parse_frame(hx("BB EC 61 00 02 0F 03 1C")).payload) == InputSource.AUX

    assert decode_volume(parse_frame(hx("BB EC 66 00 02 10 00 1F")).payload) == (16, 0)
    assert decode_eq_preset(parse_frame(hx("BB EC D5 00 01 04 81")).payload) == EqPreset.CUSTOMIZED
    assert decode_ldac(parse_frame(hx("BB EC 48 00 01 02 F2")).payload) == LdacMode.KHZ_96
    assert decode_prompt_tone(parse_frame(hx("BB EC 86 00 02 02 00 31")).payload) is False
    assert decode_prompt_tone(parse_frame(hx("BB EC 86 00 02 02 01 32")).payload) is True

    timer, sens = decode_smart_light(parse_frame(hx("BB EC 84 00 03 03 01 01 33")).payload)
    assert timer == SmartLightTimer.SEC_10
    assert sens == SmartLightSensitivity.GENERAL

    assert decode_a2dp_state(parse_frame(hx("BB EC C3 00 01 03 6E")).payload) == (0x03, "closed")
    assert decode_audio_decoding(parse_frame(hx("BB EC 68 00 01 00 10")).payload)[0] == 0x00


def test_custom_eq_decode_and_reassembler_fragmentation() -> None:
    bands = [
        EqBand.from_db(0, 62, -3.0),
        EqBand.from_db(1, 250, -1.5),
        EqBand.from_db(2, 1000, 0.0),
        EqBand.from_db(3, 4000, 1.5),
        EqBand.from_db(4, 8000, 2.5),
        EqBand.from_db(5, 16000, 3.0),
    ]
    payload = bytearray([0x03, 0x06])
    for b in bands:
        payload.extend(b.to_bytes())
    payload.extend((1700000000).to_bytes(4, "little"))
    payload.extend(b"Studio")

    full_frame = build_frame(Opcode.QUERY_CUSTOM_EQ, bytes(payload), HEADER_SPEAKER_REPLY)
    second_frame = hx("BB EC 66 00 02 10 08 27")

    # Prepend noise, split across 20-byte BLE MTU chunks, and concatenate another frame
    stream = b"\xFF\x00\xBB\x99" + full_frame + second_frame
    reassembler = FrameReassembler()
    collected = []
    for i in range(0, len(stream), 20):
        collected.extend(reassembler.feed(stream[i : i + 20]))

    assert len(collected) == 2
    assert collected[0].opcode == Opcode.QUERY_CUSTOM_EQ
    eq_state = decode_custom_eq(collected[0].payload)
    assert len(eq_state.bands) == 6
    assert [b.gain_db for b in eq_state.bands] == [-3.0, -1.5, 0.0, 1.5, 2.5, 3.0]
    assert eq_state.timestamp == 1700000000
    assert eq_state.name == "Studio"

    assert collected[1].opcode == Opcode.QUERY_VOLUME
    assert decode_volume(collected[1].payload) == (16, 8)

    meta = cmd_set_custom_eq_meta("Test", timestamp=1700000000)
    assert parse_frame(meta).opcode == Opcode.SET_CUSTOM_EQ_META


def test_m90_exact_vectors_and_ed_magic() -> None:
    # M90 Inputs (group 0x1D)
    assert cmd_set_input(M90InputSource.BLUETOOTH, MODEL_M90) == hx("AA EC 62 00 02 1D 01 18")
    assert cmd_set_input(M90InputSource.USB, MODEL_M90) == hx("AA EC 62 00 02 1D 02 19")
    assert cmd_set_input(M90InputSource.HDMI, MODEL_M90) == hx("AA EC 62 00 02 1D 03 1A")
    assert cmd_set_input(M90InputSource.OPTICAL, MODEL_M90) == hx("AA EC 62 00 02 1D 04 1B")
    assert cmd_set_input(M90InputSource.AUX, MODEL_M90) == hx("AA EC 62 00 02 1D 05 1C")

    assert decode_input(parse_frame(hx("BB EC 61 00 02 1D 01 28")).payload, MODEL_M90) == M90InputSource.BLUETOOTH
    assert decode_input(parse_frame(hx("BB EC 61 00 02 1D 03 2A")).payload, MODEL_M90) == M90InputSource.HDMI
    assert decode_input(parse_frame(hx("BB EC 61 00 02 1D 04 2B")).payload, MODEL_M90) == M90InputSource.OPTICAL

    # M90 Volume (0..50 / 0x32)
    assert cmd_set_volume(8, max_volume=M90_MAX_VOLUME) == hx("AA EC 67 00 01 08 06")
    with pytest.raises(ProtocolError):
        cmd_set_volume(51, max_volume=M90_MAX_VOLUME)
    assert decode_volume(parse_frame(hx("BB EC 66 00 02 32 08 49")).payload) == (50, 8)

    # M90 EQ Presets
    assert cmd_set_eq_preset(M90EqPreset.CLASSIC) == hx("AA EC C4 00 01 00 5B")
    assert decode_eq_preset(parse_frame(hx("BB EC D5 00 01 00 7D")).payload, MODEL_M90) == M90EqPreset.CLASSIC
    assert decode_eq_preset(parse_frame(hx("BB EC D5 00 01 02 7F")).payload, MODEL_M90) == M90EqPreset.DYNAMIC

    # M90 4-byte Custom EQ band 0
    band0_up = EqBand.from_db(index=0, freq=62, gain_db=0.5)
    assert cmd_set_custom_eq_band(band0_up, MODEL_M90) == hx("AA EC 44 00 04 00 00 3E 07 23")
    band0_flat = EqBand.from_db(index=0, freq=62, gain_db=0.0)
    assert cmd_set_custom_eq_band(band0_flat, MODEL_M90) == hx("AA EC 44 00 04 00 00 3E 06 22")

    # Decode M90 9-band 0x10 09 payload
    m90_bands = [
        EqBand.from_db(i, freq, (i - 4) * 0.5)
        for i, freq in enumerate(M90_DEFAULT_BAND_FREQS)
    ]
    m90_payload = bytearray([0x10, 0x09])
    for b in m90_bands:
        m90_payload.extend(b.to_m90_bytes())
    eq_m90 = decode_custom_eq(bytes(m90_payload))
    assert eq_m90.format_byte == 0x10
    assert len(eq_m90.bands) == 9
    assert eq_m90.bands[0].freq == 62 and eq_m90.bands[0].gain_db == -2.0
    assert eq_m90.bands[8].freq == 16000 and eq_m90.bands[8].gain_db == 2.0

    # M90 Codec / LDAC (0x91 / 0x92)
    assert cmd_query_codec_m90() == hx("AA EC 91 00 00 27")
    assert cmd_set_codec_m90(LdacMode.KHZ_48) == hx("AA EC 92 00 03 0E 01 FF 39")
    assert decode_codec_m90(parse_frame(hx("BB EC 91 00 02 0E 01 49")).payload) == LdacMode.KHZ_48

    # M90 Sub Out (0xED magic)
    assert cmd_query_sub_out() == hx("AA ED 13 00 00 AA")
    assert cmd_set_sub_out(SubOutLevel.LOW) == hx("AA ED 14 00 02 00 00 AD")
    assert cmd_set_sub_out(SubOutLevel.MEDIUM) == hx("AA ED 14 00 02 00 01 AE")
    assert cmd_set_sub_out(SubOutLevel.HIGH) == hx("AA ED 14 00 02 00 02 AF")
    sub_frame = parse_frame(hx("BB ED 13 00 02 00 02 BF"))
    assert sub_frame.magic == HEADER_MAGIC_ED
    assert decode_sub_out(sub_frame.payload) == SubOutLevel.HIGH

    # M90 Multipoint, Power Save, Timed Power-Off, Shutdown
    assert cmd_query_multipoint() == hx("AA EC 7C 00 00 12")
    assert cmd_set_multipoint(True) == hx("AA EC 7D 00 02 00 01 16")
    assert decode_multipoint(parse_frame(hx("BB EC 7C 00 02 00 00 25")).payload) is False

    assert cmd_query_power_save() == hx("AA EC B1 00 00 47")
    assert cmd_set_power_save(False) == hx("AA EC B2 00 01 00 49")
    assert decode_power_save(parse_frame(hx("BB EC B1 00 01 01 5A")).payload) is True

    assert cmd_query_timed_off() == hx("AA EC D3 00 00 69")
    assert cmd_set_timed_off(15) == hx("AA EC D1 00 02 00 0F 78")
    assert cmd_cancel_timed_off() == hx("AA EC D2 00 00 68")
    assert decode_timed_off(parse_frame(hx("BB EC D3 00 02 00 00 7C")).payload) == 0
    assert cmd_power_off_device() == hx("AA EC CE 00 00 64")

    # FrameReassembler must accept CC EC alt-ACKs and BB ED Sub Out frames
    reassembler = FrameReassembler()
    frames = reassembler.feed(hx("CC EC D1 00 01 01 8B") + hx("BB ED 13 00 02 00 01 BE"))
    assert len(frames) == 2
    assert frames[0].direction == HEADER_SETTER_ALT_ACK
    assert frames[1].magic == HEADER_MAGIC_ED
    assert decode_sub_out(frames[1].payload) == SubOutLevel.MEDIUM
