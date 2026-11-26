"""Edifier M60 / M90 BLE Control Protocol implementation.

Reference specifications:
- Edifier M60 firmware 2.4.1 (kralonur/edifier-speakers-ble docs/edifier-m60-ble.md)
- Edifier M90 firmware 2.5.1 (kralonur/edifier-speakers-ble docs/edifier-m90-ble.md)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
import struct
import time
from typing import Iterable


# ---------------------------------------------------------------------------
# Model Identifiers & BLE GATT UUIDs / Framing Constants
# ---------------------------------------------------------------------------

MODEL_M60 = "m60"
MODEL_M90 = "m90"
SUPPORTED_MODELS = frozenset({MODEL_M60, MODEL_M90})


def normalize_model(model: str | None) -> str:
    key = (model or MODEL_M60).strip().lower()
    if key in {"m90", "edifier m90"}:
        return MODEL_M90
    if key in {"m60", "edifier m60", ""}:
        return MODEL_M60
    raise ProtocolError(f"Unsupported speaker model: {model!r}")


CONNEX_ADVERTISING_SERVICE_UUID = "0000f600-0000-1000-8000-00805f9b34fb"
M60_CONNEX_ADVERTISING_SERVICE_UUID = CONNEX_ADVERTISING_SERVICE_UUID
M90_CONNEX_ADVERTISING_SERVICE_UUID = "00004503-0000-1000-8000-00805f9b34fb"

M60_GATT_SERVICE_UUID = "4809f601-1a48-11e9-ab14-d663bd873d93"
M90_GATT_SERVICE_UUID = "48094503-1a48-11e9-ab14-d663bd873d93"
M60_NOTIFY_CHAR_UUID = "48090001-1a48-11e9-ab14-d663bd873d93"
M60_WRITE_CHAR_UUID = "48090002-1a48-11e9-ab14-d663bd873d93"
EDIFIER_NOTIFY_CHAR_UUID = M60_NOTIFY_CHAR_UUID
EDIFIER_WRITE_CHAR_UUID = M60_WRITE_CHAR_UUID

HEADER_HOST_REQUEST = 0xAA
HEADER_SPEAKER_REPLY = 0xBB
HEADER_SETTER_ALT_ACK = 0xCC
HEADER_MAGIC = 0xEC
HEADER_MAGIC_ED = 0xED
VALID_MAGIC_BYTES = frozenset({HEADER_MAGIC, HEADER_MAGIC_ED})

VALID_REPLY_HEADERS = frozenset({HEADER_SPEAKER_REPLY, HEADER_SETTER_ALT_ACK})
VALID_ALL_HEADERS = frozenset(
    {HEADER_HOST_REQUEST, HEADER_SPEAKER_REPLY, HEADER_SETTER_ALT_ACK}
)

MAX_VOLUME = 16
M90_MAX_VOLUME = 50
M60_INPUT_GROUP = 0x0F
M90_INPUT_GROUP = 0x1D
MAX_DEVICE_NAME_BYTES = 35

DEFAULT_BAND_FREQS = (62, 250, 1000, 4000, 8000, 16000)
M90_DEFAULT_BAND_FREQS = (62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000)
MIN_EQ_GAIN_CODE = 0x00  # -3.0 dB
ZERO_EQ_GAIN_CODE = 0x06  # 0.0 dB
MAX_EQ_GAIN_CODE = 0x0C  # +3.0 dB
DEFAULT_Q_RAW = 0x07


def max_volume_for_model(model: str) -> int:
    return M90_MAX_VOLUME if normalize_model(model) == MODEL_M90 else MAX_VOLUME


class Opcode(IntEnum):
    QUERY_SUB_OUT = 0x13  # M90, 0xED magic
    SET_SUB_OUT = 0x14  # M90, 0xED magic
    QUERY_CUSTOM_EQ = 0x43
    SET_CUSTOM_EQ_BAND = 0x44
    SET_CUSTOM_EQ_META = 0x47
    QUERY_LDAC = 0x48
    SET_LDAC = 0x49
    QUERY_INPUT = 0x61
    SET_INPUT = 0x62
    QUERY_VOLUME = 0x66
    SET_VOLUME = 0x67
    QUERY_AUDIO_DECODING = 0x68
    QUERY_MULTIPOINT = 0x7C  # M90
    SET_MULTIPOINT = 0x7D  # M90
    QUERY_SMART_LIGHT = 0x84
    SET_SMART_LIGHT = 0x85
    QUERY_PROMPT_TONE = 0x86
    SET_PROMPT_TONE = 0x87
    QUERY_CODEC_M90 = 0x91  # M90
    SET_CODEC_M90 = 0x92  # M90
    QUERY_POWER_SAVE = 0xB1  # M90
    SET_POWER_SAVE = 0xB2  # M90
    MEDIA_PLAYBACK = 0xC2
    QUERY_A2DP_STATE = 0xC3
    SET_EQ_PRESET = 0xC4
    QUERY_FIRMWARE = 0xC6
    QUERY_CLASSIC_MAC = 0xC8
    QUERY_NAME = 0xC9
    SET_NAME = 0xCA
    DISCONNECT_BT_AUDIO = 0xCD
    POWER_OFF_DEVICE = 0xCE  # M90
    SET_TIMED_OFF = 0xD1  # M90
    CANCEL_TIMED_OFF = 0xD2  # M90
    QUERY_TIMED_OFF = 0xD3  # M90
    QUERY_EQ_PRESET = 0xD5
    QUERY_CAPABILITIES = 0xD8


class InputSource(IntEnum):
    BLUETOOTH = 0x01
    USB = 0x02
    AUX = 0x03

    @property
    def label(self) -> str:
        return {
            InputSource.BLUETOOTH: "bluetooth",
            InputSource.USB: "usb",
            InputSource.AUX: "aux",
        }[self]

    @classmethod
    def from_str(cls, value: str) -> "InputSource":
        mapping = {
            "bluetooth": cls.BLUETOOTH,
            "bt": cls.BLUETOOTH,
            "usb": cls.USB,
            "usb-c": cls.USB,
            "usbc": cls.USB,
            "aux": cls.AUX,
        }
        key = value.strip().lower()
        if key not in mapping:
            raise ValueError(f"Unsupported input source: {value!r}")
        return mapping[key]


class M90InputSource(IntEnum):
    BLUETOOTH = 0x01
    USB = 0x02
    HDMI = 0x03
    OPTICAL = 0x04
    AUX = 0x05

    @property
    def label(self) -> str:
        return {
            M90InputSource.BLUETOOTH: "bluetooth",
            M90InputSource.USB: "usb",
            M90InputSource.HDMI: "hdmi",
            M90InputSource.OPTICAL: "optical",
            M90InputSource.AUX: "aux",
        }[self]

    @classmethod
    def from_str(cls, value: str) -> "M90InputSource":
        mapping = {
            "bluetooth": cls.BLUETOOTH,
            "bt": cls.BLUETOOTH,
            "usb": cls.USB,
            "usb-c": cls.USB,
            "usbc": cls.USB,
            "hdmi": cls.HDMI,
            "hdmi-arc": cls.HDMI,
            "arc": cls.HDMI,
            "optical": cls.OPTICAL,
            "opt": cls.OPTICAL,
            "toslink": cls.OPTICAL,
            "aux": cls.AUX,
        }
        key = value.strip().lower()
        if key not in mapping:
            raise ValueError(f"Unsupported M90 input source: {value!r}")
        return mapping[key]


class EqPreset(IntEnum):
    MUSIC = 0x00
    MONITOR = 0x01
    GAME = 0x02
    MOVIE = 0x03
    CUSTOMIZED = 0x04

    @property
    def label(self) -> str:
        return {
            EqPreset.MUSIC: "music",
            EqPreset.MONITOR: "monitor",
            EqPreset.GAME: "game",
            EqPreset.MOVIE: "movie",
            EqPreset.CUSTOMIZED: "customized",
        }[self]

    @classmethod
    def from_str(cls, value: str) -> "EqPreset":
        mapping = {
            "music": cls.MUSIC,
            "monitor": cls.MONITOR,
            "game": cls.GAME,
            "gaming": cls.GAME,
            "movie": cls.MOVIE,
            "customized": cls.CUSTOMIZED,
            "custom": cls.CUSTOMIZED,
        }
        key = value.strip().lower()
        if key not in mapping:
            raise ValueError(f"Unsupported EQ preset: {value!r}")
        return mapping[key]


class M90EqPreset(IntEnum):
    CLASSIC = 0x00
    MONITOR = 0x01
    DYNAMIC = 0x02
    CUSTOM = 0x03

    @property
    def label(self) -> str:
        return {
            M90EqPreset.CLASSIC: "classic",
            M90EqPreset.MONITOR: "monitor",
            M90EqPreset.DYNAMIC: "dynamic",
            M90EqPreset.CUSTOM: "custom",
        }[self]

    @classmethod
    def from_str(cls, value: str) -> "M90EqPreset":
        mapping = {
            "classic": cls.CLASSIC,
            "music": cls.CLASSIC,
            "monitor": cls.MONITOR,
            "dynamic": cls.DYNAMIC,
            "custom": cls.CUSTOM,
            "customized": cls.CUSTOM,
        }
        key = value.strip().lower()
        if key not in mapping:
            raise ValueError(f"Unsupported M90 EQ preset: {value!r}")
        return mapping[key]


class SubOutLevel(IntEnum):
    LOW = 0x00
    MEDIUM = 0x01
    HIGH = 0x02

    @property
    def label(self) -> str:
        return {
            SubOutLevel.LOW: "low",
            SubOutLevel.MEDIUM: "medium",
            SubOutLevel.HIGH: "high",
        }[self]

    @classmethod
    def from_str(cls, value: str) -> "SubOutLevel":
        mapping = {
            "low": cls.LOW,
            "medium": cls.MEDIUM,
            "med": cls.MEDIUM,
            "mid": cls.MEDIUM,
            "high": cls.HIGH,
        }
        key = value.strip().lower()
        if key not in mapping:
            raise ValueError(f"Unsupported Sub Out level: {value!r}")
        return mapping[key]


class LdacMode(IntEnum):
    DISABLED = 0x00
    KHZ_48 = 0x01
    KHZ_96 = 0x02

    @property
    def label(self) -> str:
        return {
            LdacMode.DISABLED: "disabled",
            LdacMode.KHZ_48: "48khz",
            LdacMode.KHZ_96: "96khz",
        }[self]

    @classmethod
    def from_str(cls, value: str) -> "LdacMode":
        mapping = {
            "disabled": cls.DISABLED,
            "default": cls.DISABLED,
            "off": cls.DISABLED,
            "48khz": cls.KHZ_48,
            "44.1/48": cls.KHZ_48,
            "96khz": cls.KHZ_96,
        }
        key = value.strip().lower()
        if key not in mapping:
            raise ValueError(f"Unsupported LDAC mode: {value!r}")
        return mapping[key]


class SmartLightTimer(IntEnum):
    SEC_5 = 0x00
    SEC_10 = 0x01
    SEC_20 = 0x02
    ALWAYS_ON = 0x03

    @property
    def label(self) -> str:
        return {
            SmartLightTimer.SEC_5: "5s",
            SmartLightTimer.SEC_10: "10s",
            SmartLightTimer.SEC_20: "20s",
            SmartLightTimer.ALWAYS_ON: "always_on",
        }[self]

    @classmethod
    def from_str(cls, value: str) -> "SmartLightTimer":
        mapping = {
            "5s": cls.SEC_5,
            "5": cls.SEC_5,
            "10s": cls.SEC_10,
            "10": cls.SEC_10,
            "20s": cls.SEC_20,
            "20": cls.SEC_20,
            "always_on": cls.ALWAYS_ON,
            "always": cls.ALWAYS_ON,
            "on": cls.ALWAYS_ON,
        }
        key = value.strip().lower()
        if key not in mapping:
            raise ValueError(f"Unsupported smart light timer: {value!r}")
        return mapping[key]


class SmartLightSensitivity(IntEnum):
    HIGH = 0x00
    GENERAL = 0x01
    LOW = 0x02

    @property
    def label(self) -> str:
        return {
            SmartLightSensitivity.HIGH: "high",
            SmartLightSensitivity.GENERAL: "general",
            SmartLightSensitivity.LOW: "low",
        }[self]

    @classmethod
    def from_str(cls, value: str) -> "SmartLightSensitivity":
        mapping = {
            "high": cls.HIGH,
            "general": cls.GENERAL,
            "medium": cls.GENERAL,
            "low": cls.LOW,
        }
        key = value.strip().lower()
        if key not in mapping:
            raise ValueError(f"Unsupported smart light sensitivity: {value!r}")
        return mapping[key]


class PlaybackAction(IntEnum):
    PLAY = 0x00
    PAUSE = 0x01
    NEXT = 0x04
    PREVIOUS = 0x05

    @classmethod
    def from_str(cls, value: str) -> "PlaybackAction":
        mapping = {
            "play": cls.PLAY,
            "pause": cls.PAUSE,
            "next": cls.NEXT,
            "previous": cls.PREVIOUS,
            "prev": cls.PREVIOUS,
        }
        key = value.strip().lower()
        if key not in mapping:
            raise ValueError(f"Unsupported playback action: {value!r}")
        return mapping[key]


class ProtocolError(ValueError):
    """Raised when a BLE frame is malformed or violates protocol rules."""


@dataclass(frozen=True)
class Frame:
    direction: int
    opcode: int
    payload: bytes
    raw: bytes
    magic: int = HEADER_MAGIC

    @property
    def hex_str(self) -> str:
        return self.raw.hex(" ").upper()


@dataclass
class EqBand:
    index: int
    freq: int
    gain_code: int = ZERO_EQ_GAIN_CODE
    q_raw: int = DEFAULT_Q_RAW
    filter_raw: int = 0x00

    @property
    def gain_db(self) -> float:
        return round((self.gain_code - ZERO_EQ_GAIN_CODE) * 0.5, 1)

    @classmethod
    def from_db(
        cls,
        index: int,
        freq: int,
        gain_db: float,
        q_raw: int = DEFAULT_Q_RAW,
        filter_raw: int = 0x00,
    ) -> "EqBand":
        return cls(
            index=index,
            freq=freq,
            gain_code=db_to_gain_code(gain_db),
            q_raw=q_raw,
            filter_raw=filter_raw,
        )

    def to_bytes(self) -> bytes:
        if not 0 <= self.index <= 5:
            raise ProtocolError(f"M60 band index must be 0..5, got {self.index}")
        if not 0 <= self.freq <= 0xFFFF:
            raise ProtocolError(f"Frequency out of range: {self.freq}")
        gain_code = max(MIN_EQ_GAIN_CODE, min(MAX_EQ_GAIN_CODE, self.gain_code))
        return bytes(
            [
                self.index & 0xFF,
                self.filter_raw & 0xFF,
                (self.freq >> 8) & 0xFF,
                self.freq & 0xFF,
                gain_code & 0xFF,
                self.q_raw & 0xFF,
            ]
        )

    def to_m90_bytes(self) -> bytes:
        if not 0 <= self.index <= 8:
            raise ProtocolError(f"M90 band index must be 0..8, got {self.index}")
        if not 0 <= self.freq <= 0xFFFF:
            raise ProtocolError(f"Frequency out of range: {self.freq}")
        gain_code = max(MIN_EQ_GAIN_CODE, min(MAX_EQ_GAIN_CODE, self.gain_code))
        return bytes(
            [
                self.index & 0xFF,
                (self.freq >> 8) & 0xFF,
                self.freq & 0xFF,
                gain_code & 0xFF,
            ]
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> "EqBand":
        if len(data) != 6:
            raise ProtocolError(f"Expected 6-byte M60 EQ record, got {len(data)}")
        index, filter_raw, freq_hi, freq_lo, gain_code, q_raw = data
        return cls(
            index=index,
            filter_raw=filter_raw,
            freq=(freq_hi << 8) | freq_lo,
            gain_code=gain_code,
            q_raw=q_raw,
        )

    @classmethod
    def from_m90_bytes(cls, data: bytes) -> "EqBand":
        if len(data) != 4:
            raise ProtocolError(f"Expected 4-byte M90 EQ record, got {len(data)}")
        index, freq_hi, freq_lo, gain_code = data
        return cls(
            index=index,
            freq=(freq_hi << 8) | freq_lo,
            gain_code=gain_code,
            q_raw=DEFAULT_Q_RAW,
            filter_raw=0x00,
        )

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "freq": self.freq,
            "gain_code": self.gain_code,
            "gain_db": self.gain_db,
            "q_raw": self.q_raw,
            "filter_raw": self.filter_raw,
        }


@dataclass
class CustomEqState:
    format_byte: int = 0x03
    bands: list[EqBand] = field(default_factory=list)
    timestamp: int | None = None
    name: str = ""

    def to_dict(self) -> dict:
        return {
            "format": self.format_byte,
            "bands": [b.to_dict() for b in self.bands],
            "timestamp": self.timestamp,
            "name": self.name,
        }


def default_custom_eq_bands(model: str = MODEL_M60) -> list[EqBand]:
    freqs = (
        M90_DEFAULT_BAND_FREQS
        if normalize_model(model) == MODEL_M90
        else DEFAULT_BAND_FREQS
    )
    return [
        EqBand(index=i, freq=freq, gain_code=ZERO_EQ_GAIN_CODE, q_raw=DEFAULT_Q_RAW)
        for i, freq in enumerate(freqs)
    ]


def gain_code_to_db(code: int) -> float:
    return round((code - ZERO_EQ_GAIN_CODE) * 0.5, 1)


def db_to_gain_code(db: float) -> int:
    code = round(db * 2.0) + ZERO_EQ_GAIN_CODE
    return max(MIN_EQ_GAIN_CODE, min(MAX_EQ_GAIN_CODE, int(code)))


def compute_checksum(data: bytes) -> int:
    return sum(data) & 0xFF


def build_frame(
    opcode: int,
    payload: bytes = b"",
    direction: int = HEADER_HOST_REQUEST,
    magic: int = HEADER_MAGIC,
) -> bytes:
    if direction not in VALID_ALL_HEADERS:
        raise ProtocolError(f"Invalid frame header byte: 0x{direction:02X}")
    if magic not in VALID_MAGIC_BYTES:
        raise ProtocolError(f"Invalid frame magic byte: 0x{magic:02X}")
    length = len(payload)
    body = bytes(
        [
            direction & 0xFF,
            magic & 0xFF,
            opcode & 0xFF,
            (length >> 8) & 0xFF,
            length & 0xFF,
        ]
    ) + payload
    return body + bytes([compute_checksum(body)])


def parse_frame(raw: bytes) -> Frame:
    if len(raw) < 6:
        raise ProtocolError(f"Frame too short ({len(raw)} bytes)")
    direction, magic, opcode, len_hi, len_lo = raw[:5]
    if direction not in VALID_ALL_HEADERS or magic not in VALID_MAGIC_BYTES:
        raise ProtocolError(f"Invalid header: {raw[:2].hex(' ').upper()}")
    payload_len = (len_hi << 8) | len_lo
    expected_len = 5 + payload_len + 1
    if len(raw) != expected_len:
        raise ProtocolError(
            f"Length mismatch: expected {expected_len} bytes, got {len(raw)}"
        )
    expected_cs = compute_checksum(raw[:-1])
    actual_cs = raw[-1]
    if actual_cs != expected_cs:
        raise ProtocolError(
            f"Checksum mismatch: expected 0x{expected_cs:02X}, got 0x{actual_cs:02X}"
        )
    return Frame(
        direction=direction,
        opcode=opcode,
        payload=bytes(raw[5:-1]),
        raw=bytes(raw),
        magic=magic,
    )


class FrameReassembler:
    """Buffers BLE notification chunks and extracts complete checksum-valid frames."""

    def __init__(self, allowed_headers: Iterable[int] = VALID_REPLY_HEADERS) -> None:
        self._buf = bytearray()
        self._allowed_headers = frozenset(allowed_headers)

    def feed(self, chunk: bytes) -> list[Frame]:
        if chunk:
            self._buf.extend(chunk)
        frames: list[Frame] = []
        while len(self._buf) >= 2:
            header_idx = self._find_header_index()
            if header_idx < 0:
                # Retain trailing byte if it could be the start of a header across chunks.
                if self._buf and self._buf[-1] in self._allowed_headers:
                    self._buf = self._buf[-1:]
                else:
                    self._buf.clear()
                break
            if header_idx > 0:
                del self._buf[:header_idx]
            if len(self._buf) < 6:
                break
            payload_len = (self._buf[3] << 8) | self._buf[4]
            total_len = 5 + payload_len + 1
            if total_len > 1024:
                # Implausibly large frame length: skip corrupt header byte and resync.
                del self._buf[0]
                continue
            if len(self._buf) < total_len:
                break
            candidate = bytes(self._buf[:total_len])
            try:
                frame = parse_frame(candidate)
            except ProtocolError:
                # Corrupt framing or checksum: advance 1 byte and continue scanning.
                del self._buf[0]
                continue
            del self._buf[:total_len]
            frames.append(frame)
        return frames

    def clear(self) -> None:
        self._buf.clear()

    def _find_header_index(self) -> int:
        for i in range(len(self._buf) - 1):
            if (
                self._buf[i] in self._allowed_headers
                and self._buf[i + 1] in VALID_MAGIC_BYTES
            ):
                return i
        return -1


# ---------------------------------------------------------------------------
# Typed Command Builders
# ---------------------------------------------------------------------------


def cmd_query_capabilities() -> bytes:
    return build_frame(Opcode.QUERY_CAPABILITIES)


def cmd_query_name() -> bytes:
    return build_frame(Opcode.QUERY_NAME)


def cmd_set_name(name: str) -> bytes:
    encoded = name.encode("utf-8")
    if not 1 <= len(encoded) <= MAX_DEVICE_NAME_BYTES:
        raise ProtocolError(
            f"Device name must be 1..{MAX_DEVICE_NAME_BYTES} UTF-8 bytes, got {len(encoded)}"
        )
    return build_frame(Opcode.SET_NAME, encoded)


def cmd_query_firmware() -> bytes:
    return build_frame(Opcode.QUERY_FIRMWARE)


def cmd_query_classic_mac() -> bytes:
    return build_frame(Opcode.QUERY_CLASSIC_MAC)


def cmd_query_input() -> bytes:
    return build_frame(Opcode.QUERY_INPUT)


def cmd_set_input(
    source: InputSource | M90InputSource, model: str = MODEL_M60
) -> bytes:
    group = (
        M90_INPUT_GROUP
        if isinstance(source, M90InputSource) or normalize_model(model) == MODEL_M90
        else M60_INPUT_GROUP
    )
    return build_frame(Opcode.SET_INPUT, bytes([group, int(source)]))


def cmd_query_volume() -> bytes:
    return build_frame(Opcode.QUERY_VOLUME)


def cmd_set_volume(level: int, max_volume: int = MAX_VOLUME) -> bytes:
    if not 0 <= level <= max_volume:
        raise ProtocolError(f"Volume must be 0..{max_volume}, got {level}")
    return build_frame(Opcode.SET_VOLUME, bytes([level]))


def cmd_playback(action: PlaybackAction) -> bytes:
    return build_frame(Opcode.MEDIA_PLAYBACK, bytes([int(action)]))


def cmd_query_eq_preset() -> bytes:
    return build_frame(Opcode.QUERY_EQ_PRESET)


def cmd_set_eq_preset(preset: EqPreset | M90EqPreset) -> bytes:
    return build_frame(Opcode.SET_EQ_PRESET, bytes([int(preset)]))


def cmd_query_custom_eq() -> bytes:
    return build_frame(Opcode.QUERY_CUSTOM_EQ)


def cmd_set_custom_eq_band(band: EqBand, model: str = MODEL_M60) -> bytes:
    raw_band = (
        band.to_m90_bytes()
        if normalize_model(model) == MODEL_M90
        else band.to_bytes()
    )
    return build_frame(Opcode.SET_CUSTOM_EQ_BAND, raw_band)


def cmd_set_custom_eq_meta(name: str = "", timestamp: int | None = None) -> bytes:
    ts = int(time.time()) if timestamp is None else int(timestamp)
    payload = struct.pack("<I", ts) + name.encode("utf-8")
    return build_frame(Opcode.SET_CUSTOM_EQ_META, payload)


def cmd_query_ldac() -> bytes:
    return build_frame(Opcode.QUERY_LDAC)


def cmd_set_ldac(mode: LdacMode) -> bytes:
    return build_frame(Opcode.SET_LDAC, bytes([int(mode)]))


def cmd_query_prompt_tone() -> bytes:
    return build_frame(Opcode.QUERY_PROMPT_TONE)


def cmd_set_prompt_tone(enabled: bool) -> bytes:
    return build_frame(Opcode.SET_PROMPT_TONE, bytes([0x02, 0x01, 0x01 if enabled else 0x00]))


def cmd_query_smart_light() -> bytes:
    return build_frame(Opcode.QUERY_SMART_LIGHT)


def cmd_set_smart_light(
    timer: SmartLightTimer, sensitivity: SmartLightSensitivity
) -> bytes:
    return build_frame(
        Opcode.SET_SMART_LIGHT, bytes([0x03, int(timer), int(sensitivity)])
    )


def cmd_query_a2dp_state() -> bytes:
    return build_frame(Opcode.QUERY_A2DP_STATE)


def cmd_query_audio_decoding() -> bytes:
    return build_frame(Opcode.QUERY_AUDIO_DECODING)


def cmd_disconnect_bt_audio() -> bytes:
    return build_frame(Opcode.DISCONNECT_BT_AUDIO)


def cmd_query_codec_m90() -> bytes:
    return build_frame(Opcode.QUERY_CODEC_M90)


def cmd_set_codec_m90(ldac_mode: LdacMode, lhdc: int = 0xFF) -> bytes:
    return build_frame(
        Opcode.SET_CODEC_M90, bytes([0x0E, int(ldac_mode), lhdc & 0xFF])
    )


def cmd_query_sub_out() -> bytes:
    return build_frame(Opcode.QUERY_SUB_OUT, magic=HEADER_MAGIC_ED)


def cmd_set_sub_out(level: SubOutLevel) -> bytes:
    return build_frame(
        Opcode.SET_SUB_OUT, bytes([0x00, int(level)]), magic=HEADER_MAGIC_ED
    )


def cmd_query_multipoint() -> bytes:
    return build_frame(Opcode.QUERY_MULTIPOINT)


def cmd_set_multipoint(enabled: bool) -> bytes:
    return build_frame(
        Opcode.SET_MULTIPOINT, bytes([0x00, 0x01 if enabled else 0x00])
    )


def cmd_query_power_save() -> bytes:
    return build_frame(Opcode.QUERY_POWER_SAVE)


def cmd_set_power_save(enabled: bool) -> bytes:
    return build_frame(Opcode.SET_POWER_SAVE, bytes([0x01 if enabled else 0x00]))


def cmd_query_timed_off() -> bytes:
    return build_frame(Opcode.QUERY_TIMED_OFF)


def cmd_set_timed_off(minutes: int) -> bytes:
    if not 0 <= minutes <= 0xFFFF:
        raise ProtocolError(f"Timed off minutes must be 0..65535, got {minutes}")
    if minutes == 0:
        return cmd_cancel_timed_off()
    return build_frame(
        Opcode.SET_TIMED_OFF, bytes([(minutes >> 8) & 0xFF, minutes & 0xFF])
    )


def cmd_cancel_timed_off() -> bytes:
    return build_frame(Opcode.CANCEL_TIMED_OFF)


def cmd_power_off_device() -> bytes:
    return build_frame(Opcode.POWER_OFF_DEVICE)


# ---------------------------------------------------------------------------
# Typed Payload Decoders
# ---------------------------------------------------------------------------


def decode_name(payload: bytes) -> str:
    return payload.decode("utf-8", errors="replace").rstrip("\x00")


def decode_firmware(payload: bytes) -> str:
    if len(payload) < 3:
        return payload.hex(".")
    return f"{payload[0]}.{payload[1]}.{payload[2]}"


def decode_classic_mac(payload: bytes) -> str:
    return ":".join(f"{b:02X}" for b in payload)


def decode_capabilities(payload: bytes) -> dict:
    return {
        "raw_hex": payload.hex(" ").upper(),
        "eq_profile": payload[13] if len(payload) > 13 else None,
        "ldac_flag": payload[18] if len(payload) > 18 else None,
        "length": len(payload),
    }


def decode_input(
    payload: bytes, model: str = MODEL_M60
) -> InputSource | M90InputSource:
    if len(payload) >= 2 and payload[0] == M90_INPUT_GROUP:
        return M90InputSource(payload[1])
    if len(payload) >= 2 and payload[0] == M60_INPUT_GROUP:
        return InputSource(payload[1])
    if len(payload) == 1:
        return (
            M90InputSource(payload[0])
            if normalize_model(model) == MODEL_M90
            else InputSource(payload[0])
        )
    raise ProtocolError(f"Unexpected input payload: {payload.hex(' ')}")


def decode_volume(payload: bytes) -> tuple[int, int]:
    if len(payload) < 2:
        raise ProtocolError(f"Expected 2-byte volume payload, got {payload.hex(' ')}")
    return int(payload[0]), int(payload[1])


def decode_eq_preset(
    payload: bytes, model: str = MODEL_M60
) -> EqPreset | M90EqPreset:
    if not payload:
        raise ProtocolError("Empty EQ preset payload")
    return (
        M90EqPreset(payload[0])
        if normalize_model(model) == MODEL_M90
        else EqPreset(payload[0])
    )


def decode_custom_eq(payload: bytes) -> CustomEqState:
    if len(payload) < 2:
        raise ProtocolError(f"Custom EQ payload too short: {len(payload)} bytes")
    fmt = payload[0]
    band_count = payload[1]
    is_m90_format = fmt == 0x10 or (
        band_count == 9
        and len(payload) >= 2 + band_count * 4
        and len(payload) < 2 + band_count * 6
    )
    record_size = 4 if is_m90_format else 6
    bands_end = 2 + band_count * record_size
    if len(payload) < bands_end:
        raise ProtocolError(
            f"Truncated custom EQ bands: expected {bands_end} bytes, got {len(payload)}"
        )
    bands: list[EqBand] = []
    for i in range(band_count):
        offset = 2 + i * record_size
        chunk = payload[offset : offset + record_size]
        bands.append(
            EqBand.from_m90_bytes(chunk)
            if is_m90_format
            else EqBand.from_bytes(chunk)
        )

    ts: int | None = None
    name = ""
    tail = payload[bands_end:]
    if len(tail) >= 4:
        ts = struct.unpack("<I", tail[:4])[0]
        if len(tail) > 4:
            name = tail[4:].decode("utf-8", errors="replace").rstrip("\x00")
    return CustomEqState(format_byte=fmt, bands=bands, timestamp=ts, name=name)


def decode_ldac(payload: bytes) -> LdacMode:
    if not payload:
        raise ProtocolError("Empty LDAC payload")
    return LdacMode(payload[0])


def decode_codec_m90(payload: bytes) -> LdacMode:
    if len(payload) >= 2 and payload[0] == 0x0E:
        return LdacMode(payload[1])
    if len(payload) == 1:
        return LdacMode(payload[0])
    raise ProtocolError(f"Unexpected M90 codec payload: {payload.hex(' ')}")


def decode_sub_out(payload: bytes) -> SubOutLevel:
    if len(payload) >= 2:
        return SubOutLevel(payload[1])
    if len(payload) == 1:
        return SubOutLevel(payload[0])
    raise ProtocolError("Empty Sub Out payload")


def decode_multipoint(payload: bytes) -> bool:
    if len(payload) >= 2:
        return payload[1] != 0
    if len(payload) == 1:
        return payload[0] != 0
    raise ProtocolError("Empty multipoint payload")


def decode_power_save(payload: bytes) -> bool:
    if len(payload) >= 2:
        return payload[1] != 0
    if len(payload) == 1:
        return payload[0] != 0
    raise ProtocolError("Empty power save payload")


def decode_timed_off(payload: bytes) -> int:
    if len(payload) < 2:
        raise ProtocolError(f"Expected 2-byte timed-off payload, got {payload.hex(' ')}")
    return (payload[0] << 8) | payload[1]


def decode_prompt_tone(payload: bytes) -> bool:
    if len(payload) >= 2:
        return payload[1] != 0
    if len(payload) == 1:
        return payload[0] != 0
    raise ProtocolError("Empty prompt tone payload")


def decode_smart_light(payload: bytes) -> tuple[SmartLightTimer, SmartLightSensitivity]:
    if len(payload) < 3:
        raise ProtocolError(
            f"Expected 3-byte smart light payload, got {payload.hex(' ')}"
        )
    return SmartLightTimer(payload[1]), SmartLightSensitivity(payload[2])


def decode_a2dp_state(payload: bytes) -> tuple[int, str]:
    if not payload:
        raise ProtocolError("Empty A2DP state payload")
    code = payload[0]
    labels = {0x03: "closed", 0x0D: "streaming"}
    return code, labels.get(code, f"unknown (0x{code:02X})")


def decode_audio_decoding(payload: bytes) -> tuple[int, str]:
    if not payload:
        raise ProtocolError("Empty audio decoding payload")
    code = payload[0]
    labels = {
        0x00: "Standard / 48 kHz",
        0x04: "Wireless Hi-Res (LDAC)",
        0x05: "Wired Hi-Res (USB 96 kHz / AUX)",
        0x09: "Hi-Res 192 kHz",
    }
    return code, labels.get(code, f"Code 0x{code:02X}")


def describe_frame(frame: Frame) -> str:
    """Human-readable summary for the live frame diagnostics log."""
    direction = "TX" if frame.direction == HEADER_HOST_REQUEST else "RX"
    try:
        op_name = Opcode(frame.opcode).name
    except ValueError:
        op_name = f"0x{frame.opcode:02X}"
    return f"{direction} {op_name} ({len(frame.payload)}B)"
