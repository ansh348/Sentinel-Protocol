# POST-VERDICT ARCHAEOLOGY v1 — EXPLORATORY

**Standing boundary:** the 2026-06-11 KG1–KG4 verdict stands as computed.
Nothing below recomputes, re-scores, or reinterprets any gate quantity.
Every analysis here applies the instrument's own definitions
(`analysis/metrics.py`) per cell, for diagnosis only; outputs feed the
decision memo and the v2 design. Extraction code:
`analysis/archaeology.py` (reads traces only); full structured data:
`runs/archaeology_data.json`. Zero changes to harness, compiler, or
benchmark in this pass.

---

## 0. Protocol 6.1 attribution audit (mandated)

**Domain:** 64 injected cells (of 135 across all systems) contain at least
one `pause` event; the trace rule attributed 37 and refused 27.
**Sample:** 20% (n=13), seed 11 (the project's audit-sampling precedent),
drawn over the pause-bearing injected cells.

| sampled cell | rule | manual | evidence |
|---|---|---|---|
| d1/S2/endpoint_404/s2 | ATTR | AGREE | escalation touch precedes the pause (d1-S2-endpoint_404-s2) |
| d1/S5/gate_skip_trap/s3 | not | AGREE | only surface fire is at counter 98, after the pause (d1-S5-gate_skip_trap-s3) |
| c1/S5/doc_contradiction/s2 | not | AGREE | zero surface touches in the whole run (c1-S5-doc_contradiction-s2) |
| d1/S5/gate_skip_trap/s2 | ATTR | AGREE | fires at counters 11/22 on /docs/validate precede the pause |
| d1/S4/endpoint_404/s1 | not | AGREE | zero surface touches (d1-S4-endpoint_404-s1) |
| d1/S2/gate_skip_trap/s3 | ATTR | AGREE | two pauses; rule attributes pause 2 (escalation 17:07:04 precedes it) |
| b1/S5/schema_drift/s3 | ATTR | AGREE | three fires at counter 4 on /repo/validate precede pause |
| b1/S5/schema_drift/s2 | not | AGREE | zero surface touches |
| b1/S5/gate_skip_trap/s2 | not | AGREE | zero surface touches before either pause |
| d1/S4/endpoint_404/s2 | not | AGREE | zero surface touches |
| c1/S2/token_expiry/s1 | ATTR | AGREE | 401 responses at counters 6–8 precede pause |
| a1/S3/schema_drift/s1 | not | AGREE | no surface-touching event anywhere; pause is heartbeat-driven |
| a1/S2/schema_drift/s3 | ATTR | AGREE | escalation touch precedes pause |

**Result: 13/13 agreement, zero disagreement cases.** The pause-attribution
instrument is **CONFIRMED** as implementing its written rule.

**S2 FIR = 0.0, explained (instrument-confirmed, no deviation):** an
"orchestrator interrupt" is the `interrupt` trace event, emitted by the
conductor immediately before every orchestrator interrupt turn — including
turns the orchestrator then DISMISSES, so dismissals (7 across S2) DO enter
the denominator. Forensics over all 39 S2 cells: 17 runs had interrupts (40
total — 39 on injected cells, exactly 1 on a clean cell); 4 were false
(a1/endpoint_404/s2: 1; d1/clean/s2: 1; d1/gate_skip_trap/s3: 2), giving
per-run FIRs of fourteen 0.0s plus {0.33, 0.67, 1.0} → median 0.0. The
mechanism is S2's design: workers escalate only on observed anomalies;
clean worlds produce almost none, and injected anomalies are
surface-touching nearly by construction. KG2's verdict stands; a
gate-construction observation about the S2 denominator is recorded under
HYPOTHESES (H5).

---

## 1. CHAIN-OF-DEATH TABLE (centerpiece) — S5's 27 injected cells

Links: L0 injection never fired · L1 no covering tripwire compiled ·
L2 compiled, never fired live · L3 fired, suppressed/not escalated ·
L4 escalated, judge ruled NOISE · L5 GENUINE but no pause ·
L6 paused, unattributed. (L0 is an addition to the briefed taxonomy:
one run died before its injection counter was ever reached; the gate's
recall denominator excluded it — gate 35% = 9/26; per-cell 9/27 = 33%.
Same verdict either way.)

| cell | category | link | evidence (run dir) |
|---|---|---|---|
| a1+endpoint_404/s1 | API_SURFACE | **L2** | covered (tw_pricing_quote_accessible et al.); 0 post-inj surface visits — noise storm: 49 pre-inj fires, 172 post-inj non-surface fires, 50 cooldown-suppressed (a1-S5-endpoint_404-s1-2) |
| a1+endpoint_404/s2 | API_SURFACE | **L2** | covered (tw_pricing_endpoint_exists…); zero live surface fires (a1-S5-endpoint_404-s2) |
| a1+endpoint_404/s3 | API_SURFACE | DETECTED | (a1-S5-endpoint_404-s3) |
| a1+schema_drift/s1 | SCHEMA_DRIFT | **L2** | covered (tw_pricing_quote_primary_ok); zero surface fires (a1-S5-schema_drift-s1) |
| a1+schema_drift/s2 | SCHEMA_DRIFT | **L1** | 12 tripwires armed, none cover /pricing drift (a1-S5-schema_drift-s2) |
| a1+schema_drift/s3 | SCHEMA_DRIFT | **L2** | covered (tw_pricing_quote_200, tw_pricing_unit_price); zero surface fires (a1-S5-schema_drift-s3) |
| a1+token_expiry/s1 | PERMISSION_AUTH | **L2** | covered (tw_token_rejected_downstream); **7 observed 401s post-injection, zero fires — true matcher miss** (a1-S5-token_expiry-s1) |
| a1+token_expiry/s2 | PERMISSION_AUTH | DETECTED | (a1-S5-token_expiry-s2) |
| a1+token_expiry/s3 | PERMISSION_AUTH | DETECTED | (a1-S5-token_expiry-s3) |
| b1+schema_drift/s1 | SCHEMA_DRIFT | **L4** | 4 surface escalations; judge NOISE at 0.95 confidence (b1-S5-schema_drift-s1) |
| b1+schema_drift/s2 | SCHEMA_DRIFT | **L2** | covered; zero surface fires (b1-S5-schema_drift-s2) |
| b1+schema_drift/s3 | SCHEMA_DRIFT | DETECTED | (b1-S5-schema_drift-s3) |
| b1+gate_skip_trap/s1 | TOOL_CONTRACT | **L0** | replan_loop death before counter 4 ever arrived (b1-S5-gate_skip_trap-s1) |
| b1+gate_skip_trap/s2 | TOOL_CONTRACT | **L2** | covered (tw_validate_post_200…); 0 post-inj /repo/validate visits; 150 non-surface fires, 46 suppressed (b1-S5-gate_skip_trap-s2) |
| b1+gate_skip_trap/s3 | TOOL_CONTRACT | **L2** | covered; zero surface fires (b1-S5-gate_skip_trap-s3) |
| c1+doc_contradiction/s1 | RETRIEVAL_INTEGRITY | **L4** | 1 surface escalation; judge NOISE at 0.75 (c1-S5-doc_contradiction-s1) |
| c1+doc_contradiction/s2 | RETRIEVAL_INTEGRITY | **L2** | covered (tw_pol_returns_status…); passage never re-fetched post-injection — single-visit surface (c1-S5-doc_contradiction-s2) |
| c1+doc_contradiction/s3 | RETRIEVAL_INTEGRITY | **L3** | 4 surface fires (tw_passage_text_schema) never escalated; 5 cooldown installs in run (c1-S5-doc_contradiction-s3) |
| c1+token_expiry/s1 | PERMISSION_AUTH | DETECTED | (c1-S5-token_expiry-s1) |
| c1+token_expiry/s2 | PERMISSION_AUTH | DETECTED | (c1-S5-token_expiry-s2) |
| c1+token_expiry/s3 | PERMISSION_AUTH | DETECTED | (c1-S5-token_expiry-s3) |
| d1+gate_skip_trap/s1 | TOOL_CONTRACT | **L2** | covered (tw_validate_200…); zero surface fires (d1-S5-gate_skip_trap-s1) |
| d1+gate_skip_trap/s2 | TOOL_CONTRACT | DETECTED | (d1-S5-gate_skip_trap-s2) |
| d1+gate_skip_trap/s3 | TOOL_CONTRACT | **L3** | 1 surface fire never escalated; 12 suppressed_refires, 6 cooldown installs (d1-S5-gate_skip_trap-s3) |
| d1+endpoint_404/s1 | API_SURFACE | **L2** | covered; 0 post-inj /docs/package visits — pipeline collapsed upstream of the dead surface (d1-S5-endpoint_404-s1) |
| d1+endpoint_404/s2 | API_SURFACE | **L2** | covered (tw_package_conflict_409…); zero surface fires (d1-S5-endpoint_404-s2) |
| d1+endpoint_404/s3 | API_SURFACE | DETECTED | (d1-S5-endpoint_404-s3) |

**Rollup — misses per link (18 misses):**
L0: 1 · L1: 1 · **L2: 12** · L3: 2 · L4: 2 · L5: 0 · L6: 0

**Per category per link:**
- API_SURFACE (2/6 detected): L2 ×4
- SCHEMA_DRIFT (1/6): L1 ×1, L2 ×3, L4 ×1
- PERMISSION_AUTH (5/6): L2 ×1 (the true matcher miss)
- TOOL_CONTRACT (1/6): L0 ×1, L2 ×3, L3 ×1
- RETRIEVAL_INTEGRITY (0/3): L2 ×1, L3 ×1, L4 ×1

**L2 decomposition (the probe that matters):** of the L2 cells probed,
most are **surface starvation**, not matcher failure — the run never
re-touched the injected surface after the injection: (a) noise-storm
starvation (a1-S5-endpoint_404-s1-2: 172 post-injection fires on OTHER
surfaces, 50 cooldown suppressions, escalation-cap death before any worker
revisited pricing); (b) upstream collapse (d1-S5-endpoint_404-s1: the
pipeline never reached packaging, so the dead /docs/package was never
called); (c) single-visit timing (c1-S5-doc_contradiction-s2: the passage
was retrieved before counter 6 and never re-fetched — at n_inject =
50%-of-median, retrieval surfaces are often already cold). Exactly one
probed L2 is a **true matcher miss**: a1-S5-token_expiry-s1, where workers
observed seven 401 responses post-injection under an armed, paper-covering
tripwire and the matcher produced zero fires.

---

## 2. DETECTIONS-SOFT (dual report, beside the strict gate numbers)

SOFT (exploratory generous reading, defined a priori in
`analysis/archaeology.py::soft_detected`): the injected surface produced at
least one 6.1-predicate touch AND the orchestrator took any
interrupt-class action (interrupt/pause/replan) at/after the injection.

| category | strict | soft |
|---|---|---|
| API_SURFACE | 2/6 | 2/6 |
| SCHEMA_DRIFT | 1/6 | 1/6 |
| PERMISSION_AUTH | 5/6 | 5/6 |
| TOOL_CONTRACT | 1/6 | 2/6 |
| RETRIEVAL_INTEGRITY | 0/3 | 1/3 |
| **total** | **9/27 (33%)** | **11/27 (41%)** |

The generous reading recovers only two cells. **The recall failure is not
an attribution artifact: in 16 of 18 misses the sensor genuinely produced
nothing actionable.**

---

## 3. FALSE-INTERRUPT ANATOMY — all 34 orchestrator interrupts, 39 S5 cells

All 34 interrupts carried judge verdict GENUINE (by design: only GENUINE
reaches the interrupt path in S5). 18/34 unattributable; 3 on clean cells.
Full rows in `runs/archaeology_data.json::anatomy`; aggregate picture:

- **Evidence class of the unattributable 18:** "field" (field-shape
  predicates: tw_validate_status_field, tw_passage_body_field,
  tw_sku_*_field) ×14, "all-null" ×3, status=200-on-untrapped-path ×1.
  The noise generators are **field-absence/schema-shape tripwires firing
  on healthy traffic, and the judge ruling them GENUINE** — judge
  credulity on field-class evidence is the FIR engine (H4).
- **Clean-cell interrupts (3):** c1/clean/s1 (tw_passage_body_field),
  d1/clean/s1 ×2 (tw_passage_content_present) — all GENUINE-on-clean, all
  false by definition, all field-class.
- **D11 engagement:** cooldowns did engage in the storm runs (e.g. 50
  cooldown-suppressed refires in a1-S5-endpoint_404-s1-2; installs visible
  on redispatches in c1/d1 L3 cells) — the cooldown machinery worked, but
  it suppresses REPEATS of judged noise; novel-evidence fires kept
  arriving (varied field evidence defeats (tripwire, evidence-hash) dedup).
- **Attribution nuance for the memo:** several b1+gate_skip_trap
  interrupts were injection-CAUSED but unattributable (fired on /repo/files
  symptoms, not the trapped /repo/validate surface) — the strict rule is
  conservative on cascade effects; this depressed nothing in KG1 (those
  cells missed for separate reasons) but explains part of S5's FIR=1.0.

---

## 4. SELF-INJURY MECHANISM — S1 vs S5 success, clean/injected

| split | S1 | S5 |
|---|---|---|
| clean | **9/12** | **3/12** |
| injected | 6/27 | 1/27 |

Nine failed S5 clean cells, one paragraph each:

- **a1/clean/s1** (a1-S5-clean-s1): no interrupt ever reached the
  orchestrator; w3's shipping data was discarded at aggregation and the
  checker failed on missing shipping fields. Plain agent failure of the
  same class S1 shows — NOT sentinel-induced.
- **a1/clean/s2** (a1-S5-clean-s2): escalation_loop death — the run died
  grinding NOISE escalations before any interrupt or aggregate. Sentinel-
  induced (cap consumed the run).
- **b1/clean/s1** (b1-S5-clean-s1): escalation_loop death, zero replans —
  the 320-call worker-grind run from the S5 seed-1 read. Sentinel-induced.
- **b1/clean/s2** (b1-S5-clean-s2): escalation_loop death. Sentinel-induced.
- **b1/clean/s3** (b1-S5-clean-s3): sole worker failed with no output;
  aggregate used=[], discarded=[w1]; checker: migration never completed.
  Agent failure with sentinel interference plausible but not evidenced —
  scored NOT sentinel-induced (conservative).
- **c1/clean/s1** (c1-S5-clean-s1): interrupt → replan with **D15
  carryover EMPTY (completed_results=[])** — at interrupt time no worker
  had finished, so nothing carried; redispatch churn followed (w1r4, w2r5,
  w3r6 lineages; 4 workers discarded) and the final report lacked
  package_id. Sentinel-induced degradation via replan churn.
- **c1/clean/s3** (c1-S5-clean-s3): escalation_loop death. Sentinel-induced.
- **d1/clean/s1** (d1-S5-clean-s1): two GENUINE-on-clean interrupts → two
  replans, carryover empty both times → replan_loop death. The purest
  self-injury specimen in the matrix.
- **d1/clean/s2** (d1-S5-clean-s2): escalation_loop death. Sentinel-induced.

**Mechanism summary:** of the 9 failures, 7 are sentinel-induced (5
escalation-cap grinds + 2 replan-churn deaths with empty D15 carryover);
2 are base-rate agent failures also seen under S1. The S1→S5 clean-success
drop (9/12 → 3/12) is approximately fully explained by false-positive
grind and replan churn — the architecture injures healthy runs.

---

## 5. PER-CATEGORY RECALL (strict, mirrored grouping)

PERMISSION_AUTH **5/6** — the one passing category, exactly where D19's
hard expiry makes the signal loud, sustained, and status-coded (401s
recur on every surface until detected). RETRIEVAL_INTEGRITY **0/3** and
TOOL_CONTRACT **1/6** — both predicted near-zeros CONFIRMED: their
injected signals are content-shaped (a contradicted passage body; a
200-"passed" with checks_run=0), which the compiled status/path predicates
rarely express and single-visit access patterns rarely re-observe.
API_SURFACE 2/6 and SCHEMA_DRIFT 1/6 sit in between, dominated by
starvation-flavored L2.

---

## HYPOTHESES (candidate v2 changes — each cites its failure mode; none applied)

- **H1 — Coupled failure: FIR starves recall.** Noise storms consumed runs
  before workers revisited injected surfaces (L2-starvation: 12 misses;
  a1-S5-endpoint_404-s1-2 with 172 non-surface fires and cap death).
  v2 candidates: compile-time tripwire budget per surface class;
  pre-arm calibration pass against clean traffic (any tripwire that fires
  on the recorded clean prefix is stillborn); judge sees the clean-run
  baseline.
- **H2 — Single-visit surfaces are unobservable at 50%-of-median.**
  c1's passages are fetched once, early; by n_inject the surface is cold
  (c1-S5-doc_contradiction-s2). v2: injection timing as an explicit
  variable, or tripwires that trigger re-validation touches of declared
  assumptions (active probing), not just passive matching.
- **H3 — True matcher miss on status-class signals.**
  a1-S5-token_expiry-s1: seven 401s observed under an armed covering
  tripwire, zero fires. Inspect that tripwire's compiled url_pattern vs the
  401-bearing paths (D5/D8 dialect family suspect). One-cell evidence;
  verify before generalizing.
- **H4 — Judge credulity on field-class evidence.** All 34 interrupts were
  GENUINE; 18 unattributable, 14 of those on field-absence/shape evidence.
  v2: judge prompt receives the field's clean-run baseline value and the
  D9 excerpt; field-absence without a status anomaly defaults NOISE
  (mirrors the author's KG0 adjudication principle: WARNING defensible iff
  data recoverable).
- **H5 — KG2 is unpassable against a zero-FIR baseline.** S2's median FIR
  of 0.0 makes S5 <= 0.5×S2 require literal perfection; the gate's
  construction assumed the naive system would be noisy, but S2's
  anomaly-gated design produces interrupts only when something is actually
  wrong. Gate-design finding for the memo and any v2 prereg — recorded as
  information; the computed verdict stands.
- **H6 — D15 carryover arrives too early to help.** In both replan-churn
  clean deaths, completed_results was empty at interrupt time (carryover
  sizes [0] and [0,0]) — the mechanism worked but had nothing to carry;
  the cost of replanning was repaid with nothing. v2: defer non-critical
  interrupts to wave boundaries so carryover is non-empty, or batch
  interrupts.

*End of archaeology v1. Verdict untouched; everything above is diagnosis.*
