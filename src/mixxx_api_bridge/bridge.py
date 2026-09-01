"""Core bridge state and request handling."""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Any, Callable

from .discovery import MixxxDiscovery, MixxxProcessInfo
from .midi import MidiMessage, MidiTransport
from .protocol import (
    OP_ACK,
    OP_ACTION,
    OP_CAPABILITIES,
    OP_COMMAND,
    OP_FEEDBACK,
    OP_GET,
    OP_HELLO,
    OP_ERROR,
    OP_READY,
    OP_SETTING_GET,
    OP_SETTING_VALUE,
    OP_SUBSCRIBE,
    ControlAddress,
    ControlCommand,
    ProtocolError,
    decode_frame,
    encode_frame,
    new_request_id,
)
from .registry import ControlRegistry


@dataclass
class BridgeState:
    connected: bool = False
    last_ready_at: float | None = None
    mapping: dict[str, Any] = field(default_factory=dict)
    remote_capabilities: dict[str, Any] = field(default_factory=dict)
    controls: dict[str, dict[str, Any]] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=dict)
    setting_responses: dict[str, dict[str, Any]] = field(default_factory=dict)
    acknowledgements: dict[str, dict[str, Any]] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)


class MixxxApiBridge:
    """Translate JSON commands to the Mixxx API Mapping's SysEx protocol."""

    def __init__(
        self,
        transport: MidiTransport,
        discovery: MixxxDiscovery | None = None,
        registry: ControlRegistry | None = None,
    ) -> None:
        self.transport = transport
        self.discovery = discovery or MixxxDiscovery()
        self.registry = registry or ControlRegistry()
        self.state = BridgeState()
        self._response_condition = threading.Condition()
        self._listeners: list[Callable[[dict[str, Any]], None]] = []
        if hasattr(transport, "on_message"):
            transport.on_message = self.handle_midi_message  # type: ignore[attr-defined]

    def start(self) -> None:
        self.send_hello()

    def close(self) -> None:
        self.transport.close()

    def add_event_listener(self, listener: Callable[[dict[str, Any]], None]) -> None:
        self._listeners.append(listener)

    def send_hello(self) -> str:
        request_id = new_request_id()
        self.transport.send_sysex(
            encode_frame(
                OP_HELLO,
                {
                    "request_id": request_id,
                    "client": "mixxx-api-bridge",
                    "protocol": 1,
                },
            )
        )
        return request_id

    def request_capabilities(self) -> str:
        request_id = new_request_id()
        self.transport.send_sysex(
            encode_frame(
                OP_CAPABILITIES,
                {"request_id": request_id, "protocol": 1},
            )
        )
        return request_id

    def set_control(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._validate_wait_ms(payload.get("wait_ms"))
        address, scale = self.registry.resolve(payload)
        value = self._coerce_value(payload.get("value"), scale)
        command = ControlCommand(
            address=address,
            value=value,
            scale=scale,
            request_id=str(payload.get("request_id") or new_request_id()),
        )
        self.transport.send_sysex(encode_frame(OP_COMMAND, command.payload()))
        result = {
            "accepted": True,
            "request_id": command.id,
            "group": address.group,
            "key": address.key,
            "value": value,
            "scale": scale,
            "connected": self.state.connected,
        }
        response = self._wait_for_response(command.id, payload.get("wait_ms"))
        if response:
            result.update(response)
        return result

    def get_control(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._validate_wait_ms(payload.get("wait_ms"))
        address, scale = self.registry.resolve(payload)
        self._validate_scale(scale)
        request_id = str(payload.get("request_id") or new_request_id())
        self.transport.send_sysex(
            encode_frame(
                OP_GET,
                {
                    "request_id": request_id,
                    "group": address.group,
                    "key": address.key,
                    "scale": scale,
                },
            )
        )
        cached = self.state.controls.get(address.identifier)
        result = {
            "accepted": True,
            "request_id": request_id,
            "group": address.group,
            "key": address.key,
            "cached": cached,
        }
        response = self._wait_for_response(request_id, payload.get("wait_ms"))
        if response:
            result.update(response)
        return result

    def subscribe_control(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._validate_wait_ms(payload.get("wait_ms"))
        address, scale = self.registry.resolve(payload)
        self._validate_scale(scale)
        request_id = str(payload.get("request_id") or new_request_id())
        self.transport.send_sysex(
            encode_frame(
                OP_SUBSCRIBE,
                {
                    "request_id": request_id,
                    "group": address.group,
                    "key": address.key,
                    "scale": scale,
                },
            )
        )
        result = {
            "accepted": True,
            "request_id": request_id,
            "group": address.group,
            "key": address.key,
            "scale": scale,
        }
        response = self._wait_for_response(request_id, payload.get("wait_ms"))
        if response:
            result.update(response)
        return result

    def action_control(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Run a Mixxx momentary, toggle, or reset action on a control."""

        self._validate_wait_ms(payload.get("wait_ms"))
        action = payload.get("action")
        if action not in {"trigger", "toggle", "reset"}:
            raise ProtocolError("action must be 'trigger', 'toggle', or 'reset'")
        address, scale = self.registry.resolve(payload)
        self._validate_scale(scale)
        request_id = str(payload.get("request_id") or new_request_id())
        self.transport.send_sysex(
            encode_frame(
                OP_ACTION,
                {
                    "request_id": request_id,
                    "action": action,
                    "group": address.group,
                    "key": address.key,
                    "scale": scale,
                },
            )
        )
        result = {
            "accepted": True,
            "request_id": request_id,
            "action": action,
            "group": address.group,
            "key": address.key,
            "scale": scale,
            "connected": self.state.connected,
        }
        response = self._wait_for_response(request_id, payload.get("wait_ms"))
        if response:
            result.update(response)
        return result

    def get_setting(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Read a setting declared by the active controller mapping.

        Mixxx exposes ``engine.getSetting`` to mappings, but not a supported
        generic ``setSetting`` API. This endpoint is therefore intentionally
        read-only and does not pretend to change global Mixxx preferences.
        """

        self._validate_wait_ms(payload.get("wait_ms"))
        name = payload.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ProtocolError("setting name must be a non-empty string")
        request_id = str(payload.get("request_id") or new_request_id())
        self.transport.send_sysex(
            encode_frame(
                OP_SETTING_GET,
                {"request_id": request_id, "name": name},
            )
        )
        result = {
            "accepted": True,
            "request_id": request_id,
            "name": name,
            "cached": self.state.settings.get(name),
        }
        response = self._wait_for_response(request_id, payload.get("wait_ms"))
        if response:
            result.update(response)
        return result

    def status(self) -> dict[str, Any]:
        process = self.discovery.detect()
        if not process.running:
            # A previous READY frame must not make a stopped Mixxx instance
            # appear connected forever.
            self.state.connected = False
        return {
            "bridge": {
                "version": "0.1.0",
                "transport": getattr(self.transport, "name", type(self.transport).__name__),
                "connected": self.state.connected,
                "last_ready_at": self.state.last_ready_at,
            },
            "midi": self.transport.describe()
            if hasattr(self.transport, "describe")
            else {"name": getattr(self.transport, "name", type(self.transport).__name__)},
            "mixxx": process.as_dict(),
            "mapping": self.state.mapping,
            "remote_capabilities": self.state.remote_capabilities,
            "settings": dict(self.state.settings),
            "errors": list(self.state.errors[-10:]),
        }

    def capabilities(self) -> dict[str, Any]:
        result = self.registry.capabilities()
        result["protocol"] = {
            "transport": "midi-sysex",
            "version": 1,
            "operations": {
                "hello": OP_HELLO,
                "command": OP_COMMAND,
                "action": OP_ACTION,
                "feedback": OP_FEEDBACK,
                "capabilities": OP_CAPABILITIES,
                "get": OP_GET,
                "subscribe": OP_SUBSCRIBE,
                "setting_get": OP_SETTING_GET,
                "ready": OP_READY,
                "ack": OP_ACK,
                "setting_value": OP_SETTING_VALUE,
            },
        }
        result["remote_capabilities"] = dict(self.state.remote_capabilities)
        return result

    def handle_midi_message(self, message: MidiMessage) -> None:
        if message.kind != "sysex":
            return
        try:
            operation, payload = decode_frame(message.data)
        except ProtocolError as exc:
            self._record_error("protocol", str(exc))
            return

        if operation == OP_READY:
            self.state.connected = True
            self.state.last_ready_at = time.time()
            self.state.mapping = dict(payload)
            # Query the mapping after every READY so the HTTP capabilities
            # endpoint reflects the actual loaded script, not only local
            # aliases. This is safe for older mappings: an unsupported
            # operation is returned as an ordinary protocol error.
            try:
                self.request_capabilities()
            except RuntimeError as exc:
                self._record_error("transport", str(exc))
            with self._response_condition:
                self._response_condition.notify_all()
            self._emit({"type": "ready", **payload})
        elif operation == OP_ACK:
            request_id = str(payload.get("request_id") or "")
            if request_id:
                self.state.acknowledgements[request_id] = dict(payload)
            with self._response_condition:
                self._response_condition.notify_all()
            self._emit({"type": "ack", **payload})
        elif operation == OP_FEEDBACK:
            self._record_control(payload)
            with self._response_condition:
                self._response_condition.notify_all()
            self._emit({"type": "feedback", **payload})
        elif operation == OP_CAPABILITIES:
            self.state.remote_capabilities = dict(payload)
            self._emit({"type": "capabilities", **payload})
        elif operation == OP_SETTING_VALUE:
            request_id = str(payload.get("request_id") or "")
            name = payload.get("name")
            if isinstance(name, str):
                self.state.settings[name] = payload.get("value")
            if request_id:
                self.state.setting_responses[request_id] = dict(payload)
            with self._response_condition:
                self._response_condition.notify_all()
            self._emit({"type": "setting", **payload})
        elif operation == OP_ERROR:
            self._record_error("remote", str(payload.get("error", "unknown error")), payload)
            with self._response_condition:
                self._response_condition.notify_all()
            self._emit({"type": "error", **payload})
        else:
            self._record_error("remote", f"unknown operation {operation}", payload)

    def _record_control(self, payload: dict[str, Any]) -> None:
        group = payload.get("group")
        key = payload.get("key")
        if isinstance(group, str) and isinstance(key, str):
            self.state.controls[f"{group}/{key}"] = dict(payload)

    def _record_error(self, category: str, message: str, payload: dict[str, Any] | None = None) -> None:
        self.state.errors.append(
            {
                "category": category,
                "message": message,
                "payload": payload or {},
                "at": time.time(),
            }
        )

    def _emit(self, event: dict[str, Any]) -> None:
        for listener in list(self._listeners):
            try:
                listener(event)
            except Exception:
                # A status/event observer must never break the MIDI callback.
                continue

    def _wait_for_response(self, request_id: str, wait_ms: Any) -> dict[str, Any] | None:
        """Optionally wait for an ACK/feedback frame from the mapping."""

        if wait_ms in (None, 0, "0"):
            return None
        timeout_ms = self._validate_wait_ms(wait_ms)
        deadline = time.monotonic() + timeout_ms / 1000.0
        with self._response_condition:
            while True:
                ack = self.state.acknowledgements.get(request_id)
                setting = self.state.setting_responses.get(request_id)
                feedback = next(
                    (
                        item
                        for item in self.state.controls.values()
                        if item.get("request_id") == request_id
                    ),
                    None,
                )
                if ack is not None or feedback is not None:
                    return {"ack": ack, "feedback": feedback}
                if setting is not None:
                    return {"setting": setting}
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return {"ack": None, "feedback": None, "timed_out": True}
                self._response_condition.wait(timeout=remaining)

    def wait_until_connected(self, timeout_ms: int = 1000) -> bool:
        """Wait for a READY frame after a hello was sent."""

        if timeout_ms < 0 or timeout_ms > 10000:
            raise ProtocolError("timeout_ms must be between 0 and 10000")
        deadline = time.monotonic() + timeout_ms / 1000.0
        with self._response_condition:
            while not self.state.connected:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._response_condition.wait(timeout=remaining)
            return True

    @staticmethod
    def _validate_wait_ms(wait_ms: Any) -> int:
        if wait_ms in (None, 0, "0"):
            return 0
        try:
            timeout_ms = int(wait_ms)
        except (TypeError, ValueError) as exc:
            raise ProtocolError("wait_ms must be an integer") from exc
        if timeout_ms < 0 or timeout_ms > 5000:
            raise ProtocolError("wait_ms must be between 0 and 5000")
        return timeout_ms

    @staticmethod
    def _coerce_value(value: Any, scale: str) -> float:
        MixxxApiBridge._validate_scale(scale)
        if isinstance(value, bool):
            value = 1.0 if value else 0.0
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise ProtocolError("value must be a number or boolean") from exc
        if scale == "normalized":
            if not 0.0 <= numeric <= 1.0:
                raise ProtocolError("normalized value must be between 0 and 1")
        return numeric

    @staticmethod
    def _validate_scale(scale: str) -> None:
        if scale not in {"normalized", "raw"}:
            raise ProtocolError("scale must be 'normalized' or 'raw'")
