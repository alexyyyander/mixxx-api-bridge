# Mixxx API Bridge

[![CI](https://github.com/alexyyyander/mixxx-api-bridge/actions/workflows/ci.yml/badge.svg)](https://github.com/alexyyyander/mixxx-api-bridge/actions/workflows/ci.yml)

`mixxx-api-bridge` is a source-compatible sidecar for Mixxx. It does not
modify the Mixxx binary. A small official-style MIDI controller mapping is
installed in Mixxx's user mapping directory; the sidecar sends commands over a
virtual MIDI port using SysEx and receives acknowledgements/state feedback.

## Current scope

- Local HTTP API on `127.0.0.1:11120`.
- Read-only Mixxx process discovery (`ps` + macOS `Info.plist`).
- Generic raw `group` + `key` controls and common deck/FX aliases.
- MIDI SysEx protocol with hello/ready, set, get, action, subscribe, ack and feedback.
- Generic momentary actions (`trigger`, `toggle`, `reset`) in addition to value writes.
- Optional Mido/python-rtmidi backend; deterministic in-memory backend for tests.
- A macOS CoreMIDI C-helper transport for hosts where python-rtmidi is unsafe.
- On macOS, native CoreMIDI access is opt-in because some sandboxed hosts make
  python-rtmidi abort the interpreter; set `MIXXX_API_BRIDGE_ENABLE_NATIVE_MIDI=1`
  only after confirming the host can access MIDI.
- No Mixxx C++/source changes and no UI automation.

## Install the mapping

The installer only copies the two mapping files to the user mapping directory;
it never writes inside `Mixxx.app`:

```bash
python scripts/install_mapping.py
# equivalent module form
python -m mixxx_api_bridge.mapping_installer
# or, after pip installation:
mixxx-api-bridge-install-mapping
```

On macOS this targets the sandbox Mixxx data directory when it exists
(`~/Library/Containers/org.mixxx.mixxx/Data/Library/Application Support/Mixxx/controllers/`),
otherwise `~/Library/Application Support/Mixxx/controllers/`.
After copying, enable **Mixxx API Bridge** in Mixxx's Controllers settings.

## Run the bridge

Install MIDI support when a real or virtual MIDI port is available:

```bash
python -m pip install -e '.[midi]'
mixxx-api-bridge ports
mixxx-api-bridge check --midi-output 'IAC Driver Bus 1' \
  --midi-input 'IAC Driver Bus 1'
mixxx-api-bridge serve --midi-output 'IAC Driver Bus 1' \
  --midi-input 'IAC Driver Bus 1'
```

On macOS, enable the native backend explicitly for these commands:

```bash
MIXXX_API_BRIDGE_ENABLE_NATIVE_MIDI=1 mixxx-api-bridge ports
```

If the host cannot create a CoreMIDI client, the default is a safe structured
`backend: "disabled"` response rather than a native crash dialog.

For the macOS sandbox case shown above, a small helper can own the CoreMIDI
virtual endpoints without loading `python-rtmidi` into Python. Build it once
from the repository checkout:

```bash
clang -Wall -Wextra -Werror tools/coremidi_virtual_bridge.c \
  -framework CoreMIDI -framework CoreFoundation \
  -o /private/tmp/mixxx-coremidi-bridge
```

Start the sidecar with the helper (the default endpoint names are chosen so
Mixxx pairs the input and output correctly):

```bash
mixxx-api-bridge serve \
  --coremidi-helper /private/tmp/mixxx-coremidi-bridge
```

Use `--midi-output` and `--midi-input` with this mode to override the helper's
source and destination names. The helper is a separate process and is closed
automatically when the sidecar exits.

The same values can be supplied through `MIXXX_API_HOST`, `MIXXX_API_PORT`,
`MIXXX_MIDI_OUTPUT`, `MIXXX_MIDI_INPUT`, and `MIXXX_API_TOKEN`. If a token is
configured, clients must send `Authorization: Bearer <token>`.

For an API-only smoke test without MIDI:

```bash
mixxx-api-bridge serve --dry-run
curl http://127.0.0.1:11120/api/health
curl http://127.0.0.1:11120/api/capabilities
curl -X POST http://127.0.0.1:11120/api/control \
  -H 'Content-Type: application/json' \
  -d '{"path":"decks/1/volume","value":0.75}'

# Momentary and binary controls
curl -X POST http://127.0.0.1:11120/api/action \
  -H 'Content-Type: application/json' \
  -d '{"action":"toggle","path":"decks/1/play","wait_ms":500}'

curl -X POST http://127.0.0.1:11120/api/action \
  -H 'Content-Type: application/json' \
  -d '{"action":"trigger","group":"[Channel1]","key":"beatloop_4_activate"}'
```

The dry-run mode validates the HTTP and protocol layers but cannot change a
Mixxx control because no MIDI port is attached.

## API examples

Full endpoint and protocol documentation is in [`docs/API.md`](docs/API.md) and
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
Installation details are in [`docs/INSTALL.md`](docs/INSTALL.md).

## Repository layout

- `src/mixxx_api_bridge/`: sidecar package, protocol, transports, HTTP server,
  discovery, and control registry.
- `src/mixxx_api_bridge/mapping/`: the XML/JavaScript mapping installed into
  Mixxx's user controller directory.
- `tests/`: Python, protocol, mapping-runtime, and packaging tests.
- `.github/workflows/ci.yml`: cross-platform tests and distribution checks.
- `CONTRIBUTING.md`, `SECURITY.md`, and `CHANGELOG.md`: GitHub project policy.

Use a semantic alias:

```json
{"path":"fx/units/1/mix","value":0.5}
```

Or address any writable Mixxx ControlObject directly:

```json
{
  "group":"[EffectRack1_EffectUnit1_Effect1]",
  "key":"parameter1",
  "value":0.65,
  "scale":"normalized"
}
```

`normalized` values are always 0..1 and are applied by
`engine.setParameter`. Use `raw` only when the control's native range is
known. Effect parameter names are dynamic; use `parameterN` until a mapping
metadata table identifies the loaded effect's labels.

The raw form reaches any Mixxx ControlObject that the active version exposes to
controller mappings. It does not make read-only controls writable, enumerate
the full control index, or replace action-specific APIs. Use `/api/action` for
momentary buttons and `/api/setting` for read-only mapping settings; global
Mixxx preferences are not changed by this sidecar.

The bundled mapping declares a read-only `triggerDelayMs` setting for the
momentary trigger duration. Other mapping settings can be read when a mapping
that declares them is active.

## Protocol handshake

The bridge sends a `HELLO` SysEx frame when it starts. The mapping responds
with `READY`. This is stronger than checking for a running process or a MIDI
port alone. `GET /api/status` reports both process discovery and handshake
state.

The bridge also supports a capabilities frame so a client can verify that the
loaded mapping understands `set`, `get`, `subscribe`, and feedback operations.

## Development

```bash
python -m pytest -q
python -m compileall src scripts
```
