"""Wire protocol shared by the sidecar and the Mixxx controller mapping.

The transport is MIDI SysEx, but the payload is JSON encoded as ASCII. MIDI
SysEx data bytes must be 7-bit; ``ensure_ascii=True`` guarantees that the JSON
payload satisfies that requirement while retaining arbitrary Unicode strings.
"""

from __future__ import annotations

import json
import math
import uuid
from dataclasses import dataclass
from typing import Any, Mapping


SYSEX_START = 0xF0
SYSEX_END = 0xF7
NONCOMMERCIAL_ID = 0x7D
MAGIC = b"MXA"
PROTOCOL_VERSION = 1

OP_HELLO = 0x00
OP_COMMAND = 0x01
OP_FEEDBACK = 0x02
OP_CAPABILITIES = 0x03
OP_SUBSCRIBE = 0x04
OP_GET = 0x05
OP_ACTION = 0x06
OP_SETTING_GET = 0x07
OP_READY = 0x10
OP_ACK = 0x11
OP_SETTING_VALUE = 0x12
OP_ERROR = 0x7F

_HEADER = bytes([SYSEX_START, NONCOMMERCIAL_ID, *MAGIC, PROTOCOL_VERSION])


class ProtocolError(ValueError):
    """Raised when an incoming or outgoing frame is malformed."""


def new_request_id() -> str:
    return uuid.uuid4().hex


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    try:
        encoded = json.dumps(
            payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, UnicodeEncodeError) as exc:
        raise ProtocolError(f"payload is not JSON encodable: {exc}") from exc
    if any(byte >= 0x80 for byte in encoded):
        raise ProtocolError("SysEx payload contains a non-7-bit byte")
    return encoded


def encode_frame(operation: int, payload: Mapping[str, Any] | None = None) -> list[int]:
    """Encode a protocol frame including the F0/F7 delimiters."""

    if not 0 <= operation <= 0x7F:
        raise ProtocolError("operation must be a MIDI data byte (0..127)")
    body = _json_bytes(payload or {})
    return [*_HEADER, operation, *body, SYSEX_END]


def decode_frame(data: bytes | bytearray | list[int] | tuple[int, ...]) -> tuple[int, dict[str, Any]]:
    """Decode a frame produced by :func:`encode_frame`."""

    values = list(data)
    if len(values) < len(_HEADER) + 2:
        raise ProtocolError("frame is too short")
    if values[0] != SYSEX_START or values[-1] != SYSEX_END:
        raise ProtocolError("missing SysEx delimiters")
    if bytes(values[: len(_HEADER)]) != _HEADER:
        raise ProtocolError("unknown SysEx manufacturer/magic/version")
    if any(not 0 <= value <= 0x7F for value in values[1:-1]):
        raise ProtocolError("SysEx contains a non-7-bit data byte")

    operation = values[len(_HEADER)]
    raw_payload = bytes(values[len(_HEADER) + 1 : -1])
    try:
        parsed = json.loads(raw_payload.decode("ascii") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError(f"invalid JSON payload: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ProtocolError("payload must be a JSON object")
    return operation, parsed


@dataclass(frozen=True)
class ControlAddress:
    """A Mixxx ControlObject address, represented as group + key."""

    group: str
    key: str

    def __post_init__(self) -> None:
        if not self.group.startswith("[") or not self.group.endswith("]"):
            raise ProtocolError("group must look like '[Channel1]'")
        for name, value in (("group", self.group), ("key", self.key)):
            if not value or any(ord(char) < 0x20 or ord(char) >= 0x7F for char in value):
                raise ProtocolError(f"{name} must contain printable ASCII characters")
        if any(char in self.group or char in self.key for char in ("\n", "\r")):
            raise ProtocolError("control address cannot contain line breaks")

    @property
    def identifier(self) -> str:
        return f"{self.group}/{self.key}"


@dataclass(frozen=True)
class ControlCommand:
    address: ControlAddress
    value: float
    scale: str = "normalized"
    request_id: str = ""

    def __post_init__(self) -> None:
        if self.scale not in {"normalized", "raw"}:
            raise ProtocolError("scale must be 'normalized' or 'raw'")
        if not math.isfinite(self.value):
            raise ProtocolError("value must be finite")
        if self.scale == "normalized" and not 0.0 <= self.value <= 1.0:
            raise ProtocolError("normalized value must be between 0 and 1")

    @property
    def id(self) -> str:
        return self.request_id or new_request_id()

    def payload(self) -> dict[str, Any]:
        return {
            "group": self.address.group,
            "key": self.address.key,
            "value": self.value,
            "scale": self.scale,
            "request_id": self.id,
        }
