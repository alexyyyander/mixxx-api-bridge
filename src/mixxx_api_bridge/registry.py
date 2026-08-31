"""Semantic aliases for frequently used Mixxx controls."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .protocol import ControlAddress, ProtocolError


@dataclass(frozen=True)
class ControlSpec:
    alias: str
    address: ControlAddress
    description: str
    writable: bool = True
    value_scale: str = "normalized"


_PARAMETER_RE = re.compile(r"^(?:parameter|button_parameter)([1-9][0-9]*)$")


class ControlRegistry:
    """Resolve friendly API paths into stable Mixxx group/key addresses.

    The raw ``group`` + ``key`` form remains available for controls that are
    not listed here. Effect parameters are intentionally index based because
    their meaning depends on the currently loaded effect.
    """

    def resolve(self, payload: dict[str, Any]) -> tuple[ControlAddress, str]:
        group = payload.get("group")
        key = payload.get("key")
        if group is not None or key is not None:
            if not isinstance(group, str) or not isinstance(key, str):
                raise ProtocolError("group and key must both be strings")
            return ControlAddress(group, key), str(payload.get("scale", "normalized"))

        alias = payload.get("path")
        if not isinstance(alias, str):
            raise ProtocolError("provide either path or group + key")
        return self.resolve_alias(alias), str(payload.get("scale", "normalized"))

    def resolve_alias(self, alias: str) -> ControlAddress:
        parts = [part for part in alias.strip("/").split("/") if part]
        if parts[:1] == ["mixer"] and parts[1:] == ["crossfader"]:
            return ControlAddress("[Master]", "crossfader")
        if len(parts) == 3 and parts[0] == "decks":
            deck = self._positive_int(parts[1], "deck")
            key = parts[2]
            if key not in {"volume", "gain", "pregain", "play", "play_indicator", "rate"}:
                raise ProtocolError(f"unsupported deck control: {key}")
            return ControlAddress(f"[Channel{deck}]", key)
        if len(parts) == 4 and parts[:2] == ["fx", "units"]:
            unit = self._positive_int(parts[2], "unit")
            if parts[3] not in {"mix", "super1", "enabled"}:
                raise ProtocolError(f"unsupported FX unit control: {parts[3]}")
            return ControlAddress(f"[EffectRack1_EffectUnit{unit}]", parts[3])
        if len(parts) == 6 and parts[:2] == ["fx", "units"] and parts[3] == "slots":
            unit = self._positive_int(parts[2], "unit")
            slot = self._positive_int(parts[4], "slot")
            parameter = parts[5]
            if parameter in {"enabled", "loaded", "clear", "next_effect", "prev_effect"}:
                return ControlAddress(
                    f"[EffectRack1_EffectUnit{unit}_Effect{slot}]",
                    parameter,
                )
            match = _PARAMETER_RE.fullmatch(parameter)
            if match:
                return ControlAddress(
                    f"[EffectRack1_EffectUnit{unit}_Effect{slot}]",
                    parameter,
                )
            raise ProtocolError(
                "effect parameters must use parameterN or button_parameterN "
                "until effect metadata is available"
            )
        raise ProtocolError(f"unknown control alias: {alias}")

    def capabilities(self) -> dict[str, Any]:
        return {
            "aliases": [
                {
                    "path": "decks/{deck}/volume",
                    "address": "[ChannelN]/volume",
                    "description": "Deck channel volume",
                    "scale": "normalized",
                },
                {
                    "path": "decks/{deck}/gain",
                    "address": "[ChannelN]/gain",
                    "description": "Deck pregain",
                    "scale": "normalized",
                },
                {
                    "path": "decks/{deck}/play",
                    "address": "[ChannelN]/play",
                    "description": "Deck play/pause state",
                    "scale": "normalized",
                },
                {
                    "path": "mixer/crossfader",
                    "address": "[Master]/crossfader",
                    "description": "Master crossfader",
                    "scale": "normalized",
                },
                {
                    "path": "fx/units/{unit}/mix",
                    "address": "[EffectRack1_EffectUnitN]/mix",
                    "description": "Effect unit dry/wet mix",
                    "scale": "normalized",
                },
                {
                    "path": "fx/units/{unit}/slots/{slot}/parameterN",
                    "address": "[EffectRack1_EffectUnitN_EffectM]/parameterK",
                    "description": "Indexed effect parameter",
                    "scale": "normalized",
                },
            ],
            "raw_control": {
                "description": "Pass a Mixxx group and key directly",
                "scale": ["normalized", "raw"],
            },
        }

    @staticmethod
    def _positive_int(value: str, name: str) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ProtocolError(f"{name} must be a positive integer") from exc
        if parsed < 1 or parsed > 99:
            raise ProtocolError(f"{name} must be between 1 and 99")
        return parsed
