import subprocess
import sys
from types import SimpleNamespace

from mixxx_api_bridge.midi import MidoMidiTransport


def test_available_ports_parses_isolated_probe(monkeypatch):
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
