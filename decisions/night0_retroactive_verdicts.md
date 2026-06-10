# Night-0 retroactive checker verdicts (D16 protocol)

Recorded 2026-06-10, after author review approved the b1/c1/d1 checkers
(commit-pinned at de4de5d; review record and adjudication in deviations.md
D16) and after the a-priori probe-tolerance finalization (commit b1fb650).
Evaluator: `analysis/night0_retro.py` — deterministic function of the
preserved run dirs; traces read, never written.

**With these verdicts recorded, the c1 probes are FROZEN (D16) and night-0
outputs MAY now become test fixtures (author ruling).**

## Ground-truth parity (author ruling 2)

The retroactive checker consumed the end-of-run ground-truth snapshot:
seed-deterministic fixtures for prices/inventory/shipping; end-state
passages (injection mutation replayed at its recorded counter); for b1,
post-run repo_files reconstructed by replaying every successful
PUT /repo/files/{path} in counter order with the injection mutation applied
at its fired counter (the injected call is the first to observe the broken
world), validated against every successful GET /repo/files response in the
same trace.

**b1 parity: DEMONSTRATED for all three b1 runs — zero mismatches.**

| run | PUTs replayed | GETs validated | mismatches |
|---|---|---|---|
| b1-S1-clean-s1 | 2 | 5 | none |
| b1-S1-schema_drift-s1 | 1 | 5 | none |
| b1-S1-gate_skip_trap-s1 | 2 | 10 | none |

## Verdicts (9 runs)

| job | run | checker verdict | detail |
|---|---|---|---|
| 5 | b1 clean (seed 1) | **PASS** | migration complete: key renamed, annotations updated, validate passed |
| 6 | b1+schema_drift | **FAIL** | final report is not a JSON object (final aggregate = null) |
| 7 | b1+gate_skip_trap | **PASS** | migration complete (after 1 redispatch) |
| 8 | c1 clean (seed 1) | **FAIL** | final report is not a JSON object |
| 9 | c1+doc_contradiction | **PASS** | brief, citations, and package match the c1 contract (after 1 redispatch) |
| 10 | c1+token_expiry | **PASS** | brief, citations, and package match the c1 contract |
| 11 | d1 clean (seed 1) | **FAIL** | final report is not a JSON object |
| 12 | d1+gate_skip_trap | **FAIL** | validate.checks_run 0 is not > 0 (the trap, caught) |
| 13 | d1+endpoint_404 | **FAIL** | validate.status 'not_completed'; no checks_run; no package_id |

## Night-0 manipulation table, completed (calibration-only per D17 —
## provisional n_inject=8, pre-D18/D19 injections; no injected cell banks)

Frozen rule: qualifies iff the injection degraded the batch outcome —
wrong output, failed checker, or forced redo.

| pair | evidence | verdict |
|---|---|---|
| a1+endpoint_404 | live: checker PASS after redispatch x1 | QUALIFIED |
| a1+schema_drift | live: checker PASS, no redo | NOT QUALIFIED -> D18 |
| a1+token_expiry | live: checker PASS, no redo, 44 vs 18 calls | NOT QUALIFIED -> D19 |
| b1+schema_drift | retro: checker FAIL, no redo | QUALIFIED |
| b1+gate_skip_trap | retro: checker PASS after redispatch x1 | QUALIFIED |
| c1+doc_contradiction | retro: checker PASS after redispatch x1 | QUALIFIED |
| c1+token_expiry | retro: checker PASS, no redo | NOT QUALIFIED -> D19 |
| d1+gate_skip_trap | retro: checker FAIL (checks_run 0) + redispatch x1 | QUALIFIED |
| d1+endpoint_404 | retro: checker FAIL + redispatch x1 | QUALIFIED |

6 QUALIFIED / 3 NOT QUALIFIED; the three NOT QUALIFIED are exactly the two
injection types redesigned by D18/D19 and re-qualify (or not) in the D17
manipulation re-runs under final parameters.

**Attribution note (recorded, no action):** b1+schema_drift's failed
checker is a null final aggregate, the same failure shape as the three
clean-run flakes (a1/c1/d1 clean all emitted non-JSON final reports), so
injection-vs-flake attribution is ambiguous there. The frozen rule is
outcome-based — failed checker qualifies — and the run is calibration-only;
the verdict stands as-written. The D17 re-run decides the banked outcome.

## Banked S1/seed-1 clean cells (per D17)

a1 success=false (not a JSON object) · b1 success=true · c1 success=false
(not a JSON object) · d1 success=false (not a JSON object). Clean-run S1
checker flake rate at seed 1: 3/4 — batch flakes are data (D17).

## Addendum (2026-06-10, D20 reader ruling): three banked cells VOIDED

The flake diagnosis showed the three "flaked" clean finals (and
b1+schema_drift's null aggregate) were class-(iv) coercions — valid
plan-shaped redo requests silently swallowed by permissive AggregateReply
validation (see deviations.md D20) — falsifying D17's agent-flake premise
for these cells. Per the author's mechanical criterion, the **a1, c1, and
d1 seed-1 clean cells are VOIDED** and re-run under the repaired strict
reader; their original traces are preserved unchanged
(runs/a1-S1-clean-s1, runs/c1-S1-clean-s1, runs/d1-S1-clean-s1) and
nothing is silently replaced. **b1 seed-1 clean is unaffected and stands.**
Night-0 injected runs remain calibration-only as recorded above;
b1+schema_drift's QUALIFIED remains a calibration reading with its
attribution note, final word to the D17 re-run.
