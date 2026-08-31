"""Small standard-library HTTP server for the local sidecar."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from .bridge import MixxxApiBridge
from .protocol import ProtocolError


class _ApiHandler(BaseHTTPRequestHandler):
    bridge: MixxxApiBridge
    auth_token: str | None = None
    server_version = "MixxxApiBridge/0.1"

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if not self._authorized():
            return
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self._write_json(HTTPStatus.OK, {"ok": True, **self.bridge.status()})
            return
        if parsed.path == "/api/status":
            self._write_json(HTTPStatus.OK, self.bridge.status())
            return
        if parsed.path == "/api/capabilities":
            self._write_json(HTTPStatus.OK, self.bridge.capabilities())
            return
        if parsed.path == "/api/control":
            query = parse_qs(parsed.query)
            payload = {key: values[-1] for key, values in query.items() if values}
            try:
                result = self.bridge.get_control(payload)
            except ProtocolError as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            self._write_json(HTTPStatus.ACCEPTED, result)
            return
        self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if not self._authorized():
            return
        payload = self._read_json()
        if payload is None:
            return
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/control":
                result = self.bridge.set_control(payload)
            elif parsed.path == "/api/subscribe":
                result = self.bridge.subscribe_control(payload)
            elif parsed.path == "/api/handshake":
                result = {"accepted": True, "request_id": self.bridge.send_hello()}
            else:
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})
                return
        except (ProtocolError, RuntimeError) as exc:
            self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return
        self._write_json(HTTPStatus.ACCEPTED, result)

    def do_OPTIONS(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if not self._authorized():
            return
        self.send_response(HTTPStatus.NO_CONTENT.value)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        # Keep the CLI quiet by default; callers can use --verbose later.
        return

    def _authorized(self) -> bool:
        if not self.auth_token:
            return True
        expected = f"Bearer {self.auth_token}"
        if self.headers.get("Authorization") == expected:
            return True
        self._write_json(HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "missing or invalid bearer token"})
        return False

    def _read_json(self) -> dict[str, Any] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid Content-Length"})
            return None
        if length > 1_000_000:
            self._write_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"ok": False, "error": "payload too large"})
            return None
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"invalid JSON: {exc}"})
            return None
        if not isinstance(data, dict):
            self._write_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "JSON body must be an object"})
            return None
        return data

    def _write_json(self, status: HTTPStatus, data: dict[str, Any]) -> None:
        encoded = json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(encoded)


class ApiServer(ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], bridge: MixxxApiBridge, auth_token: str | None = None):
        handler = type(
            "MixxxApiHandler",
            (_ApiHandler,),
            {"bridge": bridge, "auth_token": auth_token},
        )
        super().__init__(address, handler)


def serve(
    bridge: MixxxApiBridge,
    host: str = "127.0.0.1",
    port: int = 11120,
    auth_token: str | None = None,
) -> None:
    server = ApiServer((host, port), bridge, auth_token)
    try:
        server.serve_forever()
    finally:
        server.server_close()
