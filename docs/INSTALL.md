# End-to-end installation

`mixxx-api-bridge` is a sidecar. It does not patch `Mixxx.app`, change Mixxx
source code, or automate the Mixxx window. The data path is:

```text
HTTP/CLI client
      │
      ▼
Python bridge ── MIDI SysEx ── Mixxx API Bridge mapping ── Mixxx ControlObjects
```

The mapping is installed in Mixxx's user controller directory. The bridge and
the mapping must use the same MIDI endpoints.

## 1. Prerequisites

- Mixxx 2.4 or newer (tested locally with Mixxx 2.5.6).
- Python 3.9 or newer.
- A MIDI connection between the bridge and Mixxx:
  - macOS: the bundled CoreMIDI helper (recommended for sandboxed hosts), an
    IAC Driver bus, or a hardware MIDI device;
  - Ubuntu/Linux: a hardware or ALSA/PipeWire virtual MIDI port.

On macOS, the CoreMIDI helper avoids loading `python-rtmidi` into the Python
process. This is useful when the host rejects native MIDI client creation and
would otherwise terminate Python.

## Ubuntu / Linux quick path

Ubuntu does not need the CoreMIDI helper. Use the ALSA MIDI backend through
Mido/`python-rtmidi`:

The normal per-user mapping directory on Ubuntu is:

```text
~/.mixxx/controllers/
```

```bash
sudo apt update
sudo apt install -y mixxx python3-venv python3-pip build-essential libasound2-dev alsa-utils

git clone https://github.com/alexyyyander/mixxx-api-bridge.git
cd mixxx-api-bridge
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev,midi]'
mixxx-api-bridge-install-mapping --force
```

If the machine has no hardware MIDI device, an ALSA sequencer dummy client can
be used for experimentation:

```bash
sudo modprobe snd-seq-dummy ports=2
aconnect -l
mixxx-api-bridge ports
```

For PipeWire sessions, use the exact port names shown by
`mixxx-api-bridge ports` and connect the bridge/Mixxx endpoints in a patchbay
such as `qpwgraph` (or with the appropriate `pw-link` commands). The bridge
does not create Linux virtual ports itself; it opens existing ALSA/PipeWire or
hardware ports.

Start Mixxx once, enable `Mixxx API Bridge` on the chosen MIDI input/output
ports, then run the sidecar in another terminal:

```bash
mixxx-api-bridge check \
  --midi-output '<port carrying commands to Mixxx>' \
  --midi-input '<port carrying Mixxx feedback>'

mixxx-api-bridge serve \
  --midi-output '<port carrying commands to Mixxx>' \
  --midi-input '<port carrying Mixxx feedback>'
```

On Linux, `MIXXX_API_BRIDGE_ENABLE_NATIVE_MIDI=1` is not required. That
environment variable is only needed for the guarded macOS native MIDI path.

## 2. Install from a checkout

```bash
git clone https://github.com/alexyyyander/mixxx-api-bridge.git
cd mixxx-api-bridge
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

For the Mido backend, install the optional MIDI dependencies too:

```bash
python -m pip install -e '.[midi]'
```

The source-checkout commands below work without installation by prefixing them
with `PYTHONPATH=src`.

## 3. Install the Mixxx mapping

Install the XML and JavaScript mapping into the user-level controller folder:

```bash
mixxx-api-bridge-install-mapping --force
```

The installer never writes inside the Mixxx application bundle. On a macOS
sandbox build it prefers:

```text
~/Library/Containers/org.mixxx.mixxx/Data/Library/Application Support/Mixxx/controllers/
```

Otherwise it uses the conventional platform-specific Mixxx user directory.
The destination can be inspected without writing:

```bash
mixxx-api-bridge-install-mapping --dry-run
```

For an isolated Mixxx profile, install explicitly into that profile's
`controllers/` directory:

```bash
mixxx-api-bridge-install-mapping --force \
  --destination "$HOME/Library/Containers/org.mixxx.mixxx/Data/Library/Application Support/Mixxx/api-bridge-test/controllers"
```

## 4. Enable the mapping in Mixxx

In Mixxx's Controllers settings, select the MIDI input port that carries the
bridge's **In** endpoint and enable `Mixxx API Bridge`. Select the matching MIDI
output port for feedback. This is the only Mixxx-side setup; no Mixxx source
change is required.

The bundled mapping declares one optional setting, `triggerDelayMs` (default
`200` ms), which controls the duration of `trigger` actions.

## 5. macOS CoreMIDI helper (recommended)

Build the helper once from the repository checkout:

```bash
clang -Wall -Wextra -Werror tools/coremidi_virtual_bridge.c \
  -framework CoreMIDI -framework CoreFoundation \
  -o /private/tmp/mixxx-coremidi-bridge
```

The helper creates two virtual endpoints:

```text
Mixxx API Bridge In   ← Mixxx receives commands here
Mixxx API Bridge Out  → Mixxx sends feedback here
```

The bridge's helper mode uses those names by default. To use different names,
pass `--midi-output` and `--midi-input` explicitly.

## 6. Start Mixxx and the bridge

Start Mixxx normally, then start the sidecar in another terminal:

```bash
mixxx-api-bridge serve \
  --coremidi-helper /private/tmp/mixxx-coremidi-bridge
```

Before starting the long-running server, the same helper connection can be
checked with:

```bash
mixxx-api-bridge check \
  --coremidi-helper /private/tmp/mixxx-coremidi-bridge
```

If Mixxx is installed elsewhere, launch its executable directly, for example:

```bash
/Applications/Mixxx.app/Contents/MacOS/Mixxx
```

Mixxx 2.5.6 does not expose a `--headless` command-line option. It can be
started as a background process, but Qt and the Mixxx GUI still initialize; the
bridge itself remains API/MIDI-only and does not interact with the window. For
diagnostic logging, add `--controller-debug --log-level info` to the Mixxx
command.

For a background launch (not a true headless process), use an exact executable
and an isolated settings directory if desired:

```bash
nohup /Applications/Mixxx.app/Contents/MacOS/Mixxx \
  --settings-path "$HOME/Library/Application Support/Mixxx/api-bridge" \
  >"$TMPDIR/mixxx-api-bridge.log" 2>&1 &
```

### Alternative: IAC Driver Bus or hardware MIDI

List ports first:

```bash
MIXXX_API_BRIDGE_ENABLE_NATIVE_MIDI=1 mixxx-api-bridge ports
```

Then verify and run with the exact names reported by `ports`:

```bash
MIXXX_API_BRIDGE_ENABLE_NATIVE_MIDI=1 mixxx-api-bridge check \
  --midi-output 'IAC Driver Bus 1' \
  --midi-input 'IAC Driver Bus 1'

MIXXX_API_BRIDGE_ENABLE_NATIVE_MIDI=1 mixxx-api-bridge serve \
  --midi-output 'IAC Driver Bus 1' \
  --midi-input 'IAC Driver Bus 1'
```

On macOS, native Mido/RTMIDI is opt-in because some sandboxed hosts crash while
probing CoreMIDI. Prefer the C helper if `ports` or `check` causes a native
MIDI error.

## 7. Verify the complete path

The default HTTP address is `http://127.0.0.1:11120`.

```bash
curl http://127.0.0.1:11120/api/health
curl http://127.0.0.1:11120/api/status
curl http://127.0.0.1:11120/api/capabilities
```

`/api/status` should report both `mixxx.running: true` and
`bridge.connected: true`. If the process is running but `connected` is false,
the mapping is not enabled on the matching MIDI ports, or the endpoint names
are mismatched.

Test a continuous control:

```bash
curl -X POST http://127.0.0.1:11120/api/control \
  -H 'Content-Type: application/json' \
  -d '{"path":"decks/1/volume","value":0.75,"wait_ms":1000}'
```

Test a button action:

```bash
curl -X POST http://127.0.0.1:11120/api/action \
  -H 'Content-Type: application/json' \
  -d '{"action":"toggle","path":"decks/1/play","wait_ms":1000}'
```

Test the mapping setting:

```bash
curl 'http://127.0.0.1:11120/api/setting?name=triggerDelayMs&wait_ms=1000'
```

Test a dynamic effect parameter:

```bash
curl -X POST http://127.0.0.1:11120/api/control \
  -H 'Content-Type: application/json' \
  -d '{"path":"fx/units/1/slots/1/parameter1","value":0.65,"wait_ms":1000}'
```

## 8. Source-checkout smoke test

This checks the Python/protocol/HTTP layers without a MIDI connection:

```bash
PYTHONPATH=src python3 -m pytest -q
PYTHONPATH=src python3 -m mixxx_api_bridge serve --dry-run
curl http://127.0.0.1:11120/api/health
```

Dry-run mode cannot change a Mixxx control. For a real local integration test,
run the CoreMIDI helper, Mixxx, and the non-dry-run `serve` command as described
above.

## 9. Optional HTTP token

Bind only to localhost by default. If a client on another trusted host needs
access, configure an explicit host and bearer token:

```bash
MIXXX_API_HOST=127.0.0.1 \
MIXXX_API_PORT=11120 \
MIXXX_API_TOKEN='replace-with-a-long-random-token' \
mixxx-api-bridge serve --coremidi-helper /private/tmp/mixxx-coremidi-bridge
```

Clients must then send:

```bash
curl -H 'Authorization: Bearer replace-with-a-long-random-token' \
  http://127.0.0.1:11120/api/status
```

## 10. Troubleshooting and shutdown

- `bridge.connected` is false: confirm Mixxx has `Mixxx API Bridge` enabled and
  that its input/output port names match the helper or `ports` output.
- `found: false` from `/api/setting`: the active mapping did not declare that
  setting. This endpoint is read-only; it does not change global Mixxx
  preferences.
- A control returns ACK value `0` with an `Unknown control` warning: the
  group/key syntax reached Mixxx, but that key is not available in the current
  Mixxx state/version or is not writable.
- An effect `parameterN` is unavailable: load an effect into that slot and use
  the parameter numbering for that effect.
- CoreMIDI aborts from Python: stop the Mido process and use the C helper mode.

Stop the bridge with `Ctrl-C`; it closes the helper automatically. Stop Mixxx
with its normal quit mechanism or send an interrupt to the exact process you
started. Do not use broad process-kill patterns on a shared workstation.

## 11. Uninstall mapping

The installer does not delete files. To remove only this mapping, delete these
two files from the user controller directory after confirming the path:

```text
MixxxApiBridge.midi.xml
MixxxApiBridge-scripts.js
```

Restart Mixxx after removing the mapping. The Mixxx application bundle and the
Mixxx database are not modified by this project.
