import pytest

from mixxx_api_bridge.protocol import ProtocolError
from mixxx_api_bridge.registry import ControlRegistry


def test_deck_alias():
    address = ControlRegistry().resolve_alias("decks/2/volume")
    assert address.group == "[Channel2]"
    assert address.key == "volume"


def test_effect_parameter_alias():
    address = ControlRegistry().resolve_alias("fx/units/1/slots/2/parameter3")
    assert address.group == "[EffectRack1_EffectUnit1_Effect2]"
    assert address.key == "parameter3"


def test_generic_deck_and_component_paths_reach_new_mixxx_controls():
    registry = ControlRegistry()
    assert registry.resolve_alias("decks/2/eq_low").identifier == "[Channel2]/eq_low"
    assert registry.resolve_alias("channels/2/eq_low").identifier == "[Channel2]/eq_low"
    assert registry.resolve_alias("samplers/3/hotcue_1_activate").identifier == "[Sampler3]/hotcue_1_activate"
    assert registry.resolve_alias("auxiliaries/1/volume").identifier == "[Auxiliary1]/volume"
    assert registry.resolve_alias("mixer/headGain").identifier == "[Master]/headGain"
    assert registry.resolve_alias("playlist/next").identifier == "[Playlist]/next"
    assert registry.resolve_alias("equalizers/1/parameter1").identifier == "[EqualizerRack1_[Channel1]]/parameter1"
    assert registry.resolve_alias("quick_effects/2/enabled").identifier == "[QuickEffectRack1_[Channel2]]/enabled"


def test_generic_path_rejects_embedded_separator():
    with pytest.raises(ProtocolError, match="unknown control alias"):
        ControlRegistry().resolve_alias("decks/1/eq/low")


def test_raw_control_is_supported():
    address, scale = ControlRegistry().resolve(
        {"group": "[Master]", "key": "crossfader", "scale": "normalized"}
    )
    assert address.identifier == "[Master]/crossfader"
    assert scale == "normalized"


def test_dynamic_effect_parameter_name_is_passed_through():
    address = ControlRegistry().resolve_alias("fx/units/1/slots/1/feedback")
    assert address.identifier == "[EffectRack1_EffectUnit1_Effect1]/feedback"
