"""In-memory Edifier M60 / M90 BLE device simulator for Demo Mode and automated testing."""

from __future__ import annotations

import time

from .protocol import (
    HEADER_MAGIC_ED,
    HEADER_SETTER_ALT_ACK,
    HEADER_SPEAKER_REPLY,
    M60_INPUT_GROUP,
    M90_INPUT_GROUP,
    M90_MAX_VOLUME,
    MAX_DEVICE_NAME_BYTES,
    MAX_VOLUME,
    MODEL_M60,
    MODEL_M90,
    CustomEqState,
    EqBand,
    EqPreset,
    InputSource,
    LdacMode,
    M90EqPreset,
    M90InputSource,
    Opcode,
    SmartLightSensitivity,
    SmartLightTimer,
    SubOutLevel,
    build_frame,
    db_to_gain_code,
    default_custom_eq_bands,
    normalize_model,
    parse_frame,
)


class SimulatedM60Device:
    """Protocol-accurate Edifier M60 / M90 emulator for Demo Mode and tests."""

    DEFAULT_CAPABILITIES = bytes.fromhex(
        "00 00 01 04 01 01 01 00 00 00 01 01 0A 13 01 00 00 20 04 03 04 30"
    )
    M90_CAPABILITIES = bytes.fromhex(
        "00 00 01 04 01 01 00 00 00 02 01 01 0A 48 00 00 00 20 00 03 84 20 41 91 00 00 20 00 10"
    )

    def __init__(self, model: str = MODEL_M60) -> None:
        self.model = normalize_model(model)
        if self.model == MODEL_M90:
            self.name = "EDIFIER M90"
            self.firmware = bytes([2, 5, 1])
            self.classic_mac = bytes([0xA4, 0x77, 0x58, 0x90, 0x56, 0x78])
            self.input_group = M90_INPUT_GROUP
            self.max_volume = M90_MAX_VOLUME
            self.input_source: InputSource | M90InputSource = M90InputSource.USB
            self.volume = 18
            self.eq_preset: EqPreset | M90EqPreset = M90EqPreset.MONITOR
            self.custom_eq = CustomEqState(
                format_byte=0x10,
                bands=[
                    EqBand(0, 62, db_to_gain_code(0.5), 0x07),
                    EqBand(1, 125, db_to_gain_code(0.5), 0x07),
                    EqBand(2, 250, db_to_gain_code(0.0), 0x07),
                    EqBand(3, 500, db_to_gain_code(0.0), 0x07),
                    EqBand(4, 1000, db_to_gain_code(0.0), 0x07),
                    EqBand(5, 2000, db_to_gain_code(0.5), 0x07),
                    EqBand(6, 4000, db_to_gain_code(1.0), 0x07),
                    EqBand(7, 8000, db_to_gain_code(0.5), 0x07),
                    EqBand(8, 16000, db_to_gain_code(0.0), 0x07),
                ],
                timestamp=int(time.time()),
                name="M90 Studio",
            )
            self.ldac_mode = LdacMode.KHZ_48
            self.prompt_tone = True
            self.light_timer = SmartLightTimer.SEC_10
            self.light_sensitivity = SmartLightSensitivity.GENERAL
            self.sub_out_level = SubOutLevel.MEDIUM
            self.multipoint = False
            self.power_save = True
            self.timed_off_minutes = 0
            self.powered_off = False
            self.a2dp_state = 0x03
            self.audio_decoding = 0x05
        else:
            self.name = "EDIFIER M60"
            self.firmware = bytes([2, 4, 1])
            self.classic_mac = bytes([0xA4, 0x77, 0x58, 0x60, 0x12, 0x34])
            self.input_group = M60_INPUT_GROUP
            self.max_volume = MAX_VOLUME
            self.input_source = InputSource.USB
            self.volume = 8
            self.eq_preset = EqPreset.MONITOR
            self.custom_eq = CustomEqState(
                format_byte=0x03,
                bands=[
                    EqBand(0, 62, db_to_gain_code(0.5), 0x07),
                    EqBand(1, 250, db_to_gain_code(0.0), 0x07),
                    EqBand(2, 1000, db_to_gain_code(0.0), 0x07),
                    EqBand(3, 4000, db_to_gain_code(1.0), 0x07),
                    EqBand(4, 8000, db_to_gain_code(0.5), 0x07),
                    EqBand(5, 16000, db_to_gain_code(0.0), 0x07),
                ],
                timestamp=int(time.time()),
                name="Studio Desk",
            )
            self.ldac_mode = LdacMode.KHZ_96
            self.prompt_tone = True
            self.light_timer = SmartLightTimer.SEC_10
            self.light_sensitivity = SmartLightSensitivity.GENERAL
            self.sub_out_level = SubOutLevel.MEDIUM
            self.multipoint = False
            self.power_save = False
            self.timed_off_minutes = 0
            self.powered_off = False
            self.a2dp_state = 0x03  # closed when on USB
            self.audio_decoding = 0x05  # Wired Hi-Res on USB

    def handle_request(self, raw_request: bytes) -> list[bytes]:
        """Process one AA EC / AA ED request frame and return 0 or more reply frames."""
        req = parse_frame(raw_request)
        op = req.opcode
        p = req.payload

        if req.magic == HEADER_MAGIC_ED:
            if op == Opcode.QUERY_SUB_OUT:
                return [
                    build_frame(
                        op,
                        bytes([0x00, int(self.sub_out_level)]),
                        HEADER_SPEAKER_REPLY,
                        magic=HEADER_MAGIC_ED,
                    )
                ]
            if op == Opcode.SET_SUB_OUT:
                if len(p) >= 2:
                    self.sub_out_level = SubOutLevel(p[1])
                return [
                    build_frame(
                        op,
                        bytes([0x00, int(self.sub_out_level)]),
                        HEADER_SPEAKER_REPLY,
                        magic=HEADER_MAGIC_ED,
                    )
                ]
            return []

        if op == Opcode.QUERY_CAPABILITIES:
            caps = (
                self.M90_CAPABILITIES
                if self.model == MODEL_M90
                else self.DEFAULT_CAPABILITIES
            )
            return [build_frame(op, caps, HEADER_SPEAKER_REPLY)]

        if op == Opcode.QUERY_NAME:
            return [build_frame(op, self.name.encode("utf-8"), HEADER_SPEAKER_REPLY)]

        if op == Opcode.SET_NAME:
            if 1 <= len(p) <= MAX_DEVICE_NAME_BYTES:
                self.name = p.decode("utf-8", errors="replace")
                return [build_frame(op, bytes([0x01]), HEADER_SETTER_ALT_ACK)]
            return [build_frame(op, bytes([0x00]), HEADER_SETTER_ALT_ACK)]

        if op == Opcode.QUERY_FIRMWARE:
            return [build_frame(op, self.firmware, HEADER_SPEAKER_REPLY)]

        if op == Opcode.QUERY_CLASSIC_MAC:
            return [build_frame(op, self.classic_mac, HEADER_SPEAKER_REPLY)]

        if op == Opcode.QUERY_INPUT:
            return [
                build_frame(
                    op,
                    bytes([self.input_group, int(self.input_source)]),
                    HEADER_SPEAKER_REPLY,
                )
            ]

        if op == Opcode.SET_INPUT:
            if len(p) >= 2 and p[0] == self.input_group:
                self.input_source = (
                    M90InputSource(p[1])
                    if self.model == MODEL_M90
                    else InputSource(p[1])
                )
                is_bt = int(self.input_source) == 0x01
                if is_bt:
                    self.a2dp_state = 0x0D
                    self.audio_decoding = (
                        0x04
                        if self.ldac_mode in (LdacMode.KHZ_48, LdacMode.KHZ_96)
                        else 0x00
                    )
                else:
                    self.a2dp_state = 0x03
                    self.audio_decoding = 0x05
            return [build_frame(op, bytes([0x01]), HEADER_SPEAKER_REPLY)]

        if op == Opcode.QUERY_VOLUME:
            return [
                build_frame(
                    op, bytes([self.max_volume, self.volume]), HEADER_SPEAKER_REPLY
                )
            ]

        if op == Opcode.SET_VOLUME:
            if p:
                self.volume = max(0, min(self.max_volume, p[0]))
            if self.model == MODEL_M90:
                return [build_frame(op, bytes([0x01]), HEADER_SETTER_ALT_ACK)]
            return [
                build_frame(
                    op, bytes([self.max_volume, self.volume]), HEADER_SPEAKER_REPLY
                )
            ]

        if op == Opcode.MEDIA_PLAYBACK:
            # Speaker forwards AVRCP with no BLE reply.
            return []

        if op == Opcode.QUERY_EQ_PRESET:
            return [
                build_frame(op, bytes([int(self.eq_preset)]), HEADER_SPEAKER_REPLY)
            ]

        if op == Opcode.SET_EQ_PRESET:
            if p:
                self.eq_preset = (
                    M90EqPreset(p[0]) if self.model == MODEL_M90 else EqPreset(p[0])
                )
            return [build_frame(op, bytes([0x01]), HEADER_SPEAKER_REPLY)]

        if op == Opcode.QUERY_CUSTOM_EQ:
            if not self.custom_eq.bands:
                self.custom_eq.bands = default_custom_eq_bands(self.model)
            payload = bytearray([self.custom_eq.format_byte, len(self.custom_eq.bands)])
            for band in self.custom_eq.bands:
                payload.extend(
                    band.to_m90_bytes()
                    if self.model == MODEL_M90
                    else band.to_bytes()
                )
            if self.custom_eq.timestamp is not None:
                payload.extend(self.custom_eq.timestamp.to_bytes(4, "little"))
                if self.custom_eq.name:
                    payload.extend(self.custom_eq.name.encode("utf-8"))
            return [build_frame(op, bytes(payload), HEADER_SPEAKER_REPLY)]

        if op == Opcode.SET_CUSTOM_EQ_BAND:
            if self.model == MODEL_M90 and len(p) == 4:
                band = EqBand.from_m90_bytes(p)
                clamped = EqBand(
                    index=band.index,
                    freq=band.freq,
                    gain_code=max(0x00, min(0x0C, band.gain_code)),
                )
                if 0 <= clamped.index < len(self.custom_eq.bands):
                    self.custom_eq.bands[clamped.index] = clamped
            elif len(p) == 6:
                band = EqBand.from_bytes(p)
                clamped = EqBand(
                    index=band.index,
                    freq=band.freq,
                    gain_code=max(0x00, min(0x0C, band.gain_code)),
                    q_raw=band.q_raw,
                    filter_raw=band.filter_raw,
                )
                if 0 <= clamped.index < len(self.custom_eq.bands):
                    self.custom_eq.bands[clamped.index] = clamped
            return [build_frame(op, bytes([0x01]), HEADER_SPEAKER_REPLY)]

        if op == Opcode.SET_CUSTOM_EQ_META:
            if len(p) >= 4:
                self.custom_eq.timestamp = int.from_bytes(p[:4], "little")
                self.custom_eq.name = p[4:].decode("utf-8", errors="replace")
            return [build_frame(op, bytes([0x01]), HEADER_SPEAKER_REPLY)]

        if op == Opcode.QUERY_LDAC:
            return [
                build_frame(op, bytes([int(self.ldac_mode)]), HEADER_SPEAKER_REPLY)
            ]

        if op == Opcode.SET_LDAC:
            if p:
                self.ldac_mode = LdacMode(p[0])
                self.light_sensitivity = SmartLightSensitivity.HIGH
                if int(self.input_source) == 0x01:
                    self.audio_decoding = (
                        0x04 if self.ldac_mode == LdacMode.KHZ_96 else 0x00
                    )
            return [build_frame(op, bytes([0x01]), HEADER_SPEAKER_REPLY)]

        if op == Opcode.QUERY_CODEC_M90:
            return [
                build_frame(op, bytes([0x0E, int(self.ldac_mode)]), HEADER_SPEAKER_REPLY)
            ]

        if op == Opcode.SET_CODEC_M90:
            if len(p) >= 2:
                self.ldac_mode = LdacMode(p[1])
                if int(self.input_source) == 0x01:
                    self.audio_decoding = (
                        0x04
                        if self.ldac_mode in (LdacMode.KHZ_48, LdacMode.KHZ_96)
                        else 0x00
                    )
            return [
                build_frame(op, bytes([0x0F, int(self.ldac_mode)]), HEADER_SPEAKER_REPLY)
            ]

        if op == Opcode.QUERY_PROMPT_TONE:
            return [
                build_frame(
                    op,
                    bytes([0x02, 0x01 if self.prompt_tone else 0x00]),
                    HEADER_SPEAKER_REPLY,
                )
            ]

        if op == Opcode.SET_PROMPT_TONE:
            if len(p) >= 3:
                self.prompt_tone = p[2] != 0
            return [build_frame(op, bytes([0x01]), HEADER_SPEAKER_REPLY)]

        if op == Opcode.QUERY_SMART_LIGHT:
            return [
                build_frame(
                    op,
                    bytes(
                        [0x03, int(self.light_timer), int(self.light_sensitivity)]
                    ),
                    HEADER_SPEAKER_REPLY,
                )
            ]

        if op == Opcode.SET_SMART_LIGHT:
            if len(p) >= 3:
                self.light_timer = SmartLightTimer(p[1])
                self.light_sensitivity = SmartLightSensitivity(p[2])
            return [build_frame(op, bytes(p[:3]), HEADER_SPEAKER_REPLY)]

        if op == Opcode.QUERY_MULTIPOINT:
            return [
                build_frame(
                    op,
                    bytes([0x00, 0x01 if self.multipoint else 0x00]),
                    HEADER_SPEAKER_REPLY,
                )
            ]

        if op == Opcode.SET_MULTIPOINT:
            if len(p) >= 2:
                self.multipoint = p[1] != 0
            elif p:
                self.multipoint = p[0] != 0
            return [build_frame(op, bytes([0x01]), HEADER_SETTER_ALT_ACK)]

        if op == Opcode.QUERY_POWER_SAVE:
            return [
                build_frame(
                    op,
                    bytes([0x01 if self.power_save else 0x00]),
                    HEADER_SPEAKER_REPLY,
                )
            ]

        if op == Opcode.SET_POWER_SAVE:
            if p:
                self.power_save = p[0] != 0
            return [build_frame(op, bytes([0x01]), HEADER_SETTER_ALT_ACK)]

        if op == Opcode.QUERY_TIMED_OFF:
            return [
                build_frame(
                    op,
                    bytes(
                        [
                            (self.timed_off_minutes >> 8) & 0xFF,
                            self.timed_off_minutes & 0xFF,
                        ]
                    ),
                    HEADER_SPEAKER_REPLY,
                )
            ]

        if op == Opcode.SET_TIMED_OFF:
            if len(p) >= 2:
                self.timed_off_minutes = (p[0] << 8) | p[1]
            return [build_frame(op, bytes([0x01]), HEADER_SETTER_ALT_ACK)]

        if op == Opcode.CANCEL_TIMED_OFF:
            self.timed_off_minutes = 0
            return [build_frame(op, bytes([0x01]), HEADER_SETTER_ALT_ACK)]

        if op == Opcode.POWER_OFF_DEVICE:
            self.powered_off = True
            return []

        if op == Opcode.QUERY_A2DP_STATE:
            return [build_frame(op, bytes([self.a2dp_state]), HEADER_SPEAKER_REPLY)]

        if op == Opcode.QUERY_AUDIO_DECODING:
            return [
                build_frame(op, bytes([self.audio_decoding]), HEADER_SPEAKER_REPLY)
            ]

        if op == Opcode.DISCONNECT_BT_AUDIO:
            self.a2dp_state = 0x03
            return []

        return []


SimulatedEdifierDevice = SimulatedM60Device
