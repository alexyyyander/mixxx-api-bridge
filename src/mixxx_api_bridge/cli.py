"""Command line entry point for the Mixxx API sidecar."""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .bridge import MixxxApiBridge
from .config import BridgeConfig
from .discovery import MixxxDiscovery
from .http_server import serve
from .midi import MidoMidiTransport, MemoryMidiTransport


def build_parser() -> argparse.ArgumentParser:
    defaults = BridgeConfig.from_env()
    parser = argparse.ArgumentParser(description="Control Mixxx through a sidecar HTTP/MIDI API")
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve_parser = subparsers.add_parser("serve", help="start the local HTTP API")
    serve_parser.add_argument("--host", default=defaults.host)
    serve_parser.add_argument("--port", type=int, default=defaults.port)
    serve_parser.add_argument("--midi-output", default=defaults.midi_output, help="MIDI output port connected to Mixxx")
    serve_parser.add_argument("--midi-input", default=defaults.midi_input, help="MIDI input port receiving Mixxx feedback")
    serve_parser.add_argument("--token", default=defaults.auth_token, help="optional bearer token for HTTP clients")
    serve_parser.add_argument("--dry-run", action="store_true", help="use an in-memory MIDI transport")

    subparsers.add_parser("status", help="print process and available MIDI status")
    subparsers.add_parser("ports", help="list available MIDI ports")

    check_parser = subparsers.add_parser("check", help="perform a MIDI mapping handshake")
    check_parser.add_argument("--midi-output", default=defaults.midi_output, required=False)
    check_parser.add_argument("--midi-input", default=defaults.midi_input)
    check_parser.add_argument("--timeout-ms", type=int, default=1000)

    send_parser = subparsers.add_parser("send", help="send one control command")
    send_parser.add_argument("--group")
    send_parser.add_argument("--key")
    send_parser.add_argument("--path")
    send_parser.add_argument("--value", type=float, required=True)
    send_parser.add_argument("--scale", choices=["normalized", "raw"], default="normalized")
    send_parser.add_argument("--midi-output", required=True)
    send_parser.add_argument("--midi-input")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "ports":
        print(json.dumps(MidoMidiTransport.available_ports(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "status":
        process = MixxxDiscovery().detect().as_dict()
        print(json.dumps({"mixxx": process, "midi": MidoMidiTransport.available_ports()}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "check":
        if not args.midi_output or not args.midi_input:
            print("check requires --midi-output and --midi-input", file=sys.stderr)
            return 2
        try:
            transport = MidoMidiTransport(args.midi_output, args.midi_input)
            bridge = MixxxApiBridge(transport)
            bridge.start()
            connected = bridge.wait_until_connected(args.timeout_ms)
            print(json.dumps(bridge.status(), ensure_ascii=False, indent=2))
            return 0 if connected else 1
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        finally:
            if "bridge" in locals():
                bridge.close()

    if args.command == "serve":
        if args.dry_run:
            transport = MemoryMidiTransport()
        elif not args.midi_output:
            print("serve requires --midi-output, or use --dry-run", file=sys.stderr)
            return 2
        else:
            try:
                transport = MidoMidiTransport(args.midi_output, args.midi_input)
            except RuntimeError as exc:
                print(str(exc), file=sys.stderr)
                return 2
        bridge = MixxxApiBridge(transport)
        bridge.start()
        print(f"Mixxx API bridge listening on http://{args.host}:{args.port}", file=sys.stderr)
        try:
            serve(bridge, args.host, args.port, args.token)
        except KeyboardInterrupt:
            pass
        finally:
            bridge.close()
        return 0

    if args.command == "send":
        payload = {"value": args.value, "scale": args.scale}
        if args.group is not None or args.key is not None:
            payload.update({"group": args.group, "key": args.key})
        else:
            payload["path"] = args.path
        try:
            transport = MidoMidiTransport(args.midi_output, args.midi_input)
            bridge = MixxxApiBridge(transport)
            result = bridge.set_control(payload)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        except (RuntimeError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        finally:
            if "bridge" in locals():
                bridge.close()
        return 0
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
