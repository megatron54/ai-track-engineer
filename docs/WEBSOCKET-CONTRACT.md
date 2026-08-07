# Dashboard WebSocket contract (frozen for the Fase 3 frontend rewrite)

> Endpoint: `ws://<host>/ws/telemetry`. Every message is a JSON object with a
> `"type"` field discriminating the payload. This document is the single
> source of truth for that wire format so the React rewrite (Fase 3) can
> proceed against a stable target without reading Python. If a payload shape
> changes, update this file in the same PR - CI does not enforce that
> automatically today (see "Contract testing gap" below).

Producers (Python): `src/dashboard/serialization.py` (session/telemetry/lap/pattern/session_report)
and `src/dashboard/pump.py` (advice/coaching/strategy/mode - built inline).

Consumer today: `src/dashboard/static/index.html` (the single-file vanilla-JS
dashboard). The React rewrite should consume exactly this contract.

---

## `session`

Sent once, when a session (track + car) loads.

```json
{
  "type": "session",
  "track": "Laguna Seca",
  "track_id": "ks_laguna_seca",
  "car": "ks_ferrari_488_gt3",
  "length_m": 3602.0,
  "best_ever_ms": 88512,
  "corners": [
    { "index": 1, "name": "Turn 1", "entry": 0.0, "exit": 0.15 }
  ],
  "map": {
    "width": 1024.0,
    "height": 768.0,
    "x_offset": 100.0,
    "z_offset": -50.0,
    "scale_factor": 4.2,
    "margin": 10.0
  }
}
```

- `best_ever_ms` and `map` are nullable (no persisted best lap yet / no map data for this track).

## `telemetry`

Per-frame live state, throttled server-side by `telemetry_every` (see `run_session`).

```json
{
  "type": "telemetry",
  "t": 123.456,
  "speed_kmh": 187.3,
  "rpm": 6800,
  "gear": "4",
  "gas": 1.0,
  "brake": 0.0,
  "fuel": 38.2,
  "lap_pos": 0.4231,
  "coords": [120.5, -33.2],
  "position": 3,
  "sector": 1,
  "current_time": "1:12.345",
  "last_time": "1:29.812",
  "best_time": "1:28.501",
  "completed_laps": 4,
  "tyre_temp": [88.1, 87.4, 82.0, 81.6],
  "tyre_wear": [96.2, 96.0, 97.1, 97.3],
  "steer_angle": 0.12,
  "g_lat": 1.3,
  "g_lon": -0.4,
  "delta": -0.245,
  "status": "LIVE",
  "session": "PRACTICE"
}
```

- `delta` is null until a personal-best reference lap exists.
- `gear` is a label string (e.g. `"N"`, `"R"`, `"4"`), not a number.
- `status` / `session` are the raw enum names from `ACStatus`/`ACSessionType`.

## `lap`

Emitted when a lap completes.

```json
{
  "type": "lap",
  "number": 5,
  "time_ms": 88512,
  "valid": true,
  "is_personal_best": true,
  "sectors_ms": [29500, 29800, 29212],
  "corner_losses": [
    { "corner": "The Corkscrew", "delta_s": 0.42 }
  ],
  "advice": [
    "[The Corkscrew] Losing 0.42s vs your reference - braked 12m later."
  ]
}
```

- `advice` is populated asynchronously (a separate `advice` event usually
  follows for the same lap number); `lap.advice` may arrive empty and be
  "backfilled" by the `advice` event below. Treat them as two independent
  arrivals for the same `lap.number`, not a single atomic update.

## `advice`

The AI (or heuristic-fallback) coaching recommendations for a completed lap.
Published asynchronously, slightly after the corresponding `lap` event.

```json
{ "type": "advice", "lap": 5, "messages": ["[The Corkscrew] ..."] }
```

## `coaching`

Real-time, in-corner feedback (post-corner delta + brake-zone warnings),
rate-limited server-side (`MessageQueue`, mode-aware budget per lap).

```json
{
  "type": "coaching",
  "priority": "HIGH",
  "text": "Approaching Turn 4: +8 km/h vs best - brake earlier",
  "corner": "Turn 4"
}
```

- `priority` is one of `CRITICAL` / `HIGH` / `NORMAL` / `LOW` (enum `.name`, uppercase).
- `corner` is nullable (some messages aren't tied to a specific corner).

## `strategy`

Emitted alongside each `lap` event: fuel, tyre wear and pit-stop guidance.

```json
{
  "type": "strategy",
  "lap": 5,
  "fuel": {
    "remaining": 34.1,
    "per_lap": 2.35,
    "laps_left": 14.5,
    "status": "ok",
    "message": "Fuel OK for 14 more laps."
  },
  "tyres": {
    "wear_pct": 91.4,
    "rate": 1.8,
    "advice": "stay_out",
    "message": "Tyre wear normal, keep an eye on it."
  },
  "pit": {
    "advice": "no_stop",
    "trigger": null,
    "lap": null,
    "message": "No pit stop needed yet."
  }
}
```

- `fuel.status` is one of `"ok"` / `"low"` / `"critical"` (`FuelStatus`).
- `tyres.advice` is one of `"stay_out"` / `"consider_pit"` / `"pit_now"` (`TyreAdvice`).
- `pit.advice` is one of `"no_stop"` / `"plan_stop"` / `"box_now"` (`PitAdvice`).

## `mode`

Emitted when the engineer's session-mode personality changes (Practice/Qualify/Race).

```json
{
  "type": "mode",
  "mode": "qualifying",
  "priority": "hotlap",
  "personality": "focused, minimal chatter",
  "max_messages_per_lap": 2
}
```

## `pattern`

Multi-lap trend detection (Fase 0), emitted once 3+ valid laps exist.

```json
{
  "type": "pattern",
  "worst_corners": [
    { "corner": "T1", "occurrences": 5, "avg_delta_s": 0.31, "trend": "regressing" }
  ],
  "consistency_trend": "stable",
  "lap_time_trend": "improving"
}
```

- `trend` / `consistency_trend` / `lap_time_trend` are one of `"improving"`, `"stable"`, `"regressing"`.

## `session_report`

Cumulative session summary, emitted after every completed lap (Fase 0).

```json
{
  "type": "session_report",
  "total_laps": 8,
  "valid_laps": 6,
  "best_lap_ms": 88512,
  "average_lap_ms": 89430.2,
  "consistency_stdev_ms": 612.4,
  "improvement_ms": 1340,
  "theoretical_best_ms": 88010
}
```

- All numeric fields except `total_laps`/`valid_laps` are nullable (no valid laps yet).

---

## Versioning policy while this contract is "frozen"

- **Additive changes are free**: new optional fields, new event `type`s. The
  React client must ignore unknown fields/types gracefully (as the current
  HTML does via its dispatch table's `|| (() => {})` fallback).
- **Breaking changes** (renaming/removing a field, changing a type) must bump
  a `"schema": 1` field onto every event (not present today - add it in the
  same PR as the first breaking change) so both old and new frontends can
  detect a mismatch instead of silently rendering garbage.
- Until then, this document is the contract. Update it in the same PR as any
  `serialization.py`/`pump.py` payload change.

## Contract testing gap (known, not fixed by this document)

There is no automated check today that this document (or the frontend) stays
in sync with the actual Python payloads - see
`docs/DEEP-DIVE-ROADMAP.md` §2.5 "No hay tests de integración end-to-end...".
A cheap follow-up once the React frontend exists: a schema (e.g. Zod) on the
TypeScript side that validates each incoming message, so a drift fails loudly
in the browser console during development instead of silently.
