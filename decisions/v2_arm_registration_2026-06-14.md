# v2 Arm Registration — Session Report (2026-06-14)

**Scope:** wire the five Phase-1b matrix arms for the matrix runner and smoke-test them on
SEEN cells. The LAST code change before the one-shot matrix; the matrix is **NOT** run.
Built to `decisions/decision_memo_phase1.md` (frozen arm semantics + reporting rules) and
prereg_1b P3. Prior state: `f588f32` (cadence D29 build close).

---

## The five arms (registered in `sentinel_v2/arms.py::ARMS`)

| arm | role | kind | wiring | reporting rule |
|---|---|---|---|---|
| **V2** | primary (P3, in ink) | v2 | full v2 stack (substrate + compile D4 + corroboration D28 + cadence D29) | the confirmatory claim attaches here regardless of outcomes |
| **V2J** | exploratory | v2 | v2 + rebuilt judge tier (exploratory seam) | never compared post-hoc against V2 as co-primary |
| **S1** | baseline | baseline | batch | — |
| **S2** | baseline | baseline | naive anomaly-gated | **mandatory head-to-head, honesty clause** (if S2 dominates V2 on recall at ≤ FIR, the paper says so in the results, not a footnote) |
| **S3** | baseline | baseline | cost-matched heartbeat | periodic-revalidation baseline |

Directive and memo agree; no discrepancy arose.

## What was wired

- **`sentinel_v2/arms.py`** (was a stub that raised): now the authoritative arm registry +
  dispatch seam. `ArmSpec` (id, kind, role, judge, honesty_clause, heartbeat); `ARMS`
  registry; `resolve_arm` (v2 arms require the v2 flag, baselines resolve regardless,
  unknown → KeyError). The normalized **`ArmResult`** (detected / n_interrupts /
  total_cost_usd / ttd_tool_calls / fir / success / source) is the matrix runner's per-cell
  record. `collect_arm_result` collects a baseline result from a completed run via the M6
  `analysis.metrics.run_metrics` (the same instrument the gates consume). `run_v2_detection`
  is the deterministic v2 detection seam (the cadence pre-completion sweep over compiled
  probes → corroboration; status-coded fast path; baseline-drift consults a harvested clean
  baseline). `v2_result` builds an ArmResult from it. The exploratory V2J judge tier is a
  documented pass-through seam (the rebuilt judge is exploratory, not implemented).
- **Separation:** the v2 arms are registered in `ARMS` with their own deterministic runner;
  they are deliberately **not** v1 `conductor.systems.SYSTEMS` entries, so they never run
  through the v1 tripwire/judge loop. Baselines (S1/S2/S3) dispatch through the **unchanged**
  v1 conductor. `conductor/` is byte-identical to HEAD.
- **`analysis/arm_smoke.py`** — the bounded SEEN-only dev-run: invokes the v2 compile step
  once on a1, runs the v2 detection seam for V2/V2J on clean + endpoint_404 seen worlds, and
  collects S1/S2/S3 from banked seen traces; caches the soft set so re-runs replay at $0.

## Smoke-test result (SEEN cells only)

Per-arm well-formed ArmResult confirmed for all five. The v2 detection seam, given a
harvested clean baseline (the §8 worker-view), correctly **detected the injected seen cell
(endpoint_404, 3 interrupts) and was quiet on the clean seen world** (no cross-instance false
positives once harvest equivalence — same world, same auth — was respected).

| arm | seen cell | detected | interrupts | ttd | cost | source | well-formed |
|---|---|---|---|---|---|---|---|
| V2 | a1 + endpoint_404 (injected) | True | 3 | — | (compile) | v2_detection | yes |
| V2J | a1 + endpoint_404 (injected) | True | 3 | — | (compile) | v2_detection | yes |
| S1 | a1 + endpoint_404 (banked) | False | 0 | — | $0.295 | conductor | yes |
| S2 | a1 + endpoint_404 (banked) | True | 1 | 4 | $0.342 | conductor | yes |
| S3 | a1 + endpoint_404 (banked) | False | 0 | — | $0.245 | conductor | yes |

(The deterministic `tests/test_arms.py` additionally proves the v2 seam fires on a real 404
and is quiet on a healthy 200, at $0.)

## Verifications

- **Result collection confirmed:** the matrix runner collects, per arm, detection /
  interrupts / total_cost_usd / TTD — baselines via `run_metrics`, v2 arms via the detection
  seam, both into the uniform `ArmResult`.
- **Dev-run spend:** ≈ **$0.26** (two live v2 compiles, 19–23 soft assumptions → probes;
  soft set then cached so re-runs replay at $0). Logged in `analysis/dev_run_ledger.md`.
- **Byte-identity:** **27/27 both flag states**; banked `replay_check.json` restored
  byte-identical (sha256 `f5b44b6…`). The arm registry is additive behind the flag and the
  conductor (baselines) is byte-unchanged, so the flag-off path is unperturbed.
- **Suite:** **364/364 passing, flag OFF and ON** (355 prior + 9 new arm tests; the scaffold
  stub tests were updated to the wired behavior).
- **No held-out file read; matrix NOT run.** Only seen artifacts touched: task a1, the
  endpoint_404 seen injection, banked seen S1/S2/S3 traces, the decision memo, the prereg.
  No escrow/holdout file was read or loaded; the held-out set enters only at matrix-fire from
  escrow. The one-shot was not spent.

## Test counts
`tests/test_arms.py` 9 (registry, resolve gating, baseline collection over banked seen,
the v2 detection seam fire/quiet, V2J judge seam). `tests/test_v2_scaffold.py` updated
(stub-raise assertions → wired-behavior assertions; still 6). Suite 364/364 both flag states.

## Rule Zero compliance
Category-blind throughout; no quota/version/resource-specific behavior in the registry or
seam. No escrowed/held-out file read or loaded; nothing run against the held-out set; the
one-shot matrix not touched. Flag-off byte-identical to Phase 1 (27/27). D28/D29 preserved.

---

## Decisions still waiting (for sessions with the author)
1. **The one-shot matrix** — fire the 215-cell (D23) matrix across the five registered arms,
   held-out drawn from escrow at fire-time; gates compute once. NOT run here.
2. **Full v2 run-loop fidelity** — the matrix V2/V2J run executes the v2 detection during a
   live multi-worker run (cadence firing probes at worker barriers mid-run, harvesting worker
   reads as baselines). This session wired the arm seam, the v2 compile, and the detection
   stack; the smoke harvested the baseline directly. Confirm the mid-run harvest path at
   matrix-fire (the cadence layer is built; this is its integration into the live run).
3. **The rebuilt judge tier (V2J)** — exploratory; the seam is a pass-through here. Wiring a
   real rebuilt judge is reserved and never compared co-primary with V2.
