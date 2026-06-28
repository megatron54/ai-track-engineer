# Spike B0 — Opponent data source

**Goal:** decide how AI-TrackEngineer should obtain the position / gap of the cars
**ahead** and **behind** the player, to unblock Phase B (live gaps) and Phase C
(overcut / undercut, race-vs-qualy pace). Target: works **offline (vs AI)** and
**online (client)**.

## The problem (verified)

Assetto Corsa's base shared memory is **player-only**. `SPageFileGraphic`
exposes a single `carCoordinates[3]` (the player car) and no per-opponent
positions or gaps — confirmed in `src/telemetry/shm_structs.py:154`. So opponent
data needs a different source.

## Options compared

| Source | Gives all cars? | Offline | Online (client) | Effort | Stability | Notes |
|--------|-----------------|---------|-----------------|--------|-----------|-------|
| **AC in-sim Python app** (`getCarsCount` + `getCarState(..., NormalizedSplinePosition/LapCount/SpeedKMH)`, `getFocusedCar`) | ✅ all cars' spline + lap | ✅ | ✅ | Low–Med | High — same API used by Helicorsa, Track Map, RaceEssentials for years | Needs a tiny app installed in AC + a bridge (UDP/SHM) to our process. Embedded Python 3.3. |
| **CSP extended shared memory** | ⚠️ not a standard documented opponent block; needs a custom CSP Lua module to publish per-car data to SHM | ✅ | ✅ | Med–High | Medium — CSP-version dependent, more reverse-engineering | Avoids an in-sim app but the opponent exposure is not turnkey. |
| **AC local UDP remote telemetry** (`[REMOTE]`) | ❌ player car only | ✅ | ✅ | Low | High | Not usable for opponents. The all-car UDP (ACSP) is **server-side** only, not the local client. |

## Recommendation

**Use the AC in-sim Python app** as the opponent source, bridged to our process.
It is the only option that reliably returns **every car's** spline position and
lap in both offline and online client sessions, using a stable, long-proven API.
CSP-SHM stays a fallback if we later want to drop the in-sim app.

**Bridge:** start with **UDP to `127.0.0.1:9997`** (simple, decoupled, easy to
test). For production we can keep UDP or move to our own named shared memory for
lower latency — the consumer interface stays the same.

## Prototype in this spike

- `tools/ac_app_opponents/OpponentsBridge.py` — the AC in-sim app. Each frame it
  packs `(focused_id, [ (car_id, spline, lap, speed) ... ])` and sends it over UDP.
- `scripts/spikes/opponent_udp_probe.py` — a standalone receiver that decodes the
  packets and prints the player's **position** and the **gap to the car ahead /
  behind** (in lap-fraction), proving the data flows end-to-end.

### How to validate (needs a multi-car session)

1. Copy `tools/ac_app_opponents/OpponentsBridge` into
   `<AssettoCorsa>/apps/python/OpponentsBridge/` (so the file is
   `OpponentsBridge/OpponentsBridge.py`).
2. In AC → Settings → General → enable the **OpponentsBridge** app, then add it
   to the on-track app bar.
3. Start a **Practice or Race with AI cars** (≥ 2 cars) at any track.
4. Run the probe and drive a lap:
   ```bash
   uv run python scripts/spikes/opponent_udp_probe.py
   ```
   You should see lines like `P3/8 | ahead +0.012 lap-frac (id 4) | behind -0.040 lap-frac (id 7)`.

If that works, Phase B production wires it in:
`OpponentSource` (decode UDP) → convert lap-fraction to seconds via track length
and closing speed → feed the existing `GapManager` → publish gaps to the
dashboard + coaching.

## Open items to confirm during the test

- Exact AC API availability in the user's AC/CSP build (function names are stable
  across recent versions but worth confirming).
- Lap-fraction → seconds conversion (needs `track_spline_length` from static SHM
  and the relative speed; trivial once the feed is confirmed).
