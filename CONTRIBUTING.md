# Contributing

## Development setup

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest -q
```

For MIDI integration work, install the optional backend as well:

```bash
python -m pip install -e '.[midi]'
```

## Scope and design rules

- Keep the bridge as a sidecar; do not patch or vendor Mixxx source code.
- Do not add UI automation or window-control code.
- Keep protocol changes mirrored in `protocol.py` and
  `src/mixxx_api_bridge/mapping/MixxxApiBridge-scripts.js`.
- Add a deterministic test for every new endpoint, protocol operation, or
  control alias.
- Keep individual files below 3000 lines and prefer small focused modules.

Before opening a pull request, run the same checks as CI:

```bash
python -m pytest -q
python -m compileall -q src scripts
node --check src/mixxx_api_bridge/mapping/MixxxApiBridge-scripts.js
```
