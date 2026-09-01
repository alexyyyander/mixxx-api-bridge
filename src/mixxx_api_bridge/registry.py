"""Semantic aliases for frequently used Mixxx controls."""

from __future__ import annotations

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
        if len(parts) == 3 and parts[0] in {"decks", "channels"}:
            deck = self._positive_int(parts[1], "deck")
            return ControlAddress(f"[Channel{deck}]", self._control_key(parts[2]))
        if len(parts) == 3 and parts[0] in {"preview_decks", "preview-decks"}:
            deck = self._positive_int(parts[1], "preview deck")
            return ControlAddress(f"[PreviewDeck{deck}]", self._control_key(parts[2]))
        if len(parts) == 3 and parts[0] == "samplers":
            sampler = self._positive_int(parts[1], "sampler")
            return ControlAddress(f"[Sampler{sampler}]", self._control_key(parts[2]))
        if len(parts) == 2 and parts[0] == "samplers":
            return ControlAddress("[Samplers]", self._control_key(parts[1]))
        if len(parts) == 3 and parts[0] in {"equalizers", "eq"}:
            deck = self._positive_int(parts[1], "deck")
            return ControlAddress(
                f"[EqualizerRack1_[Channel{deck}]]", self._control_key(parts[2])
            )
        if len(parts) == 3 and parts[0] in {"quick_effects", "quick-effects", "quickfx"}:
            deck = self._positive_int(parts[1], "deck")
            return ControlAddress(
                f"[QuickEffectRack1_[Channel{deck}]]", self._control_key(parts[2])
            )
        if len(parts) == 2 and parts[0] in {"effect_rack", "effect-rack"}:
            return ControlAddress("[EffectRack1]", self._control_key(parts[1]))
        if len(parts) == 2 and parts[0] in {"equalizer_rack", "equalizer-rack"}:
            return ControlAddress("[EqualizerRack1]", self._control_key(parts[1]))
        if len(parts) == 2 and parts[0] in {
            "mixer",
            "master",
            "main",
            "app",
            "recording",
            "library",
            "playlist",
            "autodj",
            "vinyl",
            "vinyl_control",
            "skin",
        }:
            group = {
                "mixer": "[Master]",
                "master": "[Master]",
                "main": "[Main]",
                "app": "[App]",
                "recording": "[Recording]",
                "library": "[Library]",
                "playlist": "[Playlist]",
                "autodj": "[AutoDJ]",
                "vinyl": "[VinylControl]",
                "vinyl_control": "[VinylControl]",
                "skin": "[Skin]",
            }[parts[0]]
            return ControlAddress(group, self._control_key(parts[1]))
        if len(parts) == 3 and parts[0] in {"microphones", "mics"}:
            microphone = self._positive_int(parts[1], "microphone")
            group = "[Microphone]" if microphone == 1 else f"[Microphone{microphone}]"
            return ControlAddress(group, self._control_key(parts[2]))
        if len(parts) == 3 and parts[0] in {"auxiliaries", "aux"}:
            auxiliary = self._positive_int(parts[1], "auxiliary")
            return ControlAddress(f"[Auxiliary{auxiliary}]", self._control_key(parts[2]))
        if len(parts) == 4 and parts[:2] == ["fx", "units"]:
            unit = self._positive_int(parts[2], "unit")
            return ControlAddress(
                f"[EffectRack1_EffectUnit{unit}]", self._control_key(parts[3])
            )
        if len(parts) == 6 and parts[:2] == ["fx", "units"] and parts[3] == "slots":
            unit = self._positive_int(parts[2], "unit")
            slot = self._positive_int(parts[4], "slot")
            return ControlAddress(
                f"[EffectRack1_EffectUnit{unit}_Effect{slot}]",
                self._control_key(parts[5]),
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
                    "path": "decks/{deck}/pregain",
                    "address": "[ChannelN]/pregain",
                    "description": "Deck pregain (explicit name)",
                    "scale": "normalized",
                },
                {
                    "path": "decks/{deck}/play",
                    "address": "[ChannelN]/play",
                    "description": "Deck play/pause state",
                    "scale": "normalized",
                },
                {
                    "path": "decks/{deck}/play_indicator",
                    "address": "[ChannelN]/play_indicator",
                    "description": "Deck play indicator (read-only)",
                    "scale": "normalized",
                    "writable": False,
                },
                {
                    "path": "decks/{deck}/rate",
                    "address": "[ChannelN]/rate",
                    "description": "Deck tempo/pitch rate",
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
                    "path": "fx/units/{unit}/super1",
                    "address": "[EffectRack1_EffectUnitN]/super1",
                    "description": "Effect unit super knob",
                    "scale": "normalized",
                },
                {
                    "path": "fx/units/{unit}/enabled",
                    "address": "[EffectRack1_EffectUnitN]/enabled",
                    "description": "Effect unit enabled state",
                    "scale": "normalized",
                },
                {
                    "path": "fx/units/{unit}/slots/{slot}/parameterN",
                    "address": "[EffectRack1_EffectUnitN_EffectM]/parameterK",
                    "description": "Indexed effect parameter",
                    "scale": "normalized",
                },
                {
                    "path": "fx/units/{unit}/slots/{slot}/enabled|loaded|clear|next_effect|prev_effect",
                    "address": "[EffectRack1_EffectUnitN_EffectM]/<key>",
                    "description": "Effect slot state/action (use /api/action for momentary keys)",
                    "scale": "normalized",
                },
            ],
            "raw_control": {
                "description": "Pass a Mixxx group and key directly",
                "scale": ["normalized", "raw"],
            },
            "generic_paths": [
                "decks/{deck}/{key}",
                "channels/{channel}/{key}",
                "preview_decks/{deck}/{key}",
                "samplers/{sampler}/{key}",
                "samplers/{key}",
                "equalizers/{deck}/{key}",
                "quick_effects/{deck}/{key}",
                "effect_rack/{key}",
                "equalizer_rack/{key}",
                "mixer/{key}",
                "master/{key}",
                "main/{key}",
                "app/{key}",
                "recording/{key}",
                "library/{key}",
                "playlist/{key}",
                "autodj/{key}",
                "microphones/{microphone}/{key}",
                "auxiliaries/{auxiliary}/{key}",
                "fx/units/{unit}/{key}",
                "fx/units/{unit}/slots/{slot}/{key}",
            ],
            "actions": {
                "trigger": "Momentary controls via script.triggerControl",
                "toggle": "Binary controls via script.toggleControl",
                "reset": "Restore a control's default via engine.reset",
            },
            "settings": {
                "read": "Read mapping settings via engine.getSetting",
                "declared": ["triggerDelayMs"],
                "write": False,
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

    @staticmethod
    def _control_key(value: str) -> str:
        """Validate a path component without guessing Mixxx's full key list.

        Mixxx adds controls over time and many keys are dynamic (hotcue,
        beatloop, effect parameters). Restricting only path separators and
        control characters lets the raw group/key API reach new controls while
        still preventing malformed protocol addresses.
        """

        if not isinstance(value, str) or not value or "/" in value:
            raise ProtocolError("control key must be a non-empty path component")
        if any(ord(char) < 0x20 or ord(char) >= 0x7F for char in value):
            raise ProtocolError("control key must contain printable ASCII characters")
        return value
