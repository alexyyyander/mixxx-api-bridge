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

### `POST /api/handshake`

Send a new HELLO frame. The mapping answers with READY if it is enabled on the
connected MIDI port.

## Semantic aliases

The initial registry includes:

- `decks/{deck}/volume`, `gain`, `pregain`, `play`, `rate`
- `mixer/crossfader`
- `fx/units/{unit}/mix`, `super1`, `enabled`
- `fx/units/{unit}/slots/{slot}/enabled`
- `fx/units/{unit}/slots/{slot}/parameterN`

Effect parameter names are dynamic. Use `parameterN` until a loaded-effect
metadata provider maps names such as `time` or `feedback` to parameter slots.
