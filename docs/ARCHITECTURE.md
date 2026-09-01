# Architecture

The bridge is deliberately a sidecar. It never injects code into
`Mixxx.app`, uses no window automation, and only uses the extension point that
Mixxx exposes for MIDI controller mappings.

```text
HTTP client / CLI
        |
        v
  mixxx_api_bridge
  - process discovery
  - control registry
  - request/ACK state
  - MIDI transport
        |
        | MIDI SysEx frames
        v
  MIDI transport
  - Mido/python-rtmidi (IAC or hardware)
  - CoreMIDI C helper process (macOS fallback)
        |
        v
  MixxxApiBridge.midi.xml + MixxxApiBridge-scripts.js
        |
        v
  Mixxx ControlObjects
```

## Wire protocol

Every frame is a SysEx message:

```text
F0 7D 4D 58 41 01 OP <ASCII JSON> F7
```

`0x7D` is the non-commercial SysEx manufacturer ID. JSON is encoded with
ASCII escapes so every payload byte remains a valid 7-bit MIDI data byte.

Operations are:

| Code | Direction | Meaning |
| ---: | --- | --- |
| `0x00` | bridge → Mixxx | HELLO |
| `0x01` | bridge → Mixxx | set control |
| `0x02` | Mixxx → bridge | feedback |
| `0x03` | both | capabilities |
| `0x04` | bridge → Mixxx | subscribe |
| `0x05` | bridge → Mixxx | get control |
| `0x06` | bridge → Mixxx | action (`trigger`, `toggle`, `reset`) |
| `0x07` | bridge → Mixxx | get mapping setting |
| `0x10` | Mixxx → bridge | READY |
| `0x11` | Mixxx → bridge | ACK |
| `0x12` | Mixxx → bridge | mapping setting value |
| `0x7F` | Mixxx → bridge | ERROR |

The Python and JavaScript implementations share deterministic sorted JSON key
ordering. This makes protocol frames easy to compare in tests and logs.

## Connection identity

Process discovery alone is not enough. A valid connection requires:

1. a running Mixxx process;
2. an opened MIDI input/output pair;
3. a READY frame from the mapping.

The status endpoint reports all three layers. Multiple Mixxx instances should
use separate virtual MIDI buses and separate bridge processes.

## macOS CoreMIDI helper

`CoreMidiProcessTransport` starts `tools/coremidi_virtual_bridge.c` as a child
process. The helper creates one virtual source and one virtual destination and
uses a line protocol (`SEND <hex>`, `RECV <hex>`). This keeps CoreMIDI calls
outside Python, which is important on macOS hosts where `python-rtmidi` can
abort instead of raising an exception. The helper is intentionally built and
selected explicitly with `--coremidi-helper`; it is not loaded by default.
