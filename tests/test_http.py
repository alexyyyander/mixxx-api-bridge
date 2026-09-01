import json
import threading
from http.client import HTTPConnection

import pytest

from mixxx_api_bridge.bridge import MixxxApiBridge
from mixxx_api_bridge.http_server import ApiServer
from mixxx_api_bridge.midi import MemoryMidiTransport


def test_health_and_control_endpoints():
    bridge = MixxxApiBridge(MemoryMidiTransport())
    try:
        server = ApiServer(("127.0.0.1", 0), bridge)
    except PermissionError:
        # Some managed runners disallow binding even to an ephemeral loopback
        # port. The endpoint itself is exercised in normal developer/CI runs.
        pytest.skip("environment disallows local socket binding")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        connection = HTTPConnection("127.0.0.1", port, timeout=2)
        connection.request("GET", "/api/health")
        response = connection.getresponse()
        assert response.status == 200
        assert json.loads(response.read())["ok"] is True

        body = json.dumps({"path": "decks/1/volume", "value": 0.4})
        connection.request(
            "POST",
            "/api/control",
            body=body,
            headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        assert response.status == 202
        assert json.loads(response.read())["group"] == "[Channel1]"

        body = json.dumps({"action": "toggle", "path": "decks/1/play"})
        connection.request(
            "POST",
            "/api/action",
            body=body,
            headers={"Content-Type": "application/json"},
        )
        response = connection.getresponse()
        assert response.status == 202
        assert json.loads(response.read())["action"] == "toggle"
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
