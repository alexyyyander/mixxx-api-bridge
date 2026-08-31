import json

import pytest

from mixxx_api_bridge.protocol import (
    OP_COMMAND,
    OP_HELLO,
    ControlAddress,
    ControlCommand,
    ProtocolError,
    decode_frame,
    encode_frame,
)


def test_frame_round_trip_uses_only_midi_data_bytes():
    payload = {"group": "[频道1]", "key": "volume", "value": 0.5}
    frame = encode_frame(OP_COMMAND, payload)
    assert frame[0] == 0xF0
    assert frame[-1] == 0xF7
    assert all(0 <= value <= 0x7F for value in frame[1:-1])
    operation, decoded = decode_frame(frame)
    assert operation == OP_COMMAND
    assert decoded == payload


def test_bad_magic_is_rejected():
    with pytest.raises(ProtocolError, match="unknown SysEx"):
        decode_frame([0xF0, 0x7D, ord("B"), ord("A"), ord("D"), 1, OP_HELLO, 0xF7])


def test_normalized_command_rejects_out_of_range_value():
    address = ControlAddress("[Channel1]", "volume")
    with pytest.raises(ProtocolError, match="between 0 and 1"):
        ControlCommand(address, 1.1)


def test_unicode_group_and_key_are_valid_json_ascii_frames():
    frame = encode_frame(OP_HELLO, {"label": "混音"})
    payload_bytes = bytes(frame[7:-1])
    assert payload_bytes.isascii()
    assert json.loads(payload_bytes.decode("ascii"))["label"] == "混音"
