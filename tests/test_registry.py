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


def test_raw_control_is_supported():
    address, scale = ControlRegistry().resolve(
        {"group": "[Master]", "key": "crossfader", "scale": "normalized"}
    )
    assert address.identifier == "[Master]/crossfader"
    assert scale == "normalized"


def test_unknown_effect_parameter_name_has_explicit_error():
    with pytest.raises(ProtocolError, match="parameterN"):
        ControlRegistry().resolve_alias("fx/units/1/slots/1/feedback")
