import subprocess
import sys
from types import SimpleNamespace

import pytest

from mixxx_api_bridge.midi import MidoMidiTransport


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
