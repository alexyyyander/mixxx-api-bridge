"""A source-compatible HTTP/MIDI sidecar for Mixxx."""

from .bridge import MixxxApiBridge
from .config import BridgeConfig
from .midi import (
    CoreMidiProcessTransport,
    MemoryMidiTransport,
    MidiMessage,
    MidiTransport,
    MidoMidiTransport,
)
from .protocol import ControlAddress, ControlCommand

__all__ = [
    "ControlAddress",
    "ControlCommand",
    "CoreMidiProcessTransport",
    "BridgeConfig",
    "MemoryMidiTransport",
    "MidiMessage",
    "MidiTransport",
    "MidoMidiTransport",
    "MixxxApiBridge",
]

__version__ = "0.1.0"
