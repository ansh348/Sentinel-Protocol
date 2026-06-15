# D30 — Arm-time Clean-Baseline Capture — Session Report (2026-06-14)

**Scope:** fix the content-shaped detection miss found in run-loop fidelity by adding a
proactive, category-blind, injection-blind **arm-time** side-channel baseline capture, and
validate it on SEEN cells through the REAL V2Conductor path FOR THE RIGHT REASON. Dev-run,
seen-only; the matrix is NOT run. Prior state: run-loop fidelity close.

---

## C0 — D30 recorded before code (commit `dfc89ff`)

Logged in `deviations.md`: run-loop fidelity found content-shaped detection (fingerprint,
field re-read) conditioned on a clean baseline the D29 event-gated scheduler did not
guarantee (the only worker read of the grounded surface could land after the injection
point). D30 adds a proactive **arm-time** sweep — at run start, after compile, before any
worker tool call — that records the earliest-clean observation of **every** load-bearing
surface in the compiled probe set through the §8 gate, as the guaranteed baseline. A worker
harvest may **refresh** but never **replace** it. Category-blind and injection-blind. Budget:
**~$0 dollars** (side-channel reads; KG3 unaffected); count submetric only. Amends D29
scheduling; preserves D28.

## C1 — implementation (`conductor/run_v2_loop.py`)

- `_arm_time_capture()` fires once at the first compile (run start): acquires one
  worker-class token (reused by all v2 probes for §8 same-token), reads the main counter,
  and for each **unique** load-bearing surface fires one side-channel GET; a clean read
  (status < 400, body present, side-effect-free, pre-transform) becomes the surface's
  baseline with `source="arm_time"` and its capture counter. Side-channel reads don't
  advance the injection clock, so the sweep is in the clean window by construction.
- **Refresh-not-replace:** a worker harvest fills surfaces the arm-time sweep missed (e.g.
  query-required surfaces) but never overwrites an arm-time baseline — a post-injection
  (drifted-but-200) read can't poison the clean reference.
- Same token (`self._v2_token`) used by the arm-time capture AND the barrier probes (§8).
- **Bug found + fixed during validation:** the run-loop probe dedup keyed by **target
  alone** collapsed multiple distinct-shape probes on one surface to one — dropping the
  `schema_shape` probe that catches a field rename. Fixed to dedup by probe **identity**
  (target + shape + lens), so a surface keeps both its schema and value probes.

## C2 — seen validation via the REAL path, right-reason

| cell | detected | interrupts | replans | baseline source @ counter | injection counter | right-reason |
|---|---|---|---|---|---|---|
| a1 + endpoint_404 (status) | **True** | 1 | 1 | status fast path (404) | 12 | n/a (no baseline needed) |
| a1 clean | **False** | **0** | 0 | — | none | quiet ✓ |
| a1 + schema_drift (content) | **True** | 1 | 1 | **arm_time @ 1** | 12 | **YES (1 < 12)** |
| c1 + doc_contradiction (content) | **True** | 1 | 1 | **arm_time @ 1** | 6 | **YES (1 < 6)** |

Both content-shaped cells now detect, and the detection diffed against the **arm-time clean
baseline captured at counter 1, strictly before the injection point** — confirmed for the
right reason (logged baseline capture call-index vs injection call-index; baseline precedes
injection). Status-coded still detects at 1 interrupt / 1 replan; V2 stays **quiet (0
interrupts)** on the clean seen world; **FIR sane** (one true interrupt on the injected
surface, zero false; zero on clean); **total_cost_usd sane** ($0.30–0.74/cell, no dollar
inflation); the arm-probe **count submetric** rose to 6–8/run.

Per-category real-path seen detection: **status-moved** (endpoint_404) ✓, **structure-changed**
(schema_drift) ✓ now caught, **value-moved/content** (doc_contradiction) ✓ now caught — drift
and contradiction caught for the right reason (baseline-before-injection).

## Close verifications
- **Suite:** **373/373 passing, flag OFF and ON** (371 prior + 2 new D30 guard tests:
  harvest-does-not-replace-arm-time, harvest-fills-a-missed-surface).
- **Byte-identity:** **27/27 both flag states**; banked `replay_check.json` restored
  byte-identical (sha256 `f5b44b6…`). Arm-time capture is behind the v2 flag
  (probe_channel-gated) → banked/flag-off configs byte-unchanged.
- **$0 dollar impact:** KG3 (clean overhead, dollars) unaffected — the arm-time probes are
  side-channel reads at ~$0 (clean a1 cost $0.30, no inflation). **Count submetric delta:**
  +6–8 arm-time probe reads per run.
- **Dev-run spend ≈ $2.3** (real multi-worker runs + the dedup-bug debug; bounded, seen-only).
  Logged in `analysis/dev_run_ledger.md`.
- **No held-out file read/loaded; the matrix was NOT run.** SEEN cells only.

## Named residual (NOT patched — threats to validity)
A **runtime-discovered (provisional) surface** whose **first worker touch falls after the
injection point** cannot always be clean-baselined even by the arm-time sweep: the sweep
only knew the compiled probe set at run start, so a surface discovered later has no arm-time
clean reference and its first (post-injection) read is dirty. Recorded in D30 and here;
**not patched.** (Status-coded faults on such surfaces remain detectable via the fast path,
which needs no baseline.)

## Rule Zero
Category-blind and injection-blind throughout: the sweep records the earliest clean
observation of every load-bearing surface with no category logic and no knowledge an
injection exists; the dedup-identity and refresh-not-replace fixes are general. No
escrow/held-out read; nothing run against the held-out set; the one-shot not spent.
Flag-off byte-identical. D28/D29 (otherwise) preserved.

---

## Decisions still waiting (author)
1. **The one-shot matrix** — 215 cells × 5 arms, held-out from escrow at fire, gates once.
   The real V2 path now detects status-, structure-, and content-shaped seen faults for the
   right reason; this is the remaining step.
2. **The provisional-surface residual** (above) — if drift recall on runtime-discovered
   surfaces matters, an admission-time registration of likely surfaces could extend the
   arm-time sweep; recorded, not patched.
3. **Rebuilt-judge tier (V2J)** — still the exploratory pass-through seam.
