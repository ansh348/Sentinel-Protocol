# Phase 1b pre-commitments — committed BEFORE any archaeology-v2 (A–G) result is read

Written 2026-06-11/12 (UTC), immediately after Phase 0 orientation (byte-identity
27/27, commit c697e47) and before any Task A–G analysis was executed or read.
Inputs to this file: prereg.md (frozen), decisions/kill_gates_final.md (final),
analysis/archaeology_v1.md (commit 8d5a864), the two external reviews
(decisions/external_review_*.md, commit a9143b7), sentinel_protocol_v6.md
§11.9–§11.10, and decisions/heartbeat_k_calibration.md (commit fd21d9a).
NO quantity computed by the A–G battery feeds anything below. Values marked
[freeze] are placeholders the author ratifies at Phase 1b freeze time; this
file pre-commits structure and rationale, never data-derived numbers.

---

## P1 — Inherited thresholds (verbatim, frozen)

Phase 1b inherits v1's frozen thresholds verbatim for all shared quantities:

- Detection recall ≥ 60% overall; ≥ 50% in ≥ 4 of 5 categories; kill floor 40%
  (prereg 6.2 KG1, unchanged).
- TTD ≥ 2× vs the cost-matched heartbeat (prereg 6.2 KG4 TTD arm, unchanged).

No threshold in this file or in any later Phase 1b freeze may derive from
anything the archaeology-v2 battery reports.

## P2 — New-gate threshold rationales (structure + rationale now; values at freeze)

Each new gate exists because of a wound already on record (archaeology_v1, the
kill-gate table, or a red-team finding); none derives from A–G results.

1. **Clean-run parity (anti-self-injury), absolute form.** S5 clean-cell
   success within [freeze] points of S1 clean AND an absolute clean success
   floor of [freeze]%. Rationale: v1 self-injury (S5 3/12 vs S1 9/12,
   archaeology_v1 §4); H5's lesson that ratio gates against a possibly-weak or
   possibly-quiet comparator are pathological; GPT-5.5 review ("parity can
   pass if S1 is weak") — hence the absolute floor clause.
2. **FIR caps with tail clauses.** Median per-run FIR ≤ [freeze]; P95
   false-fire count per cell ≤ [freeze]; max false-fires per cell ≤ [freeze];
   zero clean-cell escalation-cap grinds (hard clause); time-to-first-false-
   interrupt on clean cells ≥ [freeze] calls. Rationale: the 172-fire storm
   cell (a1-S5-endpoint_404-s1-2) shows a median cap can pass while a tail
   cell destroys a run (GPT "median hides storms"); the five clean
   escalation-cap grinds are the self-injury mechanism.
3. **Pre-detection false-interrupt budget on injected cells** ≤ [freeze].
   Rationale: H1 — false fires before detection consume exactly the lifetime
   detection needs; clean-only FIR caps miss this (GPT "noise on injected
   cells is missing").
4. **Probe-validity gate (hard, not diagnostic).** ≥ [freeze]% of load-bearing
   injected surfaces must have a post-injection probe that an audit classifies
   as targeted / fresh / non-perturbing / independent-of-trigger, with
   semantic-vs-deterministic explicitly marked per probe. Rationale: probes
   are v2's central repair (§11.9 #1); both reviews demand this be primary
   (GPT "missing: active-probe validity gate"; Gemini "probe-induced
   perturbation rate").
5. **Probe perturbation clause.** Probe-induced clean-run failures = 0 (hard);
   probe perturbation rate (world-state mutations or benchmark-clock advances
   attributable to probes) ≤ [freeze]. Rationale: Gemini's missing-gate
   attack; this world already exhibits concrete perturbation vectors by
   construction (POST /docs/validate admits the probed doc to packaging;
   POST /auth/token shifts the seed-derived token stream; every middleware
   request advances the injection-clock counter), so the clause is not
   hypothetical.
6. **Recovery-quality gate.** Detection outcomes counted in three exclusive
   buckets — detect-only, detect-and-recover, detect-and-abort(justified) —
   with [freeze] minimum on detect-and-recover ∪ justified-abort, and abort
   audited against the ex-ante retreat labels (an unjustified abort on a
   recoverable cell never counts toward any gate). Rationale: GPT "TTD + parity
   can pass while the architecture is useless; ABORT is a shortcut to parity";
   detection is not the product.
7. **Probe overhead in the waste column.** 1bKG4's wasted-work clause reads
   (S5 post-invalidation worker tokens + S5 total probe overhead) ≤ [freeze]×S3,
   per Gemini's accounting attack. The archaeology-v2 battery (Task E) emits a
   MEASURED per-cell probe-overhead column (probe calls under the pre-committed
   cadence below) so the freeze-time value is grounded in a measurement, not an
   estimate — the measurement informs the author's ratified value; it does not
   set it mechanically.
8. **Small-n category-clause stabilization.** The per-category clause is
   evaluated on exact-binomial (or Wilson) lower bounds at [freeze] confidence,
   or demoted to descriptive with a per-cell primary gate and stratified
   minimums of [freeze] cells per category. Rationale: GPT "a single cell can
   swing a category" — true by arithmetic at n=3–6 per category.
9. **TTD censoring sensitivity.** Beside median TTD on detected cells, a
   survival-style read assigns undetected cells a run-end censoring value;
   reported as a mandatory sensitivity row [freeze form]. Rationale: GPT
   censoring attack.
10. **Amortization ruled both ways.** Two frozen views: per-run unamortized,
    and amortized over a pre-specified repeated-plan workload of [freeze]
    runs. Rationale: GPT "the rule itself determines viability".

## P3 — Primary arm designation (no post-selection)

Primary Phase 1b arm = **two-tier (no-judge)**, per KG2's pre-committed branch
("Judge adds nothing: reframe as compile-only architecture (two tiers)").
The rebuilt-judge configuration runs as the EXPLORATORY arm. The primary arm
is fixed here, before any 1b data and before the archaeology-v2 battery;
whichever arm "wins" later, the confirmatory claim attaches to the two-tier
arm only. This adopts the identical tightening demanded by both reviews
(post-selection inference).

---

## Pre-committed operationalizations for the archaeology-v2 battery itself

Written before any A–G result; the battery executes these as specified.

### E.1 Corroboration policy (v6 §11.9 #2 made executable)

Evidence classification per escalation/interrupt event (from its evidence
object, mirroring archaeology_v1's classes):

- **status-coded (fast path):** evidence `_status`/`status` present and ≥ 400.
- **field-shape:** any non-underscore evidence field present (incl. declared-
  field nulls) with status < 400 or absent status.
- **all-null:** every non-underscore evidence field is null.
- status=2xx/3xx events are NOT fast-path (the one v1
  status=200-on-untrapped-path false interrupt motivates this boundary).

Policy: a status-coded escalation may interrupt directly (v1 semantics
retained). A field-shape or all-null escalation may interrupt ONLY with
corroboration, defined as either:
  (i) **second independent signal**: another escalation with a different
      tripwire_id AND a different path within W = 10 tool calls (counter
      distance) on either side; W = 10 is chosen a priori (≈ half a short
      task's clean call count); sensitivity reported at W = 5 and W = 20; or
  (ii) **one confirming probe**: the next scheduled probe (cadence below) of
      the SAME surface at/after the escalation's counter returns ANOMALOUS
      (differs from the seed-matched clean baseline).
Variant reported alongside (pre-committed, since (i) may let noise storms
self-corroborate — an anticipated, honestly-reported possibility, not a
post-hoc patch): **probe-primary** corroboration, clause (ii) only.

Two-tier (no-judge) routing for the offline replay: the judge is deleted;
the policy above is the entire interrupt filter; CRITICAL severity changes
nothing unless the evidence class says so (severity is compiler-assigned and
was not a reliable signal in v1).

### E.2 Mechanical probe definitions (zero-LLM; derived ONLY from armed
tripwire targets + seed-matched clean-world baselines — both compile-time-
knowable; the injections' identities are NOT inputs to probe construction,
only the tripwire-declared surfaces are)

Per armed tripwire with a resolvable surface, one probe:

- **Status probe** (tripwires whose signal gates on a url_pattern + status):
  GET (or HEAD-equivalent) the tripwire's covered concrete route (instantiated
  per D13 path-sample derivation); ANOMALOUS iff status differs from the
  seed-matched clean baseline status.
- **Auth probe** (auth_state tripwires): GET /auth/validate presenting the
  most recently observed bearer token; ANOMALOUS iff 401 where clean baseline
  is 200.
- **Schema fingerprint probe** (field_absent/field_regex tripwires on
  API payloads): GET the covered route; fingerprint = sorted (key:type) set of
  the JSON payload; ANOMALOUS iff fingerprint differs from clean baseline.
- **Anchored-content fingerprint probe** (retrieval_content /
  contradicts_assumption tripwires): GET the covered passage;
  ANOMALOUS iff sha256(content) differs from the clean baseline hash.
- **Gate-field re-read probe** (order_violation / gate-status tripwires):
  re-invoke the gate with a fixed synthetic sentinel document/payload that is
  DELIBERATELY INVALID (fails ≥ 1 check by construction); read
  (status, checks_run); ANOMALOUS iff status == "passed" with checks_run == 0
  (a gate that passes an invalid sentinel without running checks is
  skip-trapped). Read-only caveat recorded honestly: /repo/validate is pure;
  /docs/validate admits the sentinel key to validated_docs (no worker-visible
  effect; counted under the perturbation column).

**PROBE-UNCOVERED rule:** if no armed tripwire (any arming epoch) covers the
injected surface on paper (archaeology.covers_on_paper), the cell is reported
as PROBE-UNCOVERED — probes inherit Law 1 (information-bounded compilation;
GPT 1c). The PROBE-UNCOVERED count is itself a deliverable, not a skip.

### E.3 Probe cadence + overhead column (pre-committed)

Cadence: one probe sweep every k tool calls, k = the task's committed
heartbeat-k (decisions/heartbeat_k_calibration.md: a1=2, b1=21, c1=4, d1=5)
— "the heartbeat's cadence at tripwire prices" taken literally, anchored to
an artifact committed before this battery. Sweeps occur at counters that are
multiples of k after first arming; each sweep executes every defined probe
once. Per-cell probe-overhead column = (number of sweeps within the run's
actual recorded lifetime) × (probes per sweep), reported both run-total and
post-injection-only. Probe-TTD = counter distance from injection to the first
sweep whose injected-surface probe returns ANOMALOUS (∞ if the run ends
first or the cell is PROBE-UNCOVERED).

### F.1 KG3 break-even model form (written BEFORE fitting; per KG3's branch)

Inequality (v6 §11.4): pay iff  C + J + p·R < p·(W_batch − W_sent),
with W ~ n·h·burn_rate.

Estimators (fixed now): C = median S5 per-run compile cost (compile-event
usage, incl. recompiles); J = median S5 per-run judge cost (judge_verdict
usage); R = median per-replan orchestrator+recompile cost over S5 runs with
replans; W_batch = median S1 injected-cell wasted-work USD (instrument
definition, metrics.wasted.usd); W_sent = median S5 injected-cell wasted USD.
Pilot fan-out n₀ = 3, horizon h₀ = per-task clean median calls; burn = median
worker cost per call. Scaling: W_x(n) = W_x(n₀)·(n/n₀) at fixed h (the v6 form
W ~ n·h·burn with h held at pilot values). Crossover n* = smallest integer n
with C + J + p·R < p·(W_batch(n) − W_sent(n)), computed at p ∈ {0.1, 0.25,
0.5}. Uncertainty: nonparametric bootstrap over cells, 1000 resamples, 90% CI
on n*. Acceptance rule (KG3 branch wording): "plausible crossover at fan-out
≤ 8" iff n* ≤ 8 at some p ≤ 0.5 using pilot-measured C, J, R with the CI lower
bound finite. Anything else = no plausible crossover.

### A.1 Raw-replay reading discipline (Task A)

The raw replay arms each run's recorded tripwire_set(s) fresh (per arming
epoch, segmented by tripwire_set event timestamps; union-of-epochs reported as
the generous variant) and evaluates the recorded post-injection
(method, path, status, body) stream. Live D11 cooldown/suppression state is
NOT replicated in the replay; instead the live suppressed_refire log is
cross-referenced so "raw evidence existed, never fired" separates cleanly from
"fired live but suppressed" (L3-class). Any resulting L2↔L3 reclassification
is a FINDING in archaeology_v2.md — never a correction of archaeology_v1, the
chain-of-death table, or any gate quantity. Both pointer dialects run (live
and STRICT_POINTERS) for the D8 ablation.

### D.1 Horizon-analysis exclusion (Task D)

The L0 cell (b1+gate_skip_trap/s1) died before its injection counter was ever
reached: it is horizon-unanalyzable by construction and is excluded from Task
D with this one-line note.

---

*Committed before any A–G analysis output existed; see the dev-run ledger
(analysis/dev_run_ledger.md) for the complete execution record.*

---

## RATIFIED VALUES (2026-06-12)

Ratified by the author via decisions/decision_memo_phase1.md §4 (signature
clause: the memo's commit constitutes ratification, within the 48-hour
window). Values attach to the P2 structures above; where wording differs,
the committed rationale text above governs. Per P1, shared quantities
inherit v1's pre-verdict thresholds verbatim and derive from nothing the
archaeology-v2 battery reported.

- **1bKG1 (detection):** strict recall ≥60% on recoverable-class cells;
  ≥50% in ≥4/5 categories (reported with Wilson lower bounds; any category
  with n<3 is descriptive only); kill floor <40%. Probe validity is a HARD
  gate: a seeded 20% audit of probe-generated interrupts must show 100%
  targeted/fresh/non-perturbing/independent; any failure excludes that
  interrupt class from recall before the gate computes. Recovery quality:
  detect-only, detect-and-recover, detect-and-justified-abort counted
  separately; ≥50% of strict detections must be the latter two. Held-out
  categories (memo §5: RESOURCE_BUDGET, DEPENDENCY_VERSION, seeds escrowed
  with a non-implementer) are inside the recall denominator.
- **1bKG2 (noise/self-harm), absolute caps:** clean-cell median FIR = 0;
  P95 ≤ 1; max false interrupts per clean cell ≤ 3; zero escalation-cap
  grinds on clean cells (hard). Pre-detection false-interrupt budget on
  injected cells: median ≤ 2 before first true detection. Clean success:
  absolute floor ≥ 60% AND ≥ (S1 clean − 10 points). (Ratified: 60/10,
  A.M.)
- **1bKG3 (economics):** clean overhead ≤ 12% (inherited), probe costs
  included in waste. Primary view unamortized per-run; amortized view
  reported descriptively over a pre-specified 10-task repeated-plan
  workload. No crossover-plausibility gate (resolved against v1; the full
  study carries the claim).
- **1bKG4 (vs heartbeat):** TTD ≥ 2× (inherited) AND wasted-work
  parity-or-better vs cost-matched S3 with probe costs included.
  Sensitivity row: undetected cells censored at run end.
- **Standing:** instrumentation-integrity replay (Task-A pattern) runs on
  100% of injected 1b cells BEFORE gates compute; S2 is a mandatory
  head-to-head arm with an honesty clause (if S2 dominates v2 on recall at
  ≤ FIR, the paper says so in the results, not a footnote).
- **Corroboration policy:** the second-signal clause (E.1 (i)) is DELETED
  per memo §3 (6/18 false interrupts self-corroborated, two on a clean
  cell); the PROBE-PRIMARY variant — pre-committed above as the alternate —
  is the ratified policy. Status fast path retained as operationalized
  (status ≥ 400).
