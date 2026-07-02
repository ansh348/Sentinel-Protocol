# A7 — Phase 2 Validation Report (offline build; NO metered spend)

**Status: core noise mechanism BUILT + VALIDATED offline. Byte-identity gate PASSED before any
unit test counted (author's Phase-2 rule).** One build item remains before Phase 3 (the runner,
§6). No metered spend occurred; Phase 3 stays gated on the author's explicit go.

## 1. What was built (all gated behind `noise_profile`, default None → off)

| File | Change |
|---|---|
| `world/state.py` | `NoiseClass` + `NoiseProfile` model; `RunConfig.noise_profile: Optional[NoiseProfile] = None` (additive knob, same pattern as `probe_channel`/`n_regions`); seed-derived noise state in `WorldState` (dedicated `random.Random(seed + 104729)` stream; all None/False when off) |
| `world/noise.py` (new) | `active()`, `trip_transient_500()`, `decorate_body()` — harness-only, seed-derived, benign; elapsed_ms constant envelope + latency spike + additive field |
| `world/server.py` | two gated hooks: transient-500 boundary short-circuit in `WorldMiddleware.__call__` (heals after one fire); response decoration in `_respond` (before matcher + trace, so monitor and worker see the same body). Worker traffic only — the probe channel (`_respond_probe`) is untouched |

## 2. Byte-identity admissibility gate — **PASS** (the precondition)

Flag-off (`noise_profile` absent in banked `world_config.json` → defaults None → all noise code
skipped) replayed against banked **clean** traces via `analysis/replay_check.replay_cell`:

| banked clean cell | calls | matches | mismatches | injection-counter parity |
|---|---|---|---|---|
| a1-S1-clean-s1 | 24 | 24 | 0 | ✔ |
| b1-S1-clean-s1 | 8 | 8 | 0 | ✔ |
| c1-S1-clean-s1 | 10 | 10 | 0 | ✔ |

**0 unexplained mismatches. Flag-off is provably inert.**

## 3. Frozen-file integrity — **PASS**

`tests/test_frozen_integrity.py` green: the 4 sha256-pinned files (`sentinel/dsl.py`,
`prompts/{sentinel_compile,sentinel_judge,worker}.md`) are **unmodified**. A7 touched none of
them, nor the v2 compile prompt/few-shot, banked traces, sealed escrow, or gate logic.

## 4. Full suite — **PASS, no regression**

`pytest -q`: **433 passed** (417 pre-existing + 10 A7-noise + 6 A7-runner), 1 pre-existing
deprecation warning. The flag-off path changed nothing anywhere in the suite.

## 5. A7 unit tests (flag-on) — **10/10**

`tests/test_a7_noise.py`:
- flag-off state inert + responses carry no noise fields;
- `elapsed_ms` present in ALL 3 classes (D36 constant envelope);
- transient_500 fires **exactly once** at the seed-derived call and **heals** (retry → 200);
  its 500 body is the benign transient body;
- latency_spike produces **exactly one** elevated `elapsed_ms`; baseline otherwise;
- additive_field is **purely additive** — every original field preserved, only `elapsed_ms` +
  `advisory` added (`set(on) − set(off) == {elapsed_ms, advisory}`) → benign;
- same seed → same schedule (byte-replayable).

*Note (surfaced by a test): the single transient-500 can land on any early call (token OR first
surface call) depending on the seed's trigger — benign, the retry heals. Recorded because it
shapes how the live runner must tolerate the transient.*

## 6. Phase-2 build — COMPLETE (offline)

1. **Conductor plumbing — DONE.** `noise_profile` threaded through
   `conductor/run_one.py::Conductor` → `RunConfig`, and `conductor/run_v2_loop.py::run_v2_loop`
   (V2 inherits via `**kwargs`). New trace event `noise_fired` registered in `trace.py` (records
   the transient-500 landing call: token vs first surface call). Flag-off byte-identity
   **re-verified after plumbing** (still 24/24, 8/8, 10/10, 0 mismatches).
2. **`analysis/a7_runner.py` — DONE.** Foreground-chunked, resumable runner: S1-qualify-first →
   per-cell M6 gate → V2/S2 on qualified cells, in the frozen run order (S1 → transient-500 →
   additive → latency); append-only `a7_results.jsonl` ledger; cumulative **modeled** cost; hard
   **$15** cap (stop before a job could exceed the ceiling; partial; **no verdict** on a truncated
   matrix); `--preflight` mode. Per transient-500 cell, the world-trace `noise_fired` landing is
   mirrored into the ledger.
3. **Offline runner validation — 6/6** (`tests/test_a7_runner.py`, mock executor): frozen order;
   per-cell M6 gate (a disqualified cell skips only its own V2/S2, the class surviving elsewhere);
   hard cap never exceeded; resume skips completed + carries cost; chunk-time exit is resumable.

The live S1-first runs **are** the benign qualification (§3 of the plan) — exercised in Phase 3,
not fabricable offline (they need real workers).

## 7. Design conformance

- **D36** constant `elapsed_ms` envelope (present all classes/arms/qual; spikes only in latency
  cells; value-only, no wall-clock) — implemented exactly.
- Noise on **worker traffic only**; the perturbation-isolated probe channel is untouched.
- Seed-derived determinism via a dedicated RNG stream; no `time.*` on any response path.
- Additive-knob default-off → byte-identity by construction (§2).

## 8. Open items

- **Rider 3 (tex) — RESOLVED (2026-07-02, author-authorized).** `fse_focused_v5.tex:923-925`
  narrowed: only the redesign's clean FIR 0 is the optimistic bound; S2's four clean false-fires
  cited as the naive baseline already leaking in the noiseless world (`\S7`). D35 reconcile note
  **CLOSED**.
- **Phase 3 remains gated** on the author's explicit go after the pre-flight summary. No metered
  spend.
