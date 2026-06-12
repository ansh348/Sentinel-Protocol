# DECISION MEMO — Sentinel Protocol Phase 1
**Author:** Ansuman Mullick. **Window:** opened 2026-06-11 with the gate
display; this memo executes within 48 hours, per prereg.
**Inputs of record:** decisions/kill_gates_final.md;
analysis/archaeology_v1.md (commit 8d5a864); decisions/external_review_gpt55_pro.md
and external_review_gemini31_pro.md;
decisions/phase1b_precommitments.md (commit 823549e, pre-results);
analysis/archaeology_v2.md (commit 508772f); dev-run ledger;
sentinel_protocol_v6_1.md. Exact hashes: kill_gates_final.md b7d6b18 ·
archaeology_v1.md 8d5a864 · rater_adjudication_principle.md ed50079 ·
external reviews (both, verbatim ingest) a9143b7 ·
phase1b_precommitments.md 823549e (committed before any battery result) ·
archaeology_v2.md + candidate D22 508772f · dev-run ledger opened a9143b7,
entries through 94307ff · battery commits c697e47 (Phase 0 byte-identity),
6edb5ad (Task A), d6f82df (Tasks B+D), 2b12f5b (Task E), 94307ff (Task C),
83575e7 (Task F).

## 1. Verdict — stands as printed
KG1 FAIL (strict recall 35%, kill band; 1/5 categories ≥50%). KG2 FAIL
(S5 FIR 1.0). KG3 FAIL (clean overhead OVER 12%). KG4 PASS via TTD
(median 3 vs 9; 3× vs 2× bar). Computed once on the complete 195-cell
matrix; attribution audit 13/13. Nothing in this memo recomputes,
re-scores, or reinterprets any gate quantity.

## 2. Pre-committed branches — resolved
- **KG1 (<40% kill):** the v1 detection claim is killed; the flagship as
  originally conceived is dropped. Continuation is solely the Phase 1b
  path under fresh pre-registration (§5).
- **KG2:** two-tier (no-judge) ratified as the designated primary
  architecture (pre-commitment P3, in ink before battery results; judge
  corpus record per archaeology v2 G16). Rebuilt judge = exploratory arm
  only. No post-selection.
- **KG3:** break-even fit executed with the model form committed before
  fitting. Result: NO crossover at any fan-out (ΔW = −$0.072; P = 1.00
  over 1,000 bootstraps). **The v1 efficiency claim is killed.** Any v2
  efficiency claim must be earned from scratch with probe overhead
  booked as waste; the full study's measured fan-out arm is its only
  legitimate vehicle.
- **KG4:** the TTD result (3×) survives and stands alone, decoupled
  from any savings claim.

## 3. Adjudication of the external red-team — accepted as ruled
The archaeology-v2 battery's G-table (18 trace-testable [FATAL]/[MAJOR]
claims, each with trace pointers) is adopted in full. Highlights bound
into design: rival stories A and D refuted; B and C partial — the
observation bound was self-inflicted (baselines re-visited starved
surfaces 12/12; 7/12 noise-consumed); dead-pattern class confirmed (84
patterns, 19 covering, 8 cells) — v1's "one matcher defect" claim is
corrected by erratum; second-signal corroboration clause broken (6/18
false self-corroborate) and DELETED; probe-primary adopted (18/18 false
blocked, projected recall unchanged); status fast path validated; probe
perturbation vectors (3) and probe overhead (2,322 vs 107 calls)
measured. Design-level claims dispositioned per the binding-red-team
rule (every [FATAL]/[MAJOR] → clause or written waiver):
- Probe staleness → CLAUSE: probes recompile on every replan; freshness
  is an audited probe-validity criterion (§4).
- Calibration leakage → PARTIAL WAIVER: Phase 1 posteriors enter v2 only
  as weakly-informative priors, labeled exploratory; no gate consumes
  them. Rationale: passive-paradigm data cannot calibrate an
  active-paradigm system (Gemini), but discarding all signal is worse.
- Abort economics → CLAUSE: recovery-quality gate (§4); aborts counted
  separately and cannot satisfy parity.
- Five-R coarseness → WAIVER with mitigation: primary recovery_class
  retained; optional secondary hint permitted, exploratory.
- Tiered compilation (#8) → DESCOPED from 1b (convergent FATALs);
  full-study exploratory arm.
- Protocol attacks (thresholds, embargo, ledger, arm selection, holdout)
  → EXECUTED via P1–P3, the standing dev-run ledger, the data embargo,
  and §5's escrowed held-out categories.
- Novelty attacks → EXECUTED in v6.1 (§2, §9.3.1, §10): RVPLAN
  confronted; claims narrowed; "laws" reframed as findings.
- Delta-FIR (Gemini) → reported descriptively alongside absolute caps;
  gates remain absolute per H5.

## 4. Phase 1b gate values — RATIFIED ON COMMIT of this memo
Structures and rationales per phase1b_precommitments.md (823549e);
values attach to those structures; where wording differs, the committed
rationale text governs. Per P1, shared quantities inherit v1's
pre-verdict thresholds verbatim and derive from nothing the battery
reported.
- **1bKG1 (detection):** strict recall ≥60% on recoverable-class cells;
  ≥50% in ≥4/5 categories (reported with Wilson lower bounds; any
  category with n<3 is descriptive only); kill floor <40%. Probe
  validity is a HARD gate: a seeded 20% audit of probe-generated
  interrupts must show 100% targeted/fresh/non-perturbing/independent;
  any failure excludes that interrupt class from recall before the gate
  computes. Recovery quality: detect-only, detect-and-recover,
  detect-and-justified-abort counted separately; ≥50% of strict
  detections must be the latter two. Held-out categories (§5) are
  inside the recall denominator.
- **1bKG2 (noise/self-harm), absolute caps:** clean-cell median FIR = 0;
  P95 ≤ 1; max false interrupts per clean cell ≤ 3; zero escalation-cap
  grinds on clean cells (hard). Pre-detection false-interrupt budget on
  injected cells: median ≤ 2 before first true detection. **Clean
  success: absolute floor ≥ 60% AND ≥ (S1 clean − 10 points).
  (Ratified: 60/10, A.M.)**
- **1bKG3 (economics):** clean overhead ≤ 12% (inherited), probe costs
  included in waste. Primary view unamortized per-run; amortized view
  reported descriptively over a pre-specified 10-task repeated-plan
  workload. No crossover-plausibility gate (resolved against v1; full
  study carries the claim).
- **1bKG4 (vs heartbeat):** TTD ≥ 2× (inherited) AND wasted-work
  parity-or-better vs cost-matched S3 with probe costs included.
  Sensitivity row: undetected cells censored at run end.
- **Standing:** instrumentation-integrity replay (Task-A pattern) runs
  on 100% of injected 1b cells BEFORE gates compute; S2 is a mandatory
  head-to-head arm with an honesty clause (if S2 dominates v2 on
  recall at ≤ FIR, the paper says so in the results, not a footnote).

## 5. Phase 1b — AUTHORIZED, conditional on (all):
(a) thresholds above frozen by this commit, before any v2 build code;
(b) held-out categories RESOURCE_BUDGET and DEPENDENCY_VERSION authored,
manipulation-qualified, seeds escrowed with a non-implementer (advisor
or co-founder) before the v2 build begins; (c) data embargo + dev-run
ledger standing — no benchmark-world output observed pre-freeze;
(d) v2 build scope = §11.9 as amended in v6.1 (#1 side-channel +
event-gated cadence with guaranteed pre-completion sweep; #2
probe-primary; #6 two-tier primary; #7 dead-pattern-class fix with
pattern-liveness regression; #8 descoped); (e) instrument fixes (#7
class) regression-evidenced and deviation-logged.

## 6. Schedule kill gates — pre-committed
- **Gate 1 (battery decisive): PASSED 2026-06-12.**
- **Gate 2:** Phase 1b verdict in hand by 2026-07-18 23:59, else the
  FSE submission retargets per §13 fallbacks (NIER Oct 23 / SEAMS /
  ASE 2027). No extension may be granted by the author to the author.
- **Gate 3:** **≥ 50 validated onboarded real-suite tasks by
  2026-08-31** (Ratified: 50, A.M.), else descope (30–49: single-suite
  study; <30: retarget ASE 2027).

## 7. Standing orders
Product launch (Jul 15) outranks the matrix; queue pauses losslessly.
v1's verdict appears in the paper regardless of v2's outcome. Deviation
log continues (next: D23). Matrix-close checklist executes after this
memo's commit. Erratum discipline: corrected claims stay visible with
their errata (v6.1 §11.7 pattern).

## Appendix A — forecast ledger (for calibration accounting, no force)
Author's advisor-model pre-battery: detection 55–65 → post 65–70;
clean 80–85 (risk shifted to probe-injury); economics 55–60 → 40–45
(now binding); all-gates 30–35. External: GPT 40/48/30/11;
Gemini 15/40/25/5 (recall forecast refuted by shadow replay).

## Appendix B — H2–H4, H6 verbatim from archaeology_v1.md

> - **H2 — Single-visit surfaces are unobservable at 50%-of-median.**
>   c1's passages are fetched once, early; by n_inject the surface is cold
>   (c1-S5-doc_contradiction-s2). v2: injection timing as an explicit
>   variable, or tripwires that trigger re-validation touches of declared
>   assumptions (active probing), not just passive matching.
> - **H3 — True matcher miss on status-class signals.**
>   a1-S5-token_expiry-s1: seven 401s observed under an armed covering
>   tripwire, zero fires. Inspect that tripwire's compiled url_pattern vs the
>   401-bearing paths (D5/D8 dialect family suspect). One-cell evidence;
>   verify before generalizing.
> - **H4 — Judge credulity on field-class evidence.** All 34 interrupts were
>   GENUINE; 18 unattributable, 14 of those on field-absence/shape evidence.
>   v2: judge prompt receives the field's clean-run baseline value and the
>   D9 excerpt; field-absence without a status anomaly defaults NOISE
>   (mirrors the author's KG0 adjudication principle: WARNING defensible iff
>   data recoverable).
> - **H6 — D15 carryover arrives too early to help.** In both replan-churn
>   clean deaths, completed_results was empty at interrupt time (carryover
>   sizes [0] and [0,0]) — the mechanism worked but had nothing to carry;
>   the cost of replanning was repaid with nothing. v2: defer non-critical
>   interrupts to wave boundaries so carryover is non-empty, or batch
>   interrupts.

(Archaeology-v2 cross-references, recorded beside the verbatim text without
altering it: H2's single-visit mechanism is refuted for c1-S5-doc_contradiction-s2
itself — the passage was fetched only POST-injection, at counters 9 and 33
(archaeology_v2 §A.2 erratum 1); H3's "verify before generalizing" resolved:
CLASS, not singleton (§A.3).)

## Appendix C — S2 per-category head-to-head (archaeology_v2 Task F)

| | overall | API_SURFACE | SCHEMA_DRIFT | PERMISSION_AUTH | TOOL_CONTRACT | RETRIEVAL_INTEGRITY |
|---|---|---|---|---|---|---|
| **S2** | **15/27 (56%)** | 5/6 | 2/6 | 6/6 | 2/6 | 0/3 |
| **S5** | 9/27 (33%) | 2/6 | 1/6 | 5/6 | 1/6 | 0/3 |

S2 median FIR 0.0; no compile or judge overhead. Source:
runs/archaeology_v2/baseline_breakeven.json (per-cell rows included);
instrument rule (first attributable pause) mirrored exactly.

**Signature:** committing this file to the repository constitutes the
author's ratification of every value herein, within the 48-hour window.
— Ansuman Mullick, signed 2026-06-12.
