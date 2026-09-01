# Installation

This package is installed next to Mixxx as a sidecar. It does not patch or
replace the Mixxx application bundle.

## macOS

1. Create a virtual MIDI bus named `IAC Driver Bus 1` in Audio MIDI Setup, or
   connect a real MIDI controller.
2. Install this package and its optional MIDI backend:

   ```bash
   python3 -m pip install -e '/Users/alexyu/Documents/ChatGPT/mixx/mixxx-api-bridge[midi]'
   ```

3. Install the mapping as a user-level extension:

   ```bash
   mixxx-api-bridge-install-mapping
   ```

   For the macOS sandbox build, the installer automatically selects
   `~/Library/Containers/org.mixxx.mixxx/Data/Library/Application Support/Mixxx/controllers/`
   when that directory exists.

4. In Mixxx, enable the `Mixxx API Bridge` mapping for the selected MIDI port.
   Mixxx officially supports custom XML/JavaScript controller mappings; the
   mapping files belong in the user mapping directory rather than inside the
   app bundle.
5. Start and verify the sidecar:

   ```bash
   export MIXXX_API_BRIDGE_ENABLE_NATIVE_MIDI=1
   mixxx-api-bridge check \
     --midi-output 'IAC Driver Bus 1' \
     --midi-input 'IAC Driver Bus 1'
   mixxx-api-bridge serve \
     --midi-output 'IAC Driver Bus 1' \
     --midi-input 'IAC Driver Bus 1'
   ```

   If `python-rtmidi` causes a CoreMIDI abort on this Mac, build the bundled
   helper and use it instead. This keeps CoreMIDI in a small C process and
   leaves the Python sidecar on the HTTP/protocol layer:

   ```bash
   clang -Wall -Wextra -Werror tools/coremidi_virtual_bridge.c \
     -framework CoreMIDI -framework CoreFoundation \
     -o /private/tmp/mixxx-coremidi-bridge
   mixxx-api-bridge serve \
     --coremidi-helper /private/tmp/mixxx-coremidi-bridge
   ```

   The helper defaults to `Mixxx API Bridge In` (the endpoint Mixxx opens for
   input) and `Mixxx API Bridge Out` (the endpoint Mixxx opens for output).

## Source checkout

When the package is not installed yet, run the same commands with the source
directory on `PYTHONPATH`:

```bash
cd mixxx-api-bridge
PYTHONPATH=src python3 scripts/install_mapping.py --dry-run
PYTHONPATH=src python3 -m mixxx_api_bridge status
```

## Windows and Linux

Use a hardware MIDI controller or a platform virtual MIDI port, install the
mapping with the same CLI, and pass the port names to `serve`. The mapping
installer selects the conventional per-user Mixxx directory for each platform.
