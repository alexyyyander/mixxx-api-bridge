import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from mixxx_api_bridge.discovery import MixxxDiscovery


@pytest.mark.skipif(os.name == "nt", reason="POSIX process listing fixture")
def test_detect_matches_app_binary_with_arguments(monkeypatch):
    result = SimpleNamespace(
        stdout=' 14014 /Users/alexyu/Desktop/Mixxx.app/Contents/MacOS/Mixxx --developer\n',
    )
    monkeypatch.setattr("mixxx_api_bridge.discovery.subprocess.run", lambda *args, **kwargs: result)
    monkeypatch.setattr(
        MixxxDiscovery,
        "_read_version",
        staticmethod(lambda _bundle: "2.5.6"),
    )
    info = MixxxDiscovery().detect()
    assert info.running is True
    assert info.pid == 14014
    assert info.version == "2.5.6"
    assert info.bundle_path == "/Users/alexyu/Desktop/Mixxx.app"


def test_detect_ignores_unrelated_process(monkeypatch):
    result = SimpleNamespace(stdout=" 77 /usr/local/bin/mixxx-helper\n")
    monkeypatch.setattr("mixxx_api_bridge.discovery.subprocess.run", lambda *args, **kwargs: result)
    assert MixxxDiscovery().detect().running is False
