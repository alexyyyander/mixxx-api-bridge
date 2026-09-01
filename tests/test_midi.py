import subprocess
import sys
import threading
from types import SimpleNamespace

import pytest

from mixxx_api_bridge.midi import CoreMidiProcessTransport, MidoMidiTransport
from mixxx_api_bridge.protocol import OP_HELLO, encode_frame


def test_available_ports_parses_isolated_probe(monkeypatch):
    monkeypatch.setenv("MIXXX_API_BRIDGE_ENABLE_NATIVE_MIDI", "1")
    monkeypatch.setitem(sys.modules, "mido", object())
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout='{"inputs": ["in"], "outputs": ["out"], "backend": "test"}',
            stderr="",
        ),
    )

    assert MidoMidiTransport.available_ports() == {
        "inputs": ["in"],
        "outputs": ["out"],
        "backend": "test",
    }


def test_available_ports_reports_native_probe_abort(monkeypatch):
    monkeypatch.setenv("MIXXX_API_BRIDGE_ENABLE_NATIVE_MIDI", "1")
    monkeypatch.setitem(sys.modules, "mido", object())
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=-6,
            stdout="",
            stderr="Abort trap: 6",
        ),
    )

    result = MidoMidiTransport.available_ports()
    assert result["backend"] == "error"
    assert "Abort trap: 6" in result["error"]


def test_macos_native_probe_is_opt_in(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.delenv("MIXXX_API_BRIDGE_ENABLE_NATIVE_MIDI", raising=False)

    result = MidoMidiTransport.available_ports()

    assert result["backend"] == "disabled"
    assert "MIXXX_API_BRIDGE_ENABLE_NATIVE_MIDI=1" in result["error"]


def test_macos_native_transport_is_opt_in(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.delenv("MIXXX_API_BRIDGE_ENABLE_NATIVE_MIDI", raising=False)

    with pytest.raises(RuntimeError, match="Native CoreMIDI access is disabled"):
        MidoMidiTransport("any output")


def test_coremidi_process_transport_round_trip(tmp_path):
    helper = tmp_path / "helper.py"
    helper.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "print('READY test-in test-out', flush=True)\n"
        "for line in sys.stdin:\n"
        "    if line.startswith('QUIT'):\n"
        "        break\n"
        "    if line.startswith('SEND '):\n"
        "        print('RECV ' + line[5:].strip(), flush=True)\n",
        encoding="utf-8",
    )
    helper.chmod(0o755)
    received = []
    event = threading.Event()
    transport = CoreMidiProcessTransport(
        str(helper),
        "test-in",
        "test-out",
        on_message=lambda message: (received.append(message), event.set()),
    )
    try:
        frame = encode_frame(OP_HELLO, {"request_id": "round-trip"})
        transport.send_sysex(frame)
        assert event.wait(2)
        assert received[0].data == tuple(frame)
        assert transport.describe()["backend"] == "coremidi-c"
    finally:
        transport.close()
