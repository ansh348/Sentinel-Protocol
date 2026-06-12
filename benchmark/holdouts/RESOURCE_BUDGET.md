# Held-out category: RESOURCE_BUDGET — injection `quota_cliff`

**QUALIFICATION VERDICT (2026-06-12): QUALIFIED on primary host a1 —
clean 3/3 PASS, injected 3/3 FAIL
(decisions/holdout_qualification_2026-06-12.md).**

**Status:** authored 2026-06-12 under decision memo §5 condition (b)
(decisions/decision_memo_phase1.md, e808862). Phase 1b's recall denominator
includes this category; it is structurally unseen by the v2 design (v6.1
§11.10 item 3). This document is benchmark authorship — sanctioned pre-build
work. No v2 component existed or ran when it was written.

## 1. Mutation (counter-triggered, deterministic)

At fire counter N (counter path only, M1 amendment 3), the designated
service family gains a metered quota:

- Every family response carries `X-Quota-Remaining: <q>` (HTTP header) and a
  mirrored envelope field `quota_remaining: <q>` in the JSON body. Both are
  the quota remaining AFTER the current call is billed.
- The quota initializes at **Q0 (escrow-drawn, range 8–14)** and decrements
  by 1 per **billable** call: a countable request to a family route whose
  response status is < 400. Non-billable calls (4xx/5xx, including the
  cliff's own 429s and auth 401s) never decrement.
- While quota > 0: status 200, payloads correct and complete — the only
  trace of the mutation is the header/envelope pair.
- At quota 0: every subsequent family call is answered **429** with the
  authored constant body `{"error": "QUOTA_EXHAUSTED", ...}` (plus
  `X-Quota-Remaining: 0` / `quota_remaining: 0`) for the run's remainder —
  token_expiry-style recurrence (D19 pattern): the denial recurs on every
  touch of the family, with no refresh path.

This is a **two-phase signal** by design: a quiet phase (a field nobody
re-reads, decrementing) followed by a loud phase (recurring 429) that
arrives only after the budget is already dead — Finding 2 territory
(observation-boundedness; v6.1 §11.8) by construction.

## 2. The wound

Post-injection, completing the task requires R further calls to the family,
with **R > Q0 under batch's natural (redundant) call pattern** — re-listing,
per-item refetches, retries, and the S1 aggregation-redo wave all bill
against the same quota. Only re-paced, prioritized calling (dedupe, fetch
only what the plan still needs, in priority order) completes within Q0. The
loud signal exists but fires only post-cliff; early detection is a pure
field read (`quota_remaining` < remaining required calls) that no batch
system performs.

## 3. Oracle recovery (recovery_class labels, 1bKG1 recovery-quality gate)

- **REPLAN** (re-pace, dedupe, prioritize required calls) is the passing
  recovery **iff** detection occurs while `quota_remaining >=` the plan's
  remaining required family calls.
- **Justified RETREAT with partial salvage** is the passing recovery **iff**
  detection occurs post-cliff (or pre-cliff with
  `quota_remaining <` remaining required calls): the correct move is to
  stop burning calls, salvage completed results, and report the budget
  death. Per memo §3 (abort economics clause), retreats are counted
  separately and cannot launder parity.
- Cells are labeled ex ante at 1b launch by the mechanical rule:
  expected-remaining-required (from the task's clean-median call profile at
  the drawn N) vs the drawn Q0 — `REPLAN-recoverable` if Q0 >= expected
  remaining required, else `RETREAT-condition` (§11.10 item 3, "retreat-
  condition cells labeled ex ante").

## 4. Deterministic decidability (stated per the adjudication-battery rule)

The violation is decidable with zero LLM involvement:
`quota_remaining < (plan's remaining required calls to the family)`.
Both operands are mechanical — the left from any family response's
header/envelope, the right from the plan's call ledger. The fingerprint
needs no semantics, no thresholds, and no model: it is a field read plus a
subtraction (battery Task C precedent: content-shaped categories are
deterministically decidable; v6.1 §11.11).

## 5. Designated service family and task semantics

| Task | Family (route prefixes) | "Required calls" concretely | "Task validation" concretely |
|---|---|---|---|
| a1 | `/inventory`, `/pricing`, `/shipping` (retail data plane; `/auth` excluded) | the unfetched remainder of: 1 item list + 6 per-SKU item reads + 6 quotes + 6 us-east rates | checkers/a1.py exact-match: all six SKUs with correct unit_price, quantity, warehouse, shipping.rate/carrier |
| b1 | `/repo` | the unfinished remainder of: file list + per-file GETs + PUTs on the 3 pricing-annotated files + settings rename + README + 1 validate | checkers/b1.py: validate passed, no stale annotations, settings renamed exactly |
| c1 | `/docs` (`/auth` excluded) | the unfetched remainder of: 3 searches + 3 passage reads + 1 validate + 1 package | checkers/c1.py: brief grounded in the three passages, citations, package_id |
| d1 | `/docs`, `/inventory` (`/auth` excluded) | the unfetched remainder of: item list + 6 item reads + 2 passage reads + 1 validate + 1 package | checkers/d1.py: gate ran checks, package_id exists, output object complete |

Primary qualification host: **a1** (inherits token_expiry's recurrence
pattern and mid-run timing; a1 hosted token_expiry in Phase 1).

## 6. Fire counter and parameter draw rules (escrow consumes these)

- **N:** drawn uniform per cell from [40%, 60%] of the task's clean-median
  tool-call count (floored), the Phase 1 mechanical convention. Medians:
  a1 24, c1 12, d1 21 (Phase 1 finals, decisions/manipulation_table_s1_seed1.md);
  b1 uses the rev-2 clean median measured by this session's qualification
  runs (the Phase 1 b1 median predates the rev-2 fixture pack).
- **Q0:** drawn uniform per cell from [8, 14].
- Family designation per task is FIXED by §5 (recorded per cell in the
  escrow file for harness consumption, not varied).

Qualification runs (qseed-901/902/903) used **Q0 = 8, N = 12** on a1 —
values chosen from the spec ranges; the escrowed 1b values are drawn
independently and never seen by the author.

## 7. Qualification criteria (this session's Task 3, mirroring the original nine)

On the primary host (a1), seeds qseed-901/902/903 (distinct namespace;
matrix seeds are NOT drawn from these): 3 clean S1 runs + 3 injected S1
runs. **PASS** = injected S1 fails task validation (or emits wrong output)
in >= 2/3 seeds while clean S1 passes in >= 2/3 seeds. A failed
qualification revises this spec, never the bar.

## 8. Harness integration notes (1b launch; not this session)

- The world hosts the mutation at `world_rev: 2` (RunConfig field, default 1
  preserves byte-identical replay of banked Phase 1 configs).
- The 1b launcher consumes `escrow/holdout_escrow.json` programmatically
  (per-cell seed, N, Q0); the author never opens the file.
- D6 surface derivation and D13 pattern-liveness samples must become
  rev-aware at 1b build time (#7-class instrument fix, regression-evidenced
  and deviation-logged per memo §5(e)).
