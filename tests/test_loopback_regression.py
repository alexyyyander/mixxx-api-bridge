"""Exercise the Python bridge and real JS mapping on a shared, echoing bus."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from mixxx_api_bridge.bridge import MixxxApiBridge
from mixxx_api_bridge.midi import MemoryMidiTransport, MidiMessage
from mixxx_api_bridge.protocol import (
    OP_ACK, OP_ACTION, OP_CAPABILITIES, OP_COMMAND, OP_ERROR, OP_FEEDBACK,
    OP_GET, OP_HELLO, OP_READY, OP_SETTING_GET, OP_SETTING_VALUE, OP_SUBSCRIBE,
    decode_frame, encode_frame,
)


@pytest.mark.parametrize("operation", [
    OP_HELLO, OP_COMMAND, OP_GET, OP_SUBSCRIBE, OP_ACTION, OP_SETTING_GET,
    OP_CAPABILITIES,
])
def test_request_echo_does_not_report_error_or_replace_capabilities(operation):
    bridge = MixxxApiBridge(MemoryMidiTransport())
    capabilities = {"mapping": "MixxxApiBridge", "supports": ["get"]}
    bridge.handle_midi_message(MidiMessage.sysex(
        encode_frame(OP_CAPABILITIES, capabilities)
    ))
    bridge.handle_midi_message(MidiMessage.sysex(
        encode_frame(operation, {"request_id": "echo"})
    ))
    assert bridge.state.errors == []
    assert bridge.state.remote_capabilities == capabilities


def test_remote_error_is_still_reported():
    bridge = MixxxApiBridge(MemoryMidiTransport())
    bridge.handle_midi_message(MidiMessage.sysex(encode_frame(
        OP_ERROR, {"request_id": "bad", "error": "unsupported operation 99"}
    )))
    assert len(bridge.state.errors) == 1
    assert bridge.state.errors[0]["message"] == "unsupported operation 99"


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_bridge_and_mapping_complete_round_trips_on_echoing_bus():
    root = Path(__file__).parents[1]
    helper = Path(__file__).parent / "helpers/loopback_mapping.js"
    mapping = root / "src/mixxx_api_bridge/mapping/MixxxApiBridge-scripts.js"
    process = subprocess.Popen(
        ["node", str(helper), str(mapping)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1,
    )
    transport = MemoryMidiTransport()
    bridge = MixxxApiBridge(transport)
    consumed = 0
    replies = []

    def mapping_receive(frame):
        process.stdin.write(json.dumps(frame) + "\n")
        process.stdin.flush()
        line = process.stdout.readline()
        assert line, "mapping harness exited without a response"
        result = json.loads(line)
        assert not result.get("overflow"), "mapping replied indefinitely to its own output"
        assert result["processed"] <= 8
        for reply in result["output"]:
            replies.append(decode_frame(reply))
            bridge.handle_midi_message(MidiMessage.sysex(reply))
        return result

    def drain():
        nonlocal consumed
        while consumed < len(transport.sent):
            assert consumed < 30, "bridge generated an unbounded reply chain"
            message = transport.sent[consumed]
            consumed += 1
            bridge.handle_midi_message(message)
            mapping_receive(message.data)

    try:
        bridge.start()
        drain()
        assert bridge.state.connected
        assert bridge.state.remote_capabilities["mapping"] == "MixxxApiBridge"
        assert bridge.state.errors == []
        command = bridge.set_control({"path": "decks/1/volume", "value": 0.4})
        drain()
        assert bridge.state.acknowledgements[command["request_id"]]["value"] == 0.4
        assert bridge.state.controls["[Channel1]/volume"]["value"] == 0.4

        for operation, payload in [
            (OP_GET, {"group": "[Channel1]", "key": "volume"}),
            (OP_SUBSCRIBE, {"group": "[Channel1]", "key": "volume"}),
            (OP_ACTION, {"group": "[Channel1]", "key": "play", "action": "toggle"}),
            (OP_SETTING_GET, {"name": "triggerDelayMs"}),
        ]:
            transport.send_sysex(encode_frame(operation, dict(payload, request_id=str(operation))))
            drain()
        assert bridge.state.controls["[Channel1]/play"]["value"] == 1
        assert bridge.state.settings["triggerDelayMs"] == 200
        assert bridge.state.errors == []
        assert {OP_READY, OP_ACK, OP_FEEDBACK, OP_CAPABILITIES, OP_SETTING_VALUE} <= {
            operation for operation, _ in replies
        }

        result = mapping_receive(encode_frame(99, {"request_id": "bad"}))
        assert len(result["output"]) == 1
        assert len(bridge.state.errors) == 1
        assert "unsupported operation 99" in bridge.state.errors[0]["message"]
        result = mapping_receive(encode_frame(OP_CAPABILITIES, {"mapping": ""}))
        assert result["output"] == []
    finally:
        bridge.close()
        process.stdin.close()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        process.stdout.close()
        process.stderr.close()
