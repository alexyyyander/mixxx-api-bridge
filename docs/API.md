# HTTP API

The server binds to `127.0.0.1:11120` by default. All values are JSON.

## Health and discovery

### `GET /api/health`

Returns bridge liveness, Mixxx process discovery, MIDI transport details, and
the last mapping handshake.

### `GET /api/status`

Returns the same status payload without the top-level `ok` field.

### `GET /api/capabilities`

Returns the local alias registry, the SysEx protocol operations, and
`remote_capabilities` reported by the mapping (when a handshake has
completed). A READY frame automatically triggers a capabilities query.

## Controls

### `POST /api/control`

Set one writable control. Use either a semantic `path` or a raw `group` and
`key` pair:

```json
{"path":"decks/1/volume","value":0.75}
```

```json
{
  "group":"[EffectRack1_EffectUnit1_Effect1]",
  "key":"parameter1",
  "value":0.65,
  "scale":"normalized",
  "wait_ms":500
}
```

`normalized` uses the range 0..1 and calls `engine.setParameter` inside Mixxx.
`raw` uses the native Mixxx ControlObject range and calls `engine.setValue`.
`wait_ms` is optional (0..5000); when present the response includes an ACK and
feedback frame or `timed_out: true`.

### `GET /api/control`

Read a control asynchronously. Query parameters are `path`, or `group`, `key`,
and optional `scale`/`wait_ms`. The response includes the most recently cached
feedback value in `cached`.

### `POST /api/subscribe`

Subscribe to changes for a control. The mapping sends a feedback SysEx frame
whenever Mixxx changes that ControlObject.

```json
{"path":"mixer/crossfader"}
```

### `POST /api/action`

Invoke a Mixxx action that is not a simple continuous value. The `action`
field is one of `trigger`, `toggle`, or `reset`; the control may be supplied as
`path` or as raw `group` + `key`:

```json
{"action":"toggle","path":"decks/1/play","wait_ms":500}
```

`trigger` calls Mixxx's `script.triggerControl`, `toggle` calls
`script.toggleControl`, and `reset` calls `engine.reset`. The response uses the
same ACK/feedback shape as `/api/control`. Convenience aliases are also
available at `/api/trigger`, `/api/toggle`, and `/api/reset`.

### `GET /api/setting`

Read a setting declared by the active controller mapping:

```text
/api/setting?name=soft_takeover&wait_ms=500
```

This is intentionally read-only. Mixxx exposes `engine.getSetting` to a
mapping, but does not expose a generic `engine.setSetting` API for changing
global preferences through a controller mapping.

### `POST /api/handshake`

Send a new HELLO frame. The mapping answers with READY if it is enabled on the
connected MIDI port.

## Coverage boundary

The raw `group` + `key` form can address any Mixxx ControlObject that is
available to the active Mixxx version. Continuous controls should use
`scale: "normalized"`; controls with discrete or non-0..1 ranges should use
`scale: "raw"`. Read-only controls can be queried or subscribed to but cannot
be written. Momentary controls such as beatjump, hotcue activation and effect
selection should use `/api/action` rather than `/api/control`.

The bridge does not currently enumerate every ControlObject or infer dynamic
effect parameter names. Use the Mixxx Controls index to discover a `group` and
`key`, then probe it with `GET /api/control` before writing. For convenience,
generic path forms are also accepted for `decks/{deck}/{key}` (or
`channels/{channel}/{key}`), `preview_decks/{deck}/{key}`,
`samplers/{sampler}/{key}`, `equalizers/{deck}/{key}`,
`quick_effects/{deck}/{key}`, `mixer/{key}`, `master/{key}`, `main/{key}`,
`app/{key}`, `recording/{key}`, `library/{key}`, `playlist/{key}`,
`autodj/{key}`, `microphones/{n}/{key}`, `auxiliaries/{n}/{key}`, and both
effect-unit/slot forms. The path is only an address translation; Mixxx still
decides whether the key exists and is writable.

## Semantic aliases

The initial registry includes:

- `decks/{deck}/volume`, `gain`, `pregain`, `play`, `rate`
- `mixer/crossfader`
- `fx/units/{unit}/mix`, `super1`, `enabled`
- `fx/units/{unit}/slots/{slot}/enabled`
- `fx/units/{unit}/slots/{slot}/parameterN`

Effect parameter names are dynamic. Use `parameterN` until a loaded-effect
metadata provider maps names such as `time` or `feedback` to parameter slots.
