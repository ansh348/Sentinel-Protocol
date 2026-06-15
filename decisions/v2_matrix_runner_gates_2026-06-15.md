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

---

## Pinning pass (P1–P5, 2026-06-15) — close the surfaced inputs before the shot

All derived from frozen specs and cited; pinned before any sealed cell runs (cannot be tuned to a
result that does not exist).

- **P1 — arms.py forwarder ACCEPTED.** Banked seen byte-identity re-run: **27/27** unchanged
  (`analysis.replay_check`); the additive None-default `injection_params` forwarder is the
  held-out injection-delivery path. Suite 408 both flags confirms no behavior change.
- **P2 — #5 pre-detection window PINNED.** The per-cell `false_interrupts` count is the
  pre-detection value, a CONSERVATIVE UPPER BOUND (a cell's full false-interrupt count ≥ the count
  strictly before its first detection; can only over-count, never let a violation through). Cite:
  `prereg_1b.md` §2 (1bKG2, "pre-detection false-interrupt budget … median ≤ 2"). No longer
  PENDING; gates PASS/FAIL.
- **P3 — #3 replay + #4 cap-grind WIRED from traces.** (#3) `instrumentation_replay(runs_root)` runs
  the Task-A byte-identity replay on 100% of injected runs before gates (cite `prereg_1b.md` §2
  Standing + §4 line 451; archaeology_v2.md §A). (#4) `clean_cap_grinds(runs_root)` counts clean
  primary-arm runs whose `run_end.reason == "escalation_loop"` (cite `prereg_1b.md` §2 1bKG2;
  `conductor/run_one.py:662`, `MAX_ESCALATIONS=52`). Both verified on the seen smoke (replay 4/4
  injected PASS; cap-grinds 0/2 clean V2). No new thresholds.
- **P4 — #2 probe-validity audit CONFIRMED.** The seed-**1102** 20% sample (AUTHOR-12) is computed
  deterministically and emitted as `probe_audit_worksheet.json`; the author's
  targeted/fresh/non-perturbing/independent verdicts (100%-or-exclude) are consumed via
  `audit['probe_validity_verdicts']`. No threshold change. (`prereg_1b.md` §2 + §4 AUTHOR-12.)
- **P5 — #1 RB recoverable formula PROPOSED (ratification-pending; NOT frozen, NOT in code).** The
  runner still emits the `RB_MECHANICAL_AT_LAUNCH` sentinel; the closed form is proposed below for
  the author's sign-off and applied only after ratification, from sealed N/Q0, without printing them.

### P5 proposal — "expected-remaining-required" closed form (RESOURCE_BUDGET.md §3) — AWAITING RATIFICATION

The consumed RB pair is **(a1, quota_cliff)** only (`escrow_loader.CONSUMED_HOLDOUT_PAIRS`); b1's DV
is always-recoverable (`DEPENDENCY_VERSION.md` §3), so the formula is needed for a1 alone.

`RESOURCE_BUDGET.md` §3: *"REPLAN-recoverable if Q0 ≥ expected remaining required, else
RETREAT-condition,"* with expected-remaining-required = *"from the task's clean-median call profile
at the drawn N."* §2 frames it as *"R further calls to the family … only re-paced calling completes
within Q0,"* §4 makes both operands mechanical (*"the right from the plan's call ledger"*).

**Proposed closed form (a1):**

```
expected_remaining_required(N) = T_a1 − F_a1(N)
REPLAN-recoverable  iff  Q0 ≥ expected_remaining_required(N)   else  RETREAT-condition
```

- **T_a1 = 19** — total required family calls in a clean a1 run, itemized verbatim from §5's a1 row:
  1 item list + 6 per-SKU item reads + 6 quotes + 6 us-east rates (family = `/inventory` `/pricing`
  `/shipping`; `/auth` excluded).
- **F_a1(N)** = number of family-prefix calls among the **first N tool calls** of a1's
  **clean-median call profile** (the median-tool-call-count clean run's call ledger, §4; the same
  clean-median basis §6 draws N from — a1 clean median 24, so N ∈ [9, 14], Q0 ∈ [8, 14]).
- So `expected_remaining_required(N)` = the **unfetched remainder** of the 19 required family calls
  at the injection point N (§5 "unfetched remainder" framing); REPLAN-recoverable iff the drawn Q0
  covers that remainder.

**The one choice that needs the author's ruling:** which clean run defines the profile for F_a1(N) —
proposed the **S1 (batch) clean-median** a1 run's call ledger (the wound is defined "under batch's
natural pattern," §2, and S1 is the inherited clean-cost/profile reference), median seed by
tool-call count. Confirm S1-vs-other-arm and the median-seed tie-break before freezing.

**HALT:** not frozen, not committed to code, no RB cell labeled until ratified.
