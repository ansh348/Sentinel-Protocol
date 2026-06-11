# POST-VERDICT ARCHAEOLOGY v2 — ADJUDICATION OF THE EXTERNAL RED-TEAM (EXPLORATORY)

**Standing boundary:** the 2026-06-11 KG1–KG4 verdict (decisions/kill_gates_final.md)
stands as computed. Nothing below recomputes, re-scores, or reinterprets any gate
quantity. Severity follows decisions/rater_adjudication_principle.md: trace evidence
and resistance to written rebuttal — never which rater, never which direction.
Inputs of record: decisions/external_review_gpt55_pro.md,
decisions/external_review_gemini31_pro.md (commit a9143b7). Pre-commitments:
decisions/phase1b_precommitments.md (commit 823549e, BEFORE any A–G result).
Extraction code: analysis/{replay_check,raw_replay,trajectory_horizon,probe_replay,
semantic_rebin,baseline_breakeven}.py; structured data: runs/archaeology_v2/*.json.
Execution record: analysis/dev_run_ledger.md (total LLM cost: $0.00).
Where a result contradicts an archaeology_v1 narrative, it is reported as a FINDING;
v1, the chain-of-death table, and all gate quantities stand as printed.

---

## 0. RIVAL-STORY VERDICT TABLE (one line each; details in §A–§F)

| Rival story | Raters | Verdict | Discriminating evidence |
|---|---|---|---|
| **A. "L2 starvation" is telemetry/normalization loss** | both | **REFUTED** (with one sub-claim CONFIRMED) | 9/12 L2 cells: ZERO post-injection surface observations in the raw wire stream — nothing existed to lose (raw_replay.json). The matcher consumes the same (method, path, status, body) the middleware serves; worlds replay byte-identical 27/27 (replay_check.json). Sub-claim "the one-matcher-defect claim is too strong" CONFIRMED: the 401 miss is a CLASS — 84 dead armed url_patterns, 61 host-qualified, 19 on covering tripwires across 8 cells (§A.3). |
| **B. Misses are trajectory distortion by false interrupts** | GPT | **PARTIAL** | REPLANNED-AWAY = 0/12 and TRUE-SINGLE-VISIT = 0/12 (no cell lost a previously-visited surface to a replan). But intervention-induced loss is real in adjacent forms: 7/12 NOISE-CONSUMED deaths; same-seed baselines re-visited the surface post-counter in **12/12** L2 cells while S5 did not; and one replan-recompile DROPPED all surface coverage 12 s before injection (b1+schema_drift/s2, §A.2). |
| **C. Bottleneck is content semantics, not observation ("L1.5")** | both | **PARTIAL** | L1.5 exists: 2/12 revisited-predicate-too-weak (b1+schema_drift/s2: drift inside a YAML string, unreachable by JSON-pointer predicates; c1+doc_contradiction/s2: status_in [404,410,500] vs a 200 contradiction). But revisited-semantically-ambiguous = 0, and **all 8 RI/TC ideal-probe payloads are DETERMINISTICALLY DECIDABLE** (content sha flips; checks_run field reads flip) — "re-observation delivers another ambiguous blob" is refuted in this benchmark (§C). Reconciliation (which version is *right*) remains semantic; detection does not. |
| **D. Misses are base-agent/horizon failure** | GPT | **REFUTED** | s5_died_before_oracle = false in **17/17** missed cells: every missed run out-lived (in tool-call terms) the counter at which same-seed S1 re-touched the surface (trajectory_horizon.json). Splits: 9 NOISE-INDUCED, 7 RUN-COMPLETED (no collapse at all), 1 judge-rejection grind (hand-ruled, §D). Base agent is weak overall (S1 failed 10/17 same-seed cells) but no miss is horizon-attributable. |
| **E-coupled-knobs. Corroboration will suppress the true positives probes recover** | both (FATAL) | **PARTIAL — mechanism CONFIRMED, outcome not** | The corroboration rule suppresses 10/16 (full) – 15/16 (probe-primary) of the actually-attributable v1 interrupts, and **one v1 detection is lost outright** (b1+schema_drift/s3). But probe evidence rides the fast path: projected strict recall **21/27 (78%)**, identical under both policy variants (§E.4). Gemini's "100% false-negative for omission-based violations" REFUTED: the gate-field re-read probe IS the confirming evidence; TOOL_CONTRACT projects 4/6. |

Battery headline counts: L2 re-bin = 9 not-revisited / 1 revisited-matcher-failed /
2 revisited-predicate-too-weak / 0 semantically-ambiguous. Probe coverage =
24 COVERED-DECISIVE / 2 COVERED-INDECISIVE / 0 PROBE-UNCOVERED (fixed dialect);
22 / 2 / 2 (strict dialect — the §11.9 #7 fix buys exactly 2 cells). S2 strict
recall 15/27 vs S5 9/27. Break-even: **no crossover at any fan-out** (W_batch −
W_sent < 0).

---

## PHASE 0 — ORIENTATION REPORT (recorded before the battery ran)

(i) **The 12 L2 cells** (archaeology_v1.md:67–94): a1+endpoint_404/s1
(a1-S5-endpoint_404-s1-2), a1+endpoint_404/s2, a1+schema_drift/s1,
a1+schema_drift/s3, a1+token_expiry/s1, b1+schema_drift/s2, b1+gate_skip_trap/s2,
b1+gate_skip_trap/s3, c1+doc_contradiction/s2, d1+gate_skip_trap/s1,
d1+endpoint_404/s1, d1+endpoint_404/s2.

(ii) **Infrastructure confirmed reachable:** raw event streams = per-call
tool_call/tool_response with counter/method/path/query/body/status in every run's
trace_world.jsonl; normalized matcher inputs = the same (method, path, status, body)
tuples the middleware hands `TripwireMatcher.evaluate` (world/server.py:441) — there
is no separate normalization layer to lose evidence in; armed sets recoverable per
run (and per recompile epoch) from `tripwire_set` events; KG0 armed-matcher replay
pattern (analysis/phase0_audit.py::simulate_pair) reusable, with the
STRICT_POINTERS D8 ablation switch.

(iii) **Deterministic worlds replay byte-identically: 27/27 injected S5 cells**
(analysis/replay_check.py; runs/archaeology_v2/replay_check.json), with three
mechanical exclusion classes counted per cell (control-stripped rows, tripped-409
short-circuits that never reached the router live, and one LOSSY-REQ row —
candidate deviation D22).

(iv) **Assumed-but-absent:** no probe infrastructure existed (new analysis-layer
scripts only; zero system code touched); the external reviews were not in the repo
(supplied by the author, committed verbatim a9143b7); request bodies are stored as
errors="replace" decodes (D22).

---

## A. RAW-EVENT REPLAY (12 L2 cells × 2 pointer dialects + epoch-faithful and union variants)

Method per pre-commitment A.1. Full per-call tables in
runs/archaeology_v2/raw_replay.json; summary:

| cell | post-inj surface obs (raw) | 409-blocked attempts | replay fires (epoch-faithful) | union-variant fires (fresh) | live fires | live suppressed (D11) | ruling |
|---|---|---|---|---|---|---|---|
| a1+endpoint_404/s1 | 0 | 0 | 0 | 0 | 0 | 0 | TRUE-STARVATION |
| a1+endpoint_404/s2 | 0 | 0 | 0 | 0 | 0 | 0 | TRUE-STARVATION |
| a1+schema_drift/s1 | 0 | 0 | 0 | 0 | 0 | 0 | TRUE-STARVATION |
| a1+schema_drift/s3 | 0 | 0 | 0 | 0 | 0 | 0 | TRUE-STARVATION |
| a1+token_expiry/s1 | **7** | 0 | 0 | 0 (0 fresh) | 0 | 0 | OBSERVED-BUT-UNMATCHABLE |
| b1+schema_drift/s2 | **7** | 0 | 0 | 7 (0 fresh) | 0 | 0 | OBSERVED-BUT-UNMATCHABLE |
| b1+gate_skip_trap/s2 | 0 | 0 | 0 | 0 | 0 | 0 | TRUE-STARVATION |
| b1+gate_skip_trap/s3 | 0 | 0 | 0 | 0 | 0 | 0 | TRUE-STARVATION |
| c1+doc_contradiction/s2 | **2** | 0 | 0 | 2 (artifact-fresh) | 0 | 0 | OBSERVED-BUT-UNMATCHABLE |
| d1+gate_skip_trap/s1 | 0 | 0 | 0 | 0 | 0 | 0 | TRUE-STARVATION |
| d1+endpoint_404/s1 | 0 | 0 | 0 | 0 | 0 | 0 | TRUE-STARVATION |
| d1+endpoint_404/s2 | 0 | 0 | 0 | 0 | 0 | 0 | TRUE-STARVATION |

**A.1 Count of L2 cells where raw matchable evidence existed but never fired
(misclassified "starvation"): 1 of 12** — a1+token_expiry/s1 (already flagged in
v1 as the true matcher miss; mechanism now exact). Per-call table
(a1-S5-token_expiry-s1, injection at counter 12): five GET /inventory/items/{sku}
401s (counters 12–16) blocked solely by `tw_token_rejected_downstream`'s
url_pattern `localhost:8400/inventory/items` — **host-qualified → D5-dead** (the
matcher matches paths; the pattern matches no world path under glob or regex);
two POST /auth/token 401s (counters 17–18) blocked by its `method: GET` gate.
Predicate intent (status_in [401,403]) was correct; transmission dialect killed it.

**A.2 The two other observed cells are NOT telemetry loss** — the matcher saw every
event; no armed predicate could discriminate:

- **b1+schema_drift/s2** (b1-S5-schema_drift-s2): the worker READ the drifted
  config/settings.yaml at counter 4 — the injection counter itself — then
  overwrote it (PUT c8) and legitimately passed validate (c10: status passed,
  checks_run 3). Live timeline (trace ts): rev-0 set armed 10:13:30 with 6
  covering tripwires → field-noise fires on the **file-listing** response at
  counters 1–2 → judge NOISEs the first escalation (correct, well-reasoned) but
  rules the second **GENUINE at 0.98** (misreading the listing as the validate
  response) → pause → replan → **rev-1 recompile armed 10:18:31 with ZERO
  covering tripwires** → injection fires 12 s later. The union variant shows
  rev-0 would have fired on c4 — but those predicates are non-discriminating
  (first-fired pre-injection on the clean listing; the drifted key lives inside
  a YAML string no JSON-pointer can address). Coupling chain in one cell:
  field-noise → judge credulity → replan → **recompile coverage loss** →
  unmonitored drift. The purest H1 specimen in the matrix.
- **c1+doc_contradiction/s2** (c1-S5-doc_contradiction-s2): the passage path was
  fetched at counters 9 and 33 — both POST-injection (n_inject 6).
  **FINDING (v1 narrative erratum):** v1's "the passage was retrieved before
  counter 6 and never re-fetched — single-visit surface" is inverted by its own
  trace; the surface was visited ONLY post-injection, twice. The single covering
  tripwire (tw_returns_passage_404, status_in [404,410,500]) cannot fire on a
  200-with-contradicted-content. L2 link unchanged; the v1 *mechanism* story for
  this cell was wrong.

**A.3 Singleton-or-class ruling: CLASS.** Dead-pattern sweep over all 27 injected
S5 cells: **84 dead armed url_patterns (61 host-qualified), 19 of them on
tripwires covering their own cell's injection on paper, across 8 cells**
(a1+endpoint_404/s2, a1+token_expiry/s1–s3, b1+schema_drift/s2–s3,
c1+token_expiry/s1, d1+endpoint_404/s3 — including DETECTED cells, which
detected via other live tripwires). The compile-side dialect family (D5) emitted
host-qualified patterns at scale; the arm-time `url_match_modes` record captured
every one. The a1+token_expiry/s1 miss is the only place the class changed an
outcome, because elsewhere a sibling tripwire was live.

**A.4 D8 ablation:** STRICT_POINTERS changes surface-fire outcomes in **0** cells —
the pointer dialect is not implicated in any L2 miss.

**A.5 D11 cross-reference (user amendment):** live suppressed_refire events on the
injected surface post-injection = **0 in all 12 cells** — no "fired live but
suppressed" cases hide inside L2; **no L2↔L3 reclassification arises.** (The 50
and 46 cooldown suppressions v1 reported in the storm cells were all on
NON-surface paths.)

**A.6 FINDING (v1 coverage-heuristic artifact):** the v1 L1 cell
(a1+schema_drift/s2) was in fact covered by a LIVE regex-dialect field tripwire
(`tw_pricing_unit_price_schema`, pattern `.*/pricing/quote/[^/]+$`, field-shaped)
that `covers_on_paper`'s startswith-heuristic does not see. Its raw replay shows
zero post-injection pricing observations — i.e., the cell is L2-equivalent
(starvation), not a compile-coverage gap. Reported as a finding; v1's table
stands as printed.

---

## B. TRAJECTORY-DISTORTION ANALYSIS (12 L2 cells)

Rules pre-stated in analysis/trajectory_horizon.py; full rows in
runs/archaeology_v2/trajectory_horizon.json.

| cell | pre-inj visits | post-inj visits | false interrupts | replan? | any baseline re-visit ≥ counter? | class |
|---|---|---|---|---|---|---|
| a1+endpoint_404/s1 | 0 | 0 | 0 | n | Y | NOISE-CONSUMED |
| a1+endpoint_404/s2 | 0 | 0 | 1 | Y | Y | NOISE-CONSUMED |
| a1+schema_drift/s1 | 0 | 0 | 0 | n | Y | NOISE-CONSUMED |
| a1+schema_drift/s3 | 0 | 0 | 0 | n | Y | NOISE-CONSUMED |
| a1+token_expiry/s1 | 0 | 7 | 0 | n | Y | N/A-OBSERVED (→ §A) |
| b1+schema_drift/s2 | 3 | 7 | 1 | Y | Y | N/A-OBSERVED (→ §A) |
| b1+gate_skip_trap/s2 | 0 | 0 | 2 | Y | Y | NOISE-CONSUMED |
| b1+gate_skip_trap/s3 | 0 | 0 | 1 | Y | Y | UPSTREAM-COLLAPSE |
| c1+doc_contradiction/s2 | 0 | 2 | 1 | Y | Y | N/A-OBSERVED (→ §A) |
| d1+gate_skip_trap/s1 | 0 | 0 | 2 | Y | Y | NOISE-CONSUMED |
| d1+endpoint_404/s1 | 0 | 0 | 2 | Y | Y | UPSTREAM-COLLAPSE |
| d1+endpoint_404/s2 | 0 | 0 | 0 | n | Y | NOISE-CONSUMED |

Cross-system check: **at least one same-seed baseline (S1/S2/S4) observed the
injected surface at/after the injection counter in 12/12 cells** — the surfaces
were structurally re-observable on this seed/task. In 9/12 the S5 run never
visited the surface at ANY counter (e.g., a1-S5-endpoint_404-s1-2 issued zero
/pricing calls in 54 counters; d1-S5-endpoint_404-s1 zero /docs/package calls).
GPT's strict counterfactual signature (surface on the pre-interrupt path,
replanned off it) appears in 0 cells; the intervention-distortion family appears
as noise-death-before-first-visit instead, plus the §A.2 recompile coverage drop.

---

## C. SEMANTIC-SUFFICIENCY RE-BIN

Re-bin of the 12 L2 cells (definitions in analysis/semantic_rebin.py):

| bin | n | cells |
|---|---|---|
| not-revisited | 9 | the nine TRUE-STARVATION cells of §A |
| revisited-matcher-failed | 1 | a1+token_expiry/s1 (D5 dialect class) |
| revisited-predicate-too-weak (**L1.5**) | 2 | b1+schema_drift/s2, c1+doc_contradiction/s2 |
| revisited-semantically-ambiguous | 0 | — |

Ideal post-injection probe payloads, captured live from admin-injected snapshot
worlds (runs/archaeology_v2/semantic_rebin.json), for every RETRIEVAL_INTEGRITY
and TOOL_CONTRACT miss:

| cell (v1 link) | ideal probe | clean → mutated | ruling |
|---|---|---|---|
| c1+doc_contradiction/s1 (L4), /s2 (L2), /s3 (L3) | GET /docs/passages/pol-returns | sha256(content) 4cca556eed6451c9 → fe19641304dfc088; payload = the verbatim contradiction text | **DETERMINISTICALLY DECIDABLE** |
| b1+gate_skip_trap/s1 (L0), /s2 (L2), /s3 (L2) | POST /repo/validate (pure; no side effects) | checks_run 3 → **0**; status "passed" → "passed" | **DETERMINISTICALLY DECIDABLE** |
| d1+gate_skip_trap/s1 (L2), /s3 (L3) | POST /docs/validate with a deliberately-INVALID sentinel doc | status "failed" → **"passed"**, checks_run 4 → **0** | **DETERMINISTICALLY DECIDABLE** |

8/8 decidable by content fingerprint / anchored value / field read — no LLM on the
probe path. Two honest caveats: (1) the benchmark's payloads are authored to flip
cleanly; real-corpus contradiction detection may not reduce to an anchored hash —
DESIGN-LEVEL residue for the full study; (2) deciding which version is *correct*
(Reconcile-class recovery) remains semantic; the probes decide only "changed since
plan time."

---

## D. HORIZON CONFOUND (17 missed cells; L0 excluded)

The L0 cell (b1+gate_skip_trap/s1) died before its injection counter was ever
reached: horizon-unanalyzable by construction — excluded. Full rows in
runs/archaeology_v2/trajectory_horizon.json.

| cell | n_inj | S5 last counter | S1 oracle visit | died before oracle? | S1 success | run end | split |
|---|---|---|---|---|---|---|---|
| a1+endpoint_404/s1 | 12 | 54 | 20 | n | False | escalation_loop | NOISE-INDUCED |
| a1+endpoint_404/s2 | 12 | 59 | 15 | n | True | escalation_loop | NOISE-INDUCED |
| a1+schema_drift/s1 | 12 | 54 | 13 | n | True | escalation_loop | NOISE-INDUCED |
| a1+schema_drift/s3 | 12 | 107 | 12 | n | False | escalation_loop | NOISE-INDUCED |
| a1+token_expiry/s1 | 12 | 18 | 12 | n | False | (completed) | RUN-COMPLETED |
| b1+schema_drift/s2 | 4 | 10 | 4 | n | False | (completed) | RUN-COMPLETED |
| b1+gate_skip_trap/s2 | 4 | 59 | 8 | n | True | escalation_loop | NOISE-INDUCED |
| b1+gate_skip_trap/s3 | 4 | 18 | — | n | False | (completed) | RUN-COMPLETED |
| c1+doc_contradiction/s2 | 6 | 40 | 8 | n | False | (completed) | RUN-COMPLETED |
| d1+gate_skip_trap/s1 | 10 | 37 | 26 | n | False | replan_loop | NOISE-INDUCED |
| d1+endpoint_404/s1 | 10 | 32 | 30 | n | False | (completed) | RUN-COMPLETED |
| d1+endpoint_404/s2 | 10 | 112 | 24 | n | False | escalation_loop | NOISE-INDUCED |
| a1+schema_drift/s2 | 12 | 108 | 12 | n | False | escalation_loop | NOISE-INDUCED |
| c1+doc_contradiction/s3 | 6 | 25 | — | n | True | replan_loop | NOISE-INDUCED |
| d1+gate_skip_trap/s3 | 10 | 129 | 28 | n | False | (completed) | RUN-COMPLETED |
| b1+schema_drift/s1 | 4 | 53 | 4 | n | True | escalation_loop | hand-ruled: NOISE-INDUCED (judge-rejection grind) |
| c1+doc_contradiction/s1 | 6 | 37 | — | n | False | (completed) | RUN-COMPLETED |

("—" = S1 itself never re-touched the surface post-counter; "(completed)" = the
run produced a final aggregate.)

Splits: **NOISE-INDUCED 10** (incl. the hand-ruled b1+schema_drift/s1, an
escalation-cap death grinding genuine-surface escalations the judge kept ruling
NOISE — the L4 mechanism's partner; b1-S5-schema_drift-s1), **RUN-COMPLETED 7**
(no collapse at all; the miss is observational/predicate-level),
**INJECTION-CAUSED 0, BASE-RATE 0** under the pre-stated narrow rules.
**"Pipeline collapse" decomposes into sentinel-noise deaths and completed-but-blind
runs; zero cells died for want of horizon.**

---

## E. ZERO-LLM SHADOW REPLAY (the centerpiece)

Pre-committed mechanics: probes derived mechanically from armed tripwire targets +
seed-matched clean baselines (E.2); cadence = committed heartbeat-k (a1=2, b1=21,
c1=4, d1=5) (E.3); corroboration policy E.1 (full + probe-primary variants).
Assumptions A1–A4 in analysis/probe_replay.py's header — chiefly: probe targets
extracted with the v2 §11.9 #7 dialect fix (strict variant alongside);
trajectories held fixed; probe detection rides the fast path; healthy surfaces
probe NOMINAL (justified by Phase 0 byte-identity). Data:
runs/archaeology_v2/probe_replay.json.

### E.1 Per-cell probe table (fixed-dialect primary)

| cell | coverage | probe-TTD (calls) | post-inj sweeps | probe calls total / post-inj | v1 strict |
|---|---|---|---|---|---|
| a1+endpoint_404/s1 | COVERED-DECISIVE | 0 | 22 | 378 / 308 | n |
| a1+endpoint_404/s2 | COVERED-DECISIVE | 0 | 24 | 1189 / 984 | n |
| a1+endpoint_404/s3 | COVERED-DECISIVE | 0 | 13 | 648 / 468 | Y |
| a1+schema_drift/s1 | COVERED-INDECISIVE | — | 22 | 594 / 484 | n |
| a1+schema_drift/s2 | COVERED-DECISIVE | 0 | 49 | 2322 / 2107 | n |
| a1+schema_drift/s3 | COVERED-DECISIVE | 0 | 48 | 1749 / 1584 | n |
| a1+token_expiry/s1 | COVERED-DECISIVE | 0 | 4 | 153 / 68 | n |
| a1+token_expiry/s2 | COVERED-DECISIVE | 0 | 31 | 1476 / 1271 | Y |
| a1+token_expiry/s3 | COVERED-DECISIVE | 0 | 10 | 330 / 220 | Y |
| b1+schema_drift/s1 | COVERED-INDECISIVE | — | 2 | 12 / 12 | n |
| b1+schema_drift/s2 | COVERED-DECISIVE | — (0 sweeps) | 0 | 0 / 0 | n |
| b1+schema_drift/s3 | COVERED-DECISIVE | — (0 sweeps) | 0 | 0 / 0 | Y |
| b1+gate_skip_trap/s1 | L0-NO-INJECTION | — | 0 | 0 / 0 | n |
| b1+gate_skip_trap/s2 | COVERED-DECISIVE | 17 | 2 | 14 / 14 | n |
| b1+gate_skip_trap/s3 | COVERED-DECISIVE | — (0 sweeps) | 0 | 0 / 0 | n |
| c1+doc_contradiction/s1 | COVERED-DECISIVE | 2 | 8 | 108 / 96 | n |
| c1+doc_contradiction/s2 | COVERED-DECISIVE | 2 | 9 | 110 / 99 | n |
| c1+doc_contradiction/s3 | COVERED-DECISIVE | 2 | 5 | 60 / 50 | n |
| c1+token_expiry/s1 | COVERED-DECISIVE | 2 | 3 | 48 / 36 | Y |
| c1+token_expiry/s2 | COVERED-DECISIVE | 2 | 13 | 168 / 156 | Y |
| c1+token_expiry/s3 | COVERED-DECISIVE | 2 | 3 | 48 / 36 | Y |
| d1+gate_skip_trap/s1 | COVERED-DECISIVE | 0 | 6 | 56 / 48 | n |
| d1+gate_skip_trap/s2 | COVERED-DECISIVE | 0 | 78 | 1106 / 1092 | Y |
| d1+gate_skip_trap/s3 | COVERED-DECISIVE | 0 | 24 | 450 / 432 | n |
| d1+endpoint_404/s1 | COVERED-DECISIVE | 0 | 5 | 84 / 70 | n |
| d1+endpoint_404/s2 | COVERED-DECISIVE | 0 | 21 | 396 / 378 | n |
| d1+endpoint_404/s3 | COVERED-DECISIVE | 0 | 6 | 140 / 120 | Y |

**Coverage: 24 COVERED-DECISIVE / 2 COVERED-INDECISIVE / 0 PROBE-UNCOVERED**
(fixed dialect). Strict dialect: 22 / 2 / **2 PROBE-UNCOVERED** (a1+token_expiry/s1
and b1+schema_drift/s2 — the sets whose every relevant pattern was host-qualified):
**probe coverage inherits Law 1 through the compile dialect; the §11.9 #7 fix buys
exactly those two cells.** The 2 INDECISIVE cells (a1+schema_drift/s1,
b1+schema_drift/s1) had only status-shaped probe bases on the drifted surface —
a status probe is blind to payload drift (GPT #1's "probe compiles the wrong
thing", confirmed for this signal-class-inheritance form).

### E.2 Probe validity audit

Fresh: by construction (post-injection sweeps). Targeted: per the 6.1 surface
predicate (decisive probes listed per cell in the JSON). Decisive: 24/26
injection-bearing cells. **Non-perturbing: three concrete violations found and
measured** — (1) every probe call through the middleware advances the global
tool-call counter, which is the benchmark's injection clock (probes would need
counter-exempt routing in 1b — instrument design item); (2) a probe POST
/auth/token would shift the seed-derived token stream (the auth probe therefore
re-uses the last observed token and GETs /auth/validate); (3) POST /docs/validate
admits the probe's sentinel doc key to validated_docs (no worker-visible effect;
the /repo gate is pure). Gemini's probe-perturbation gate demand is empirically
grounded; P2 #5 drafts it.

### E.3 Probe overhead (the measured column P2 #7 required)

At heartbeat-k cadence with one probe per concrete target, probe call counts reach
**16–22× the run's own tool traffic** on a1 (k=2: 2,322 probe calls against a
107-call run) and 1,106 calls on d1's longest run. HTTP-cheap but not free:
rate-limit, perturbation, and wasted-work accounting must carry it (1bKG4 clause
per Gemini). At the other extreme, b1's k=21 yields **zero sweeps within three
of six b1 runs' lifetimes** — see E.4.

### E.4 Confusion-matrix preview (the deliverable)

Over the actual Phase 1 S5 interrupt stream (34 interrupts: 31 on injected cells,
3 on clean cells — matching v1 anatomy exactly):

| quantity | full policy (fast ∨ 2nd-signal ∨ probe) | probe-primary (fast ∨ probe) |
|---|---|---|
| of **18 false** interrupts, blocked | **12** | **18** |
| of **16 true** (attributable) interrupts, suppressed | **10** | **15** |
| projected strict recall (per-cell, /27) | **21/27 (78%)** | **21/27 (78%)** |
| projected strict recall (gate denominator, /26) | **21/26 (81%)** | **21/26 (81%)** |

- The 6 false interrupts that SURVIVE the full policy all self-corroborate via the
  second-signal clause — different noise tripwires inside the W=10 window —
  including **two on a clean cell** (d1-S5-clean-s1, tw_passage_content_present
  ×2): noise storms corroborate themselves; clause (i) as drafted in v6 §11.9 #2
  is broken, exactly as anticipated in the pre-commitment. Probe-primary blocks
  18/18.
- **One v1 detection is LOST under v2 mechanics: b1+schema_drift/s3** — its
  attributable interrupt is field-shape (suppressed without corroboration) and
  b1's k=21 cadence schedules **zero probe sweeps within the run's 5-call
  lifetime**. The reviews' central fear (corroboration kills true positives) has
  exactly one realized cell — and its mechanism is cadence, not corroboration
  alone.
- All six remaining projected misses: a1+schema_drift/s1 + b1+schema_drift/s1
  (status-only probe basis), b1+schema_drift/s2 + s3 and b1+gate_skip_trap/s3
  (k=21 cadence starvation — the cost-matched cadence, inflated by b1's 320-call
  clean grind during calibration, starves short b1 runs), b1+gate_skip_trap/s1
  (L0). **Projected per-category: API_SURFACE 6/6, PERMISSION_AUTH 6/6,
  RETRIEVAL_INTEGRITY 3/3, TOOL_CONTRACT 4/6, SCHEMA_DRIFT 2/6.**
- Read against P1's inherited thresholds this projection would clear recall ≥60%
  and ≥50% in 4/5 categories — stated for orientation ONLY: it is an
  assumption-laden replay (A1–A4) on the same nine leaked injections, with no
  trajectory feedback, no probe-side FIR, and no clean-run economics. It is not a
  gate and predicts nothing about held-out injections.

---

## F. BASELINE HONESTY + BREAK-EVEN FIT (owed to the decision memo)

**S2 strict recall (instrument rule mirrored; exploratory — S2 recall was never a
gate input):**

| | overall | API_SURFACE | SCHEMA_DRIFT | PERMISSION_AUTH | TOOL_CONTRACT | RETRIEVAL_INTEGRITY |
|---|---|---|---|---|---|---|
| **S2** | **15/27 (56%)** | 5/6 | 2/6 | 6/6 | 2/6 | 0/3 |
| **S5** | 9/27 (33%) | 2/6 | 1/6 | 5/6 | 1/6 | 0/3 |

S2 — the "naive" anomaly-gated baseline with median FIR 0.0 and no compile/judge
overhead — **beats or ties the full sentinel architecture in every category**. Its
workers are the sensors; escalation is anomaly-gated, so it pays no noise tax. H5
lands in its strongest form; the paper must report this head-to-head
(runs/archaeology_v2/baseline_breakeven.json, per-cell rows included).

**KG3 break-even fit** (model form, estimators, acceptance rule pre-committed in
phase1b_precommitments.md §F.1 before fitting): C=$0.322 (median S5 compile),
J=$0.048 (median judge), R=$0.257 (median per-replan), W_batch=$0.145 vs
W_sent=$0.216 (instrument wasted-USD medians, injected cells) →
**W_batch − W_sent = −$0.072: v1's interrupt machinery wasted MORE than batch**.
The inequality C + J + p·R < p·ΔW·(n/n₀) has **no solution at any fan-out** for
any p ∈ {0.1, 0.25, 0.5}; P(no crossover ≤ 8 workers) = 1.00 across 1,000
bootstraps (seed 11). **Acceptance rule: NO plausible crossover — per KG3's
pre-committed branch, the efficiency claim dies on its own fit.** (GPT's "a fitted
crossover can pass while economics fail" is moot here: the fit fails outright;
there is nothing to launder.)

---

## G. CLOSING TABLE — every trace-testable [FATAL]/[MAJOR] claim, both reviews

| # | claim (rater, severity) | disposition | pointer |
|---|---|---|---|
| G1 | Story A: L2 starvation is telemetry/normalization loss (GPT F; Gemini Story 1 M = context/summarization erasure) | **REFUTED** — 9/12 zero raw post-inj surface observations; matcher consumes the middleware stream directly; worlds byte-identical 27/27 | §A; raw_replay.json; replay_check.json |
| G2 | "One matcher defect" is too strong; defects undercounted (GPT Story A sub-claim + #7 M) | **HOLDS** — dialect dead-pattern CLASS: 84 dead patterns / 61 host-qualified / 19 covering / 8 cells; outcome changed in exactly 1 cell | §A.3; raw_replay.json::dead_pattern_sweep |
| G3 | Story B: trajectory distortion by false interrupts (GPT F) | **PARTIAL** — strict signature 0/12; adjacent intervention-loss real: 7 NOISE-CONSUMED + 1 recompile coverage drop; baselines re-visited 12/12 | §B; §A.2; trajectory_horizon.json |
| G4 | Story C: semantic insufficiency / L1.5 (GPT M; Gemini Story 2 M) | **PARTIAL** — L1.5 = 2/12 confirmed (incl. the 200-with-contradiction predicate gap Gemini predicted); ambiguous bin = 0; all 8 RI/TC payloads deterministically decidable | §C; semantic_rebin.json |
| G5 | Story D: base-agent/horizon failure (GPT M) | **REFUTED** — died-before-oracle 0/17; splits 10 noise / 7 completed / 0 base-rate | §D |
| G6 | Probes compile the wrong thing for RI/TC (GPT #1 F; Gemini Change-1 F: "needs an LLM") | **PARTIAL→largely REFUTED in-benchmark** — gate-field re-read + anchored fingerprint are decisive 8/8 with zero LLM; signal-class inheritance does blind 2 status-based cells | §C; §E.1 |
| G7 | Probe world perturbation (GPT #1b M; Gemini missing-gate M) | **HOLDS** — three concrete vectors measured (injection-clock counter, token-stream shift, validated_docs sentinel) | §E.2 |
| G8 | Probe targeting inherits Law 1 (GPT #1c F) | **HOLDS as mechanism** — PROBE-UNCOVERED 2/26 (strict dialect), 0/26 with the #7 fix; plus 2 signal-class-blind cells | §E.1 |
| G9 | Corroboration is a false-negative machine; coupled knobs (GPT #2 F + closing F; Gemini Change-2 F "100% FN for omissions") | **PARTIAL** — suppression real (10–15/16 true interrupts) and 1 v1 detection LOST; but probe fast-path lifts projected recall to 21/27; omission-based TC projects 4/6 (probe IS the corroboration) — 100%-FN refuted | §E.4 |
| G10 | Status-coded fast path admits benign errors (GPT #2a M) | **REFUTED in-corpus** — zero false interrupts carried status ≥400 (the one status-class false was a 200); residue DESIGN-LEVEL for transient-error worlds | §E.4; probe_replay.json::interrupts |
| G11 | Second-signal corroboration can be gamed/self-corroborate (anticipated in pre-commitment; implied by both raters' noise analyses) | **HOLDS** — 6/18 false interrupts self-corroborate (incl. 2 on a clean cell); probe-primary variant blocks 18/18 | §E.4 |
| G12 | Median FIR hides storms (GPT 1bKG2 F) | **HOLDS** — the 172-fire storm cell coexists with median-friendly cells; P2 #2 drafts P95/max/no-grind caps | archaeology_v1 §3; a1-S5-endpoint_404-s1-2 |
| G13 | Category clause unstable at small n (GPT M) | **HOLDS by arithmetic** — n=3–6 per category; one cell swings RETRIEVAL_INTEGRITY by 33 points; P2 #8 | §F table |
| G14 | Clean-parity gate tolerates a weak S1 (GPT M) | **HOLDS as risk** — S1 clean = 9/12 (75%); P2 #1 adds the absolute floor | archaeology_v1 §4 |
| G15 | Probe cost must sit in the waste column (Gemini 1bKG4 M) | **HOLDS + measured** — up to 2,322 probe calls vs 107 run calls; P2 #7 adopts the clause with the measured column | §E.3 |
| G16 | Two-tier loses the judge's semantic fallback (Gemini Change-6 M) | **REFUTED in-corpus** — the judge approved 34/34 interrupts (filtered nothing), NOISE'd 2 genuine surface escalations (L4 ×2), and GENUINE'd a misread listing at 0.98 (§A.2); in this corpus the judge was net-negative; DESIGN-LEVEL residue for worlds where predicates are weaker | §A.2; archaeology_v1 §1, §3 |
| G17 | Instrumentation-integrity replay gate missing (GPT M) | **HOLDS — and this battery is its prototype**: byte-identity 27/27 + raw replay found G2's class | Phase 0; §A |
| G18 | Fitted crossover can pass while observed economics fail (GPT 1bKG3 F) | **MOOT/ANSWERED** — the pre-committed fit finds NO crossover at any fan-out (ΔW < 0); the efficiency claim dies on its own branch | §F |

**DESIGN-LEVEL (not trace-testable; listed for the author's disposition log):**
GPT — #1a probe staleness; #3 calibration-from-Phase-1 leakage; #4 abort
economics/premature-abandonment taxonomy; #5 five-R coarseness (single-injection
pilot cannot exhibit compound recovery); #6 two-tier post-selection (DISPOSED by
pre-commitment P3); §3 protocol attacks — threshold-ratification loophole, "no v2
data" embargo definition, external-holdout demand, retreat-label leak, deviation-
log self-deception, red-team bindingness (PARTIALLY EXECUTED already: dev-run
ledger live, P1–P3 committed; the rest is the author's); §4 1bKG1
recovery-conditioned detection (P2 #6 drafts), TTD censoring (P2 #9), amortization
two-views (P2 #10); §5 novelty table and probe-novelty collapse; §7 forecasts.
Gemini — Change-3 passive→active posterior mismatch; Change-4 abort misfires;
Change-8 work-at-risk vs impact; §3 holdout-categories tightening (RESOURCE_BUDGET
/ DEPENDENCY_VERSION); 1bKG2 Delta-FIR alternative; §5 novelty. The Phase 1b
freeze must convert each into a clause or a written waiver (GPT's own tightening,
adopted as a P2 process note).

---

## CANDIDATE DEVIATION (report-only; instrument-vs-system boundary held)

**D22 (CANDIDATE)** — appended to deviations.md: trace `tool_call.body` stores the
errors="replace" decode of raw request bytes; invalid-UTF-8 request bodies are
unrecoverable byte-exactly (one instance in the matrix: d1-S5-endpoint_404-s1
counter 31 — live 400, replay 200). Response-side matcher inputs unaffected; no
gate quantity involved. No repair performed.

## v1 narrative errata (findings, not corrections — table and gates stand)

1. c1+doc_contradiction/s2: surface visited ONLY post-injection (c9, c33), not
   "retrieved before counter 6 and never re-fetched" (§A.2).
2. a1+schema_drift/s2 (the L1 row): covered by a live regex-dialect field
   tripwire invisible to the covers_on_paper startswith heuristic; the cell is
   starvation-equivalent, and v1's "ontology prior largely intact" actually
   STRENGTHENS (coverage misses ≈ 0 of 27) (§A.6).

## Cost and custody

Total battery LLM spend: **$0.00** (every step deterministic local replay; ledger:
analysis/dev_run_ledger.md). No harness, compiler, matcher, benchmark, or frozen
artifact modified; new code under analysis/ only; banked runs/ never written.
The author's kill-gate decision memo may now consume §E.4, §F, and the G-table.

*End of archaeology v2. Verdict untouched; everything above is adjudication.*
