# Changelog

## Unreleased

- Ignore request echoes in the Python sidecar and response echoes in the Mixxx
  mapping so a shared loopback MIDI bus cannot create a reply storm.
- Preserve capabilities when the bus echoes a capabilities query, while still
  reporting real remote errors.
- Add a Python/JavaScript protocol round-trip regression on an echoing bus.

## 0.1.0 - 2026-09-01

Initial public package:

- HTTP sidecar API for Mixxx controls and status discovery.
- MIDI SysEx protocol with handshake, capabilities, commands, feedback, and
  subscriptions.
- User-level Mixxx mapping installer for macOS, Windows, and Linux.
- Optional Mido/python-rtmidi transport plus deterministic memory transport.
- Tests, API/architecture/install documentation, and reproducible packaging.
