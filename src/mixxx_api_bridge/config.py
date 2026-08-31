"""Environment and command-line independent bridge configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class BridgeConfig:
    host: str = "127.0.0.1"
    port: int = 11120
    midi_output: str | None = None
    midi_input: str | None = None
    auth_token: str | None = None

    @classmethod
    def from_env(cls) -> "BridgeConfig":
        return cls(
            host=os.getenv("MIXXX_API_HOST", cls.host),
            port=_integer_env("MIXXX_API_PORT", cls.port),
            midi_output=os.getenv("MIXXX_MIDI_OUTPUT") or None,
            midi_input=os.getenv("MIXXX_MIDI_INPUT") or None,
            auth_token=os.getenv("MIXXX_API_TOKEN") or None,
        )


def _integer_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not 1 <= value <= 65535:
        raise ValueError(f"{name} must be between 1 and 65535")
    return value
