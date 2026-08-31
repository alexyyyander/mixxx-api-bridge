from types import SimpleNamespace

from mixxx_api_bridge.discovery import MixxxDiscovery


def test_windows_tasklist_detection(monkeypatch):
    result = SimpleNamespace(stdout='"Mixxx.exe","1234","Console","1","20,000 K"\n')
    monkeypatch.setattr("mixxx_api_bridge.discovery.os.name", "nt")
    monkeypatch.setattr("mixxx_api_bridge.discovery.subprocess.run", lambda *args, **kwargs: result)
    info = MixxxDiscovery().detect()
    assert info.running is True
    assert info.pid == 1234
    assert info.executable == "Mixxx.exe"
