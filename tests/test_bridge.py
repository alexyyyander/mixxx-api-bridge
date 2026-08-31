from mixxx_api_bridge.bridge import MixxxApiBridge
from mixxx_api_bridge.midi import MemoryMidiTransport, MidiMessage
from mixxx_api_bridge.protocol import (
    OP_CAPABILITIES,
    OP_FEEDBACK,
    OP_READY,
    ProtocolError,
    decode_frame,
    encode_frame,
)


def test_start_sends_hello_and_ready_connects():
    transport = MemoryMidiTransport()
    bridge = MixxxApiBridge(transport)
    bridge.start()
    assert len(transport.sent) == 1
    operation, payload = decode_frame(transport.sent[0].data)
    assert operation == 0
    assert payload["client"] == "mixxx-api-bridge"

    transport.emit(
        MidiMessage.sysex(
            encode_frame(
                OP_READY,
                {"mapping": "MixxxApiBridge", "protocol": 1},
            )
        )
    )
    assert bridge.state.connected is True
    assert bridge.state.mapping["mapping"] == "MixxxApiBridge"
    operation, payload = decode_frame(transport.sent[-1].data)
    assert operation == OP_CAPABILITIES
    assert payload["protocol"] == 1


def test_set_control_sends_command_frame():
    transport = MemoryMidiTransport()
    bridge = MixxxApiBridge(transport)
    result = bridge.set_control({"path": "decks/1/volume", "value": 0.75})
    assert result["accepted"] is True
    operation, payload = decode_frame(transport.sent[-1].data)
    assert operation == 1
    assert payload["group"] == "[Channel1]"
    assert payload["key"] == "volume"
    assert payload["value"] == 0.75


def test_feedback_is_cached_by_group_and_key():
    transport = MemoryMidiTransport()
    bridge = MixxxApiBridge(transport)
    transport.emit(
        MidiMessage.sysex(
            encode_frame(
                OP_FEEDBACK,
                {"group": "[Channel1]", "key": "volume", "value": 0.5},
            )
        )
    )
    assert bridge.state.controls["[Channel1]/volume"]["value"] == 0.5


def test_status_reports_transport_details():
    bridge = MixxxApiBridge(MemoryMidiTransport())
    status = bridge.status()
    assert status["midi"]["backend"] == "memory"
    assert status["bridge"]["connected"] is False


def test_set_control_can_wait_for_mapping_ack_or_time_out():
    bridge = MixxxApiBridge(MemoryMidiTransport())
    result = bridge.set_control({"path": "decks/1/volume", "value": 0.25, "wait_ms": 1})
    assert result["timed_out"] is True


def test_wait_until_connected_returns_after_ready_frame():
    transport = MemoryMidiTransport()
    bridge = MixxxApiBridge(transport)
    transport.emit(MidiMessage.sysex(encode_frame(OP_READY, {"mapping": "MixxxApiBridge"})))
    assert bridge.wait_until_connected(0) is True


def test_capabilities_exposes_remote_mapping_metadata():
    bridge = MixxxApiBridge(MemoryMidiTransport())
    bridge.handle_midi_message(
        MidiMessage.sysex(
            encode_frame(
                OP_CAPABILITIES,
                {"mapping": "MixxxApiBridge", "supports": ["set", "get"]},
            )
        )
    )
    assert bridge.capabilities()["remote_capabilities"]["mapping"] == "MixxxApiBridge"


def test_get_and_subscribe_reject_unknown_scale():
    bridge = MixxxApiBridge(MemoryMidiTransport())
    for method in (bridge.get_control, bridge.subscribe_control):
        try:
            method({"path": "decks/1/volume", "scale": "percent"})
        except ProtocolError as exc:
            assert "scale" in str(exc)
        else:  # pragma: no cover - assertion guard
            raise AssertionError("unknown scale was accepted")
