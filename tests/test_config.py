from mixxx_api_bridge.config import BridgeConfig


def test_config_reads_environment(monkeypatch):
    monkeypatch.setenv("MIXXX_API_HOST", "127.0.0.2")
    monkeypatch.setenv("MIXXX_API_PORT", "12000")
    monkeypatch.setenv("MIXXX_MIDI_OUTPUT", "Mixxx API Out")
    monkeypatch.setenv("MIXXX_MIDI_INPUT", "Mixxx API In")
    config = BridgeConfig.from_env()
    assert config.host == "127.0.0.2"
    assert config.port == 12000
    assert config.midi_output == "Mixxx API Out"
    assert config.midi_input == "Mixxx API In"
