"""A source-compatible HTTP/MIDI sidecar for Mixxx."""

from .bridge import MixxxApiBridge
from .config import BridgeConfig
from .midi import MemoryMidiTransport, MidiMessage, MidiTransport, MidoMidiTransport
from .protocol import ControlAddress, ControlCommand

__all__ = [
    "ControlAddress",
    "ControlCommand",
    "BridgeConfig",
    "MemoryMidiTransport",
    "MidiMessage",
    "MidiTransport",
    "MidoMidiTransport",
    "MixxxApiBridge",
]

__version__ = "0.1.0"
