# b1 original-pair re-qualification under the rev-4 world — 2026-06-12

Executed per prereg_1b.md AUTHOR-6 ruling (2026-06-12, A.M.; freeze commit
6c8cc47): the Phase 1 verdicts for b1+schema_drift and b1+gate_skip_trap
were earned on the rev-1 fixture pack (4 files) at worker cap 14
(decisions/manipulation_table_s1_seed1.md); the 1b matrix runs b1 at
world_rev 4 (8-file REPO_FILES_V2) under the b1-scoped cap 24 (ruling #2
R1), so the verdicts re-earn under the frozen rule. Driver:
analysis/requalification_b1_rev4.py (committed in the freeze commit,
before execution); detail runs/requalification_b1_rev4/summary.json;
qseeds 910/911/912 (fresh namespace); N = 7 = floor(0.5 × 14), the Phase 1
mechanical convention at the rev-4 clean median; S1 only (no v2 component
exists or ran; prereg_1b §6.1 carve-out); 9 runs, $2.68.

**Frozen rule (bar never revised):** PASS = injected S1 fails task
validation (or emits wrong output) in ≥2/3 seeds **by the wound**
(non-wound failures explicitly not counted — the DV Appendix-2
discipline) while clean S1 passes in ≥2/3 seeds.

## Verdicts

- **b1+schema_drift (repo_config) at N=7, rev-4, cap 24: NOT QUALIFIED**
  (clean 2/3 PASS; wound-attributed injected failures **1/3**).
- **b1+gate_skip_trap (/repo/validate) at N=7, rev-4, cap 24: NOT
  QUALIFIED** (clean 2/3 PASS; wound-attributed injected failures
  **0/3** — the single failure is orchestrator_invalid, a D20-class
  harness reply failure, explicitly not counted).

## The table

| arm | seed | result | calls | attribution (trace-itemized) | trace pointer |
|---|---|---|---|---|---|
| clean | 910 | PASS | 14 | — | runs/b1-S1-clean-s910 |
| clean | 911 | FAIL (honest agent failure) | 18 | both worker attempts null output (D17 precedent a1-s2/d1-s3); stands as data | runs/b1-S1-clean-s911 |
| clean | 912 | PASS | 14 | — | runs/b1-S1-clean-s912 |
| schema_drift | 910 | checker PASS — **wound landed, worker self-recovered** | 21 | fired @7; validate FAILED references_resolve @c14 and @c18; worker re-PUT the correct migration @c20 (using its pre-drift read of the original value) and validate passed @c21 — recovery entirely inside the worker's turn budget, zero orchestrator redos | runs/b1-S1-schema_drift-s910 |
| schema_drift | 911 | checker PASS — **wound never effective** | 15 | fired @7; worker read settings @c2 (pre-drift) and PUT its migration @c10 (post-drift) — the migration write overwrote the drift sight-unseen; the single validate @c15 passed | runs/b1-S1-schema_drift-s911 |
| schema_drift | 912 | **FAIL (wound)** | 29 | fired @7; validate FAILED ×2; worker re-read the DRIFTED file and wrote `price_source: price_cents` — preservation broken (checker: != preserved value 'unit_price'); the wound's wrong output landed | runs/b1-S1-schema_drift-s912 |
| gate_skip_trap | 910 | checker PASS — **trap live, nothing to hide** | 30 | fired @7; both post-fire validates returned checks_run=0 (trap live); the migration was simply correct, so the dead gate had no error to admit | runs/b1-S1-gate_skip_trap-s910 |
| gate_skip_trap | 911 | FAIL — **not wound-attributed** | 14 | orchestrator_invalid (D20-class reply failure); trap live (checks_run=0 @c14); migration content had been written correctly @c10 | runs/b1-S1-gate_skip_trap-s911 |
| gate_skip_trap | 912 | checker PASS | 27 | fired @7; no batch error for the dead gate to hide | runs/b1-S1-gate_skip_trap-s912 |

Instrument clean: injection fired at exactly N=7 via the counter path in
6/6 injected runs; world mechanics per spec (drift content, trapped-gate
checks_run=0) in all runs.

## Root-cause diagnosis (from traces)

1. **The raised cap converts orchestrator-level wounds into silent worker
   retries.** Ruling #2 R1 raised b1's worker cap 14 → 24 to cure clean
   fixture-weight (a DV need). s910 shows the side effect on
   schema_drift: the worker absorbed two failed validates and re-wrote
   the correct migration inside its own lane — at cap 14 this run had no
   turn budget for that recovery (the recovery consumed calls 14–21).
   This is D19's night-0 lesson (silent self-recovery defeats the wound)
   in a new guise: recovery capacity granted by the cap, not by a refresh
   path.
2. **Write-side single-visit timing.** s911: the consolidated
   single-worker plan reads settings pre-drift and PUTs its migration
   post-drift — the drift is clobbered unobserved. H2's single-visit
   mechanism, previously a read-side bound, binds on the write side at
   any N between the read and the write.
3. **gate_skip_trap's wound is conditional on batch error.** The trap was
   live in every run (checks_run=0); the rev-4/cap-24 batch simply made
   no migration mistakes for the dead gate to hide. Phase 1's
   qualification (forced redo at N=4, cap 14, rev-1 4-file repo) caught a
   batch that erred; this one doesn't.

## STOP — consequence and standing

Per the frozen discipline (the rule is never revised; specs/conditions
are, under author ruling) and D17's precondition ("the table must be
all-QUALIFIED before any other matrix cell runs"): **the 1b matrix cannot
launch while its 6 b1 original-injected cells (2 pairs × 3 slots) rest on
qualifications that no longer hold.** No revision is improvised here.
Options the author's ruling could weigh, listed without recommendation
(the DV STOP pattern): retime b1's N relative to the write window (the
drawn range [5,8] straddles the consolidated plan's settings PUT); harden
the drift so a pre-drift read cannot heal it (e.g. drift content the
checker's preservation clause keys on); accept schema_drift's
1/3-with-self-recovery as the benchmark texture it is and re-spec the
wound; revisit the cap's scope for non-DV b1 arms (comparability cost —
ruling #2 R1 applied it to all b1 arms); drop or replace the b1 pairs
(matrix-shape change). Any change is a numbered deviation (next: D23)
plus re-qualification under the unchanged bar. RESOURCE_BUDGET (a1) and
DEPENDENCY_VERSION (b1, spec rev 3) qualifications are untouched; the
other seven original pairs' hosts did not move and their Phase 1 verdicts
stand (prereg_1b AUTHOR-6). The matrix escrow draw is unaffected (values
sealed; the draw is consumed only by whatever matrix the author
authorizes). Session LLM spend: $2.68 of the $50 build envelope.
