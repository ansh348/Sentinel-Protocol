# 1b confirmatory matrix runner + 1bKG gate computation — build record (reviewed change)

**Date:** 2026-06-15 (pre-fire; the one-shot is the next deliberate step). **Scope:** GLUE +
SCORING only. The frozen detection stack is unchanged except one additive, behavior-preserving
pass-through (flagged below). The compile prompt, escrow, and D-series are byte-unchanged
(verified). **No sealed cell was executed; no held-out value was read.**

## What was built

- `analysis/matrix_runner.py` (C1) — the confirmatory matrix runner. Loads + hash-verifies BOTH
  escrow files via `conductor/escrow_loader.py`; enumerates the consumable cells (33 matrix = 21
  injected after the D23 skip of 6 + 12 clean; 10 held-out = 5 RB + 5 DV; ×5 arms = 215 / ×4 =
  172); accepts an arm-scope parameter (the fire passes V2/S1/S2/S3 per D33); dispatches each cell
  through the frozen `sentinel_v2.arms.dispatch` using the cell's sealed seed + opaque
  injection-params (no new RNG); persists a SEAL-SAFE per-cell-per-arm ledger (public identity +
  outcome metrics only — no drawn seed/n_inject/param ever written or printed); a persistent,
  logged, resumable launcher (append-as-you-go + skip-completed) with a `__main__` fire entry.
- `analysis/matrix_gates.py` (C2) — the 1bKG1–4 post-matrix computation over the ledger.
- `analysis/matrix_smoke.py` (C3) — the seen smoke (wiring + compute; no sealed cell).
- `tests/test_matrix_runner_gates.py` — 9 synthetic unit tests (no LLM, no real escrow).

## Gate definitions implemented, with frozen-prereg citations

| component | definition (verbatim source) |
|---|---|
| 1bKG1 overall recall | strict recall ≥60% on RECOVERABLE-class cells; kill floor <40% — `prereg_1b.md` §2 + §3a (AUTHOR-8 manifest); `decision_memo_phase1.md` §4 |
| 1bKG1 recoverable-class labels | original 9 pairs verbatim from §3a; DEPENDENCY_VERSION always recoverable (`DEPENDENCY_VERSION.md` §3); RESOURCE_BUDGET mechanical at the drawn N/Q0 (`RESOURCE_BUDGET.md` §3) — **SURFACED**, see below |
| 1bKG1 categorical clause | ≥50% in ≥4/5 ORIGINAL categories; per-category strict detection over ALL injected cells — AUTHOR-1 ruled option (a), `prereg_1b.md` §4 |
| 1bKG1 Wilson lower bound | 95% (two-sided convention) — AUTHOR-9 ruled, `prereg_1b.md` §2 line 426; n<3 descriptive only |
| 1bKG1 probe-validity HARD gate | seeded 20% audit, seed **1102**, author audits targeted/fresh/non-perturbing/independent, 100% pass or exclude class — AUTHOR-12, `prereg_1b.md` §2 + §4 — **human input** |
| 1bKG1 recovery-quality | detect-only / detect-and-recover / detect-and-justified-abort; ≥50% latter two; unjustified abort on a recoverable cell never counts — `prereg_1b.md` §2 + §3a |
| 1bKG2 | clean median FIR=0, P95≤1, max false ≤3, zero escalation-cap grinds (hard); injected pre-detection false median ≤2; clean success ≥60% AND ≥(S1 clean−10) — `prereg_1b.md` §2; FIR 0/0=0 `prereg.md` 6.1 |
| 1bKG3 | clean overhead = (V2 clean median cost − S1 clean median cost)/S1 ≤ 0.12 — `prereg_1b.md` §2; overhead def `prereg.md` 6.1; ≤12% of S1 `prereg.md` 6.2 |
| 1bKG4 | TTD ≥2× faster than S3 AND wasted-work (V2 post-invalidation tokens + probe overhead) ≤1.0×S3 — `prereg_1b.md` §2 + §4; TTD/wasted-work defs `prereg.md` 6.1/6.2 |

## Surfaced — NOT invented (human-audit inputs / fire-time / unpinned closed form)

The gate computation marks these PENDING (never auto-PASS) and consumes them as explicit inputs:

1. **RESOURCE_BUDGET recoverable-class closed form.** `RESOURCE_BUDGET.md` §3 labels a RB cell
   REPLAN-recoverable iff `Q0 ≥ expected-remaining-required (from the task's clean-median call
   profile at the drawn N)`. The "expected-remaining-required" derivation is described but NOT
   given as a single closed formula; the runner returns `RB_MECHANICAL_AT_LAUNCH` for RB cells and
   the gate surfaces them, to be labeled at fire from the sealed N/Q0 (without printing them) — not
   invented here.
2. **Probe-validity audit verdicts** (AUTHOR-12): the gate computes the deterministic 20% sample
   (seed 1102) and presents it; the targeted/fresh/non-perturbing/independent verdicts are the
   author's audit, supplied as `audit['probe_validity_verdicts']`. Absent ⇒ PENDING.
3. **Instrumentation-integrity replay** (Standing, 100% injected, BEFORE gates): supplied as
   `audit['instrumentation_replay_passed']`. Absent ⇒ PENDING.
4. **Escalation-cap-grind signal on clean cells** (1bKG2 hard, zero): not a ledger field; supplied
   as `audit['clean_escalation_cap_grinds']`. Absent ⇒ PENDING.
5. **Injected pre-detection false-interrupt window** (1bKG2, "before first detection"): a trace
   quantity; the ledger's per-cell `false_interrupts` is used as an upper PROXY, with the windowed
   value supplied as `audit['injected_pre_detection_false']` if a tighter measure is wanted.

## The one frozen-stack touch (flagged for review)

`sentinel_v2/arms.py`: `dispatch(...)` gained an **additive, optional, None-default**
`injection_params` parameter, forwarded to `run_one`/`V2Conductor` — which ALREADY accept it
(`run_one.py:332`, added by the N3 sealed-loader commit "None = byte-identical"). It is the missing
forwarder so the runner can dispatch HELD-OUT cells (which carry drawn params) through the frozen
arms, as the deliverable requires. It touches NO detection logic; `None` = byte-identical, and the
suite is **399→408 green both flag states** with the seen smoke byte-unchanged on the `None` path.
Recorded transparently as the sole modification to the frozen arms; the alternative (a runner-local
conductor call) was rejected because it would fork frozen dispatch logic rather than dispatch
through it.

## Seen-smoke confirmation (wiring + compute; runs/matrix_1b_smoke, gitignored)

2 development seen cells (a1+endpoint_404, a1+clean) × V2/S1/S2/S3 = 8 dispatches, persisted; the
gate computation ran over them and emitted per-gate statuses + a verdict without error
(1bKG3 FAIL on the tiny set, 1bKG1/1bKG2/1bKG4 PENDING on owed human inputs / undetected-S3 — the
smoke proves the plumbing, it is NOT tuned to pass). The escrow-load path hash-verified BOTH files
(matrix 33, holdout 10, D23 skipped 6) dispatching no sealed cell. **0 sealed cells executed; 0
held-out values read.**

## Status

Built before the run, so it cannot be tuned to a result. The one-shot is the next deliberate step:
re-run the pre-flight, then `python -m analysis.matrix_runner V2 S1 S2 S3` fires it; the gates run
as the clean post-matrix follow-up with the author's audit inputs.
