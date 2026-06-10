# Completed manipulation table — S1/seed-1, final parameters (D17 re-runs)

Recorded 2026-06-11. Runs executed under: final per-task n_inject from the
n=3 clean medians (frozen 50% rule, fraction floored per the pre-committed
D17 rule — it bit once, d1: 21 -> 10.5 -> 10); the D18 non-self-describing
pricing drift and D19 hard token expiry; the D20 strict reply reader; the
D21 launcher guard and void-run invariant. Queue jobs 36-44; one run per
pair, seed 1, counter-triggered injections only (amendment 3).

Frozen qualification rule (protocol §4): a pair qualifies only if the
injection degrades the batch outcome — wrong output, failed checker, or
forced redo.

## Final n_inject (mechanical)

a1: median 24 -> 12 · b1: median 8 -> 4 · c1: median 12 -> 6 ·
d1: median 21 -> 10.5 -> 10 (floored)

## The table: 9/9 QUALIFIED

| pair | n_inject | fired | post-injection | redo | checker | verdict |
|---|---|---|---|---|---|---|
| a1+endpoint_404 | 12 | @12, counter | 404 observed | x1 | FAIL (unit_price None for all SKUs) | **QUALIFIED** |
| a1+schema_drift | 12 | @12, counter | drifted payload (+405 probe) | x1 | PASS after forced redo | **QUALIFIED** |
| a1+token_expiry | 12 | @12, counter | 401; issuance suspended | x1 | FAIL (every SKU missing; 48 calls) | **QUALIFIED** |
| b1+schema_drift | 4 | @4, counter | drifted settings | x1 | PASS after forced redo | **QUALIFIED** |
| b1+gate_skip_trap | 4 | @4, counter | silent-success gate | x1 | PASS after forced redo | **QUALIFIED** |
| c1+doc_contradiction | 6 | @6, counter | contradicted passage | x1 | FAIL (30-day premise probe caught it) | **QUALIFIED** |
| c1+token_expiry | 6 | @6, counter | 401; issuance suspended | x1 | FAIL (premise probes; 38 calls) | **QUALIFIED** |
| d1+gate_skip_trap | 10 | @10, counter | 422 + silent-success gate | x1 | FAIL (no title/citations) | **QUALIFIED** |
| d1+endpoint_404 | 10 | @10, counter | 404 on /docs/package | x1 | FAIL (no validate report, no package) | **QUALIFIED** |

Every injection fired exactly at its task's final n_inject via the counter
path. Every pair forced at least one redo (degradation under the frozen
rule even where the checker eventually passed). The three night-0
NOT QUALIFIED pairs requalified exactly as the redesigns intended:
D18's non-self-describing drift forced a redo where night-0's batch
shrugged off `price_cents`; D19's hard expiry turned both token_expiry
pairs from silent self-recovery into failed checkers.

## Banked cells (matrix accounting per D17/D20)

- S1 seed-1 injected: these 9 runs (jobs 36-44). Night-0 injected runs
  remain calibration-only.
- S1 clean: seed-1 a1/c1/d1 = the D20/D21 re-runs (jobs 33-35) + b1
  original; seeds 2-3 = jobs 25-32. 10/12 clean cells PASS; a1-s2 and
  d1-s3 are honest agent failures with full checker evidence (stand per
  D17).
- Matrix progress: 21 of 195 cells banked (all of S1 except injected
  seeds 2-3). Nothing beyond the S1/seed-1 slice has run.

## D20 reader, first production statistics

Across the 20 banked runs: 10 reply_rejected events, 10 first-re-prompt
recoveries, 0 reply_schema_violation failures. The dialect-error class is
real, frequent (~1 in 2 runs), and fully absorbed by the strict
reader + fixed re-prompt.

## Gate status

The all-QUALIFIED precondition for running any other matrix cell is MET.
Scheduling of the remaining 174 cells awaits the author's ruling.
