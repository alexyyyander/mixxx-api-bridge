"""MIDI transport abstractions.

The optional Mido backend talks to real or virtual MIDI ports. Tests can use
``MemoryMidiTransport`` without installing any MIDI dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import queue
import subprocess
import sys
import threading
from typing import Any, Callable, Protocol


_NATIVE_MIDI_ENV = "MIXXX_API_BRIDGE_ENABLE_NATIVE_MIDI"


def _native_midi_enabled() -> bool:
    """Return whether this process explicitly opted into native MIDI access.

    On macOS, python-rtmidi can terminate the interpreter when CoreMIDI
    rejects a client (notably from a sandboxed host).  Keep that native path
    opt-in so a status check cannot create a system crash dialog by surprise.
    Other platforms retain the historical default behavior.
    """

    return sys.platform != "darwin" or os.getenv(_NATIVE_MIDI_ENV) == "1"


@dataclass(frozen=True)
class MidiMessage:
    kind: str
    data: tuple[int, ...]

    @classmethod
    def sysex(cls, frame: list[int] | tuple[int, ...]) -> "MidiMessage":
        return cls("sysex", tuple(frame))

    @classmethod
    def cc(cls, channel: int, control: int, value: int) -> "MidiMessage":
        if not 0 <= channel <= 15:
            raise ValueError("MIDI channel must be 0..15")
        if not 0 <= control <= 127 or not 0 <= value <= 127:
            raise ValueError("MIDI CC values must be 0..127")
        return cls("cc", (0xB0 | channel, control, value))


class MidiTransport(Protocol):
    """Minimal transport required by the bridge."""

    name: str

    def send_sysex(self, frame: list[int]) -> None: ...

    def send_cc(self, channel: int, control: int, value: int) -> None: ...

    def close(self) -> None: ...

    def describe(self) -> dict[str, Any]: ...


class MemoryMidiTransport:
    """Deterministic transport for unit tests and dry runs."""

    name = "memory"

    def __init__(self, on_message: Callable[[MidiMessage], None] | None = None):
        self.sent: list[MidiMessage] = []
        self.on_message = on_message
        self.closed = False

    def send_sysex(self, frame: list[int]) -> None:
        self._send(MidiMessage.sysex(frame))

    def send_cc(self, channel: int, control: int, value: int) -> None:
        self._send(MidiMessage.cc(channel, control, value))

    def emit(self, message: MidiMessage) -> None:
        if self.on_message:
            self.on_message(message)

    def close(self) -> None:
        self.closed = True

    def describe(self) -> dict[str, Any]:
        return {
            "backend": "memory",
            "name": self.name,
            "sent_messages": len(self.sent),
            "closed": self.closed,
        }

    def _send(self, message: MidiMessage) -> None:
        if self.closed:
            raise RuntimeError("MIDI transport is closed")
        self.sent.append(message)


class MidoMidiTransport:
    """Mido/python-rtmidi backed transport for hardware or virtual ports."""

    def __init__(
        self,
        output_name: str,
        input_name: str | None = None,
        on_message: Callable[[MidiMessage], None] | None = None,
    ) -> None:
        if not _native_midi_enabled():
            raise RuntimeError(
                "Native CoreMIDI access is disabled on macOS by default because "
                "python-rtmidi may abort the interpreter; set "
                f"{_NATIVE_MIDI_ENV}=1 only after confirming the host can access MIDI."
            )
        try:
            import mido
        except ImportError as exc:  # pragma: no cover - depends on host setup
            raise RuntimeError(
                "MIDI backend unavailable; install mixxx-api-bridge[midi]"
            ) from exc

        self._mido = mido
        self.name = output_name
        self.on_message = on_message
        self.output = mido.open_output(output_name)
        try:
            self.input = (
                mido.open_input(input_name, callback=self._on_mido_message)
                if input_name
                else None
            )
        except Exception:
            # Do not leak an already-open output when the input port cannot be
            # opened (for example after a stale virtual MIDI bus disappears).
            self.output.close()
            raise

    @staticmethod
    def available_ports() -> dict[str, Any]:
        if not _native_midi_enabled():
            return {
                "inputs": [],
                "outputs": [],
                "backend": "disabled",
                "error": (
                    "Native CoreMIDI probing is disabled on macOS by default; "
                    f"set {_NATIVE_MIDI_ENV}=1 to opt in."
                ),
            }
        try:
            import mido
        except ImportError:
            return {"inputs": [], "outputs": [], "backend": "unavailable"}

        # CoreMIDI errors from python-rtmidi can call ``abort(3)`` in the
        # native extension instead of raising a Python exception.  Keep that
        # failure in a short-lived child process so a status/ports request can
        # never take down the HTTP bridge (or the caller's Python process).
        probe = """
import json
import mido

inputs = list(mido.get_input_names())
outputs = list(mido.get_output_names())
backend = str(
    getattr(mido.backend, "module_name", None)
    or getattr(mido.backend, "name", None)
    or mido.backend
)
print(json.dumps({"inputs": inputs, "outputs": outputs, "backend": backend}))
"""
        try:
            result = subprocess.run(
                [sys.executable, "-c", probe],
                capture_output=True,
                text=True,
                timeout=5,
                env=os.environ.copy(),
            )
        except Exception as exc:  # pragma: no cover - host process dependent
            return {"inputs": [], "outputs": [], "backend": "error", "error": str(exc)}

        if result.returncode != 0:
            detail = result.stderr.strip() or f"exit code {result.returncode}"
            return {
                "inputs": [],
                "outputs": [],
                "backend": "error",
                "error": f"MIDI backend probe failed: {detail}",
            }
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:  # pragma: no cover - backend dependent
            return {
                "inputs": [],
                "outputs": [],
                "backend": "error",
                "error": f"invalid MIDI backend response: {exc}",
            }
        if not isinstance(payload, dict):  # pragma: no cover - defensive guard
            return {
                "inputs": [],
                "outputs": [],
                "backend": "error",
                "error": "invalid MIDI backend response",
            }
        return payload

    def send_sysex(self, frame: list[int]) -> None:
        if frame[0] != 0xF0 or frame[-1] != 0xF7:
            raise ValueError("SysEx frame must include F0 and F7")
        self.output.send(self._mido.Message("sysex", data=tuple(frame[1:-1])))

    def send_cc(self, channel: int, control: int, value: int) -> None:
        self.output.send(
            self._mido.Message(
                "control_change",
                channel=channel,
                control=control,
                value=value,
            )
        )

    def close(self) -> None:
        self.input.close() if self.input else None
        self.output.close()

    def describe(self) -> dict[str, Any]:
        return {
            "backend": "mido",
            "name": self.name,
            "input_name": getattr(self.input, "name", None) if self.input else None,
            "closed": False,
        }

    def _on_mido_message(self, message: Any) -> None:
        if message.type != "sysex" or self.on_message is None:
            return
        frame = [0xF0, *message.data, 0xF7]
        self.on_message(MidiMessage.sysex(frame))


class CoreMidiProcessTransport:
    """CoreMIDI transport backed by the small C helper in ``tools/``.

    The helper owns one virtual source and one virtual destination and exposes
    a line protocol over stdin/stdout.  Keeping CoreMIDI in that process avoids
    the interpreter-abort failure mode seen with python-rtmidi on sandboxed
    macOS hosts.  ``output_name`` is the endpoint Mixxx opens for input, while
    ``input_name`` is the endpoint Mixxx opens for output.
    """

    name = "coremidi-c"

    def __init__(
        self,
        helper_path: str,
        output_name: str = "Mixxx API Bridge In",
        input_name: str = "Mixxx API Bridge Out",
        on_message: Callable[[MidiMessage], None] | None = None,
        startup_timeout: float = 5.0,
    ) -> None:
        if not helper_path:
            raise ValueError("helper_path is required")
        self.helper_path = os.fspath(helper_path)
        self.output_name = output_name
        self.input_name = input_name
        self.on_message = on_message
        self._write_lock = threading.Lock()
        self._startup: queue.Queue[str | BaseException] = queue.Queue(maxsize=1)
        self._stderr: list[str] = []
        self._closed = False
        try:
            self._process = subprocess.Popen(
                [self.helper_path, self.output_name, self.input_name],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            raise RuntimeError(f"unable to start CoreMIDI helper: {exc}") from exc

        self._reader_thread = threading.Thread(
            target=self._read_stdout,
            name="mixxx-api-coremidi-reader",
            daemon=True,
        )
        self._reader_thread.start()
        self._stderr_thread = threading.Thread(
            target=self._read_stderr,
            name="mixxx-api-coremidi-stderr",
            daemon=True,
        )
        self._stderr_thread.start()
        try:
            first_line = self._startup.get(timeout=startup_timeout)
        except queue.Empty as exc:
            self.close()
            raise RuntimeError("CoreMIDI helper did not become ready") from exc
        if isinstance(first_line, BaseException):
            self.close()
            raise RuntimeError(str(first_line)) from first_line
        if not first_line.startswith("READY "):
            self.close()
            raise RuntimeError(f"unexpected CoreMIDI helper greeting: {first_line}")

    def send_sysex(self, frame: list[int]) -> None:
        if len(frame) < 2 or frame[0] != 0xF0 or frame[-1] != 0xF7:
            raise ValueError("SysEx frame must include F0 and F7")
        if any(not 0 <= value <= 0xFF for value in frame):
            raise ValueError("MIDI bytes must be between 0 and 255")
        self._send_bytes(frame)

    def send_cc(self, channel: int, control: int, value: int) -> None:
        if not 0 <= channel <= 15:
            raise ValueError("MIDI channel must be 0..15")
        if not 0 <= control <= 127 or not 0 <= value <= 127:
            raise ValueError("MIDI CC values must be 0..127")
        self._send_bytes([0xB0 | channel, control, value])

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        process = getattr(self, "_process", None)
        if process is None:
            return
        try:
            if process.stdin and process.poll() is None:
                with self._write_lock:
                    process.stdin.write("QUIT\n")
                    process.stdin.flush()
        except (BrokenPipeError, OSError):
            pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream:
                try:
                    stream.close()
                except OSError:
                    pass

    def describe(self) -> dict[str, Any]:
        process = getattr(self, "_process", None)
        return {
            "backend": self.name,
            "helper_path": self.helper_path,
            "output_name": self.output_name,
            "input_name": self.input_name,
            "pid": process.pid if process is not None else None,
            "closed": self._closed,
            "stderr": "".join(self._stderr[-10:]).strip(),
        }

    def _send_bytes(self, data: list[int]) -> None:
        if self._closed or self._process.poll() is not None:
            raise RuntimeError("CoreMIDI helper is not running")
        if self._process.stdin is None:
            raise RuntimeError("CoreMIDI helper stdin is unavailable")
        encoded = "".join(f"{value:02X}" for value in data)
        try:
            with self._write_lock:
                self._process.stdin.write(f"SEND {encoded}\n")
                self._process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise RuntimeError(f"CoreMIDI helper write failed: {exc}") from exc

    def _read_stdout(self) -> None:
        stream = self._process.stdout
        if stream is None:
            self._startup.put(RuntimeError("CoreMIDI helper stdout is unavailable"))
            return
        try:
            for raw_line in stream:
                line = raw_line.strip()
                if not line:
                    continue
                if line.startswith("READY "):
                    try:
                        self._startup.put_nowait(line)
                    except queue.Full:
                        pass
                    continue
                if not line.startswith("RECV "):
                    continue
                try:
                    data = bytes.fromhex(line[5:].strip())
                except ValueError:
                    continue
                if data and self.on_message is not None:
                    self.on_message(MidiMessage.sysex(list(data)))
        finally:
            if not self._closed:
                try:
                    self._startup.put_nowait(
                        RuntimeError("CoreMIDI helper exited before becoming ready")
                    )
                except queue.Full:
                    pass

    def _read_stderr(self) -> None:
        stream = self._process.stderr
        if stream is None:
            return
        for raw_line in stream:
            self._stderr.append(raw_line)
