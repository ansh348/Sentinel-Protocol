<!--
PRE-REGISTRATION — Phase 1c: FAN-OUT ARM (v3; freeze-ready, pending author sign-off on the
four marked judgment values). Swarm-regime mechanism-scaling probe on the supervisor harness.
FROZEN before any N>n0 data. Sources of truth on freeze: prereg_1b.md,
decisions/decision_memo_phase1.md §2/§4, analysis/baseline_breakeven.py,
runs/matrix_1b/fanout_model_inputs.json, runs/matrix_1b/cost_autopsy_v3.json,
runs/matrix_1b/results.jsonl, runs/matrix_1b/gate_report_final.json.
v3 CHANGELOG (second-round review, five points):
 S1 KG0 excludes only trace-verifiable INSTRUMENT failures; SUT-induced failure/timeout/
    rate-limit/context-overflow at high N is an experimental OUTCOME, retained and costed.
    "Clean programmatic execution" moved out of KG0 into the quality outcome.
 S2 crossover is quality-qualified AND persistent (F^Q_grid); isolated positive points are
    "local positivity, no persistent crossover." F_grid uncertainty = bootstrap of the whole
    selection procedure (no fabricated CI). Removed the impossible "F_grid > 64" value.
 S3 p*(N) generalized with five pre-committed sign edge-cases + uncertainty; labeled a
    runtime-cost threshold when the quality floor fails. "No accounting ambiguity" softened to
    "observed execution cost" (B_p does not price the external loss of an invalid answer).
 S4 all statistical placeholders filled (confidence, sidedness, multiplicity, bootstrap,
    margins, zero-waste, outliers, fitted-crossover); power covers the binary quality gates;
    CPVO defined with valid-outcome rule and zero-denominator handling.
 S5 KG0 adds manipulation validity (fault-before-read, aggregate-poisoned, unusable-count =
    estimand, S1 wounded at every N); N=3 bridge gets a pre-committed interpretation fork;
    "negative is dispositive" and "fixed p is conservative" both scoped down.
Custody inherited from prereg_1b: SHA-256 freeze pin, numbered deviation log, dev-run ledger,
data embargo. Knobs D35/D36 logged with a committed SUT-neutrality diff artifact BEFORE any
1c cell runs. Author-judgment values needing sign-off at freeze are marked [AUTHOR-CONFIRM].
-->

# Pre-Registration — Phase 1c: Fan-Out Arm (v3, freeze-ready)

**Status:** freeze-ready pending [AUTHOR-CONFIRM] values · freeze pin: `[SHA-256 at freeze]` · date: `[pinned at commit]`
**Lineage:** Phase 1 (v1 pilot, killed) → Phase 1b (v2 confirmatory, OVERALL FAIL on 1bKG3) → **Phase 1c (this arm)**, the economics question deferred from 1bKG3 per `decision_memo_phase1.md` §2/§4.

---

## 1. What this arm is, and what it is not

Phase 1b failed economics (1bKG3, 55.5% overhead) in a regime the §9 model predicted failure: fan-out n≈3, where a fixed per-plan compile amortizes over almost no parallel work. Phase 1c forces the parallel-worker count **N** as a controlled variable and measures how the cost/waste curves scale, to locate the empirical break-even fan-out and test the assumption behind the model's extrapolation.

**It is** a mechanism-scaling probe on the existing supervisor harness. **It is not** a swarm deployment study (orchestrator-worker substrate; no peer coordination, message bus, or shared mutable agent state). Forced N is a proxy for the swarm regime's *scaling*, not a swarm. **No 1c outcome revises the 1b FAIL or licenses a deployment-efficiency claim** (§9).

**Regime context (qualitative).** Production fan-out is bimodal: supervisor defaults ~3–5 (sometimes >10); swarm topologies ~20–100+. The model's extrapolated break-even (§3) sits above the supervisor range, inside the swarm range. The §6 boundary descriptions reference these regimes qualitatively, not as universal cutoffs.

**Interpretive asymmetry (frozen, scoped — S5).** A **negative** 1c result is *strong evidence against crossover for this width-scaled workload, this harness, and the tested range through N=64* — not universally dispositive (real tasks may carry more work-at-risk per worker or longer horizons). A **positive** 1c result is weak: crossover on a constructed supervisor substrate under free mock probes — *necessary-not-sufficient*, deferring to the real-suite arm (§9).

---

## 2. Estimand (pinned)

- **Workload:** *width-scaled* — fixed work per worker, total work grows with N (matches the model's `W_x(N)=W_x(3)·N/3` extrapolation). Always labeled width-scaled, never "pure fan-out."
- **Invalidation scope:** plan-level. The fault lands on one shard's surface but poisons the aggregate (a1 "fetch-N-services-and-reconcile"); batch waste is all N workers' post-injection work discarded at aggregation. Detecting surface = 1 shard; affected work = all N.
- **Fault probability p (plan-level):** probability the *plan* is invalidated, held fixed across N. We do not model per-shard hazards. **Scoped (S5):** holding p fixed is conservative against the architecture *only under the single-fault model with conditional costs held fixed*; multiple-fault dynamics need not share that direction. Stated so the choice cannot be read as favorable tuning, and not over-claimed.
- **N=3 bridge (required) + interpretation fork (S5):** at N=3 run both the emergent 1b plan and the forced-template plan (D36), same task/seeds. **Pre-committed fork:** if the forced template matches the emergent plan within `[AUTHOR-CONFIRM: similarity/cost margin]`, 1c is a *direct test of the 1b 25–86 extrapolation*; if it differs materially, the 1b 25–86 values can no longer be described as predictions for the new curve and 1c is reported as a *standalone synthetic scaling study* (still valid, no longer a test of the 1b anchor).

---

## 3. Model and prediction under test (frozen, from 1b)

`W_x(N)=W_x(3)·N/3`, n0=3 (`baseline_breakeven.py:8`/v6_1 §11.4). v2 1b estimates (`fanout_model_inputs.json`): C $0.1714 (clean $0.1376), J $0, R $0.2210, W_batch(3) $0.1881, W_sent(3) $0.1200, **ΔW(3) +$0.0682** (v1: −$0.0715). Extrapolated break-even: 86 (p=.10), 40 (.25), 25 (.50) — **the prediction under test, not a result**, resting on the elasticity assumption tested in 1cKG3.

---

## 4. Independent variable and knobs

**N ∈ {1, 3, 8, 16, 32, 64}**, set not LLM-chosen.
- **D35** `max_workers=4`→`N` (`run_one.py:953`), executor width only.
- **D36** seeded N-shard plan template (width-scaled a1), plan input only; compiler grounds on the plan it is handed.

**SUT-neutrality (hard pre-condition):** D35+D36 proven by committed diff to leave compile/probe/arming/corroboration/cadence/detection byte-identical to 1b; artifact `runs/matrix_1c/sut_neutrality_diff.json` committed **before the first 1c cell runs**. Editing the orchestrator's reasoning to force width is prohibited. D35/D36 in `deviations.md` at freeze. (Budget pinned at freeze; N=64 is ~64× per-worker token cost.)

---

## 5. Measured quantities (per cell, per N, per arm)

Inherit prereg.md §6.1 definitions; **paired seeds across arms** (§7). Measure vs N: (1) total run cost split clean `K⁰` / injected `K¹`; (2) W_batch(N), W_sent(N); (3) W_sent decomposition (worker-rework vs probe/sweep); (4) **C(N)** (compile cost vs plan width — measured, not assumed flat); (5) R(N); (6) **probe-volume(N)** armed/exercised (deployment-cost canary, $0 in mock); (7) **detection & recovery scaling** — recall, per-category recall, coverage, FIR {median, P95, max, per-probe-opportunity}, recovery buckets — a reported outcome feeding economics, not a validity check; (8) **realized fan-out** — emitted plan width, concurrent workers at injection, workers invalidated.

**Matrix.** Arms S1 (batch), S3 (heartbeat), V2 (sentinel); S2 (naive) exploratory `[AUTHOR-CONFIRM: promote to full arm if the 1b honesty-clause head-to-head is to carry forward]`. N grid × paired seeds, injected + clean per N, plus the N=3 bridge. Injection counters/parameters from fresh seeds the designers never see.

**Seed count + stopping rule (S1, S4).** Power simulation (pre-freeze) using 1b's per-cell cost/waste variance AND 1b's quality-gate base rates, choosing `n_seeds` so that at each grid point: the one-sided 95% LCB half-width of `B_p(N)` ≤ **H = $0.015** **and** the binary non-inferiority gates (§6) reach ≥80% power at their frozen margins. Floor = 5 seeds; escalate per simulation; the sim, target, and resulting `n_seeds` committed at freeze. **[RATIFIED-PRE-PILOT 2026-06-25 — blind resize formula, frozen before the pilot, not hash-pinned]:** `n_seeds(N) = max(5, ⌈(1.645·SD_seed[B_p(N)] / H)²⌉)` evaluated at the **worst-case p** (max SD over p∈{0.10,0.25,0.50}); per-width n for N∈{8,32}, the confirmatory grid uses the binding-width (larger) n unless per-width is clearly warranted; **budget bound B = $450** for the confirmatory stage — if `Σ_cells n·(per-cell cost) > B`, surface n-wanted vs n-affordable and STOP for author call (no silent truncation). Computed blind to detection / treatment-effect. **Stopping rule:** run exactly `n_seeds`; no peek-and-add. **Replacement (S1):** permitted *only* for a pre-enumerated, trace-verifiable failure of the measurement infrastructure independent of the assigned arm and fan-out (hash mismatch, corrupted trace, injection-mechanism failure, external-service outage). **A clean task failure, timeout, rate-limit, context overflow, or transport failure attributable to system load is an experimental outcome, retained and costed — not replaced.**

---

## 6. Frozen gates and pre-committed branches

### 6.0 Statistical specification (frozen, S4)

- **Resampling unit:** seed (paired across arms — same seed → same world/injection). Cluster bootstrap at the seed level, B=10,000, percentile intervals (BCa as sensitivity).
- **Confidence/sidedness:** directional claims (`B_p>0`, F^Q selection, p* "pays") use one-sided 95% lower bounds; descriptive estimates use two-sided 95%.
- **Multiplicity:** the family of `B_p(N)>0` tests over 6 N × 3 p = 18 hypotheses is controlled by Holm at family-wise α=0.05; the binary non-inferiority gates are controlled within their own Holm family at α=0.05. (A fixed-sequence-by-descending-N test is noted as a more powerful pre-registered alternative *iff* monotonicity holds; since monotonicity is not assumed, Holm is primary.)
- **Non-inferiority margins:** clean-success δ_cs = **10 pp** (inherited from 1bKG2 "within 10 pp of batch"); detection δ_rec on recoverable-class recall vs the N=3 anchor = `[AUTHOR-CONFIRM: proposed 10 pp]` — flagged: small per-category denominators may make δ_rec untestable at the floor seed count; the power sim must confirm it is powered, else δ_rec is widened or the detection gate is reported descriptively only.
- **Zero/near-zero waste in the log fit:** elasticity fit on injected-cell waste using `log(W+ε)`, ε = 1 token, with ε-sensitivity reported; if >10% of injected cells have W≈0, switch to the pre-committed two-part (hurdle) model.
- **Outliers:** no trimming (high-N outliers may be treatment-induced, S1); all cells in the primary analysis; median-based primary, mean-based sensitivity; cells beyond 3 MAD flagged and reported with/without as sensitivity only.
- **Continuous fitted crossover:** secondary; solve the break-even from the fitted log-log W_batch(N), W_sent(N), C(N), R(N); uncertainty by bootstrapping the fit; caveated as assuming the fitted functional form.

### 6.1 1cKG0 — Integrity & manipulation validity (computed first; the ONLY invalidator) (S1, S5)

**Pass requires, per cell:** code/prompt hashes identical to the 1b build; executor configured to width N and plan emitted N shards (D35/D36 applied); **injection fired at the correct global-call fraction and before the affected read**; **the injected state actually poisoned the aggregate**; **the number of outputs rendered unusable matches the declared plan-level estimand**; **clean S1 passes and injected S1 is wounded at every N** under the frozen 1b qualification rule; trace integrity (no corruption/hash mismatch). **Realized concurrent fan-out at injection is recorded as a covariate** — if median realized < N at any grid point, interpretation uses the realized effective fan-out (reported), not an exclusion. **Not in KG0:** V2/S3 clean programmatic execution and any SUT-induced failure/timeout/rate-limit/context-overflow — those are quality/economic *outcomes* (6.2/6.3). KG0 failure invalidates only the affected cells' causal reading (replace per §5 instrument rule, or exclude with logged reason).

### 6.2 1cKG1 — Primary economic result: quality-qualified, persistent net-cost crossover (S2, S3, S4)

**Primary quantity — paired observed-grid expected-cost contrast**, per seed, per N, per p ∈ {0.10, 0.25, 0.50}:

  `B_p(N) = (1−p)·[K⁰_S1(N) − K⁰_V2(N)] + p·[K¹_S1(N) − K¹_V2(N)]`,  with `D⁰=K⁰_S1−K⁰_V2`, `D¹=K¹_S1−K¹_V2`.

`B_p(N)>0` ⇒ V2 cheaper in expectation. `B_p` folds compile, probes, replans, false interrupts, and the **observed execution cost** of missed-detection runs into one quantity — but **it does not price the external loss of producing an invalid answer** (S3); that distinction is carried by the quality floor and CPVO below.

**Quality gate Q(N) (mandatory before any "pays" — S2/S4/S6):** Q(N)=1 iff at N all hold (Holm-controlled, lower-bounded): clean task-success non-inferior to batch (margin δ_cs); recovery-quality floor met (≥ half of detections in detect-and-recover/justified-abort, 1b structure); detection non-inferior to the N=3 anchor (margin δ_rec). A complementary primary view reports **cost per valid outcome**:

  `CPVO_{a,p}(N) = [(1−p)·E[K⁰_a(N)] + p·E[K¹_a(N)]] / [(1−p)·P(V⁰_a(N)=1) + p·P(V¹_a(N)=1)]`,

where a **valid outcome** V=1 is a successful task completion **or** an oracle-justified abort-with-salvage; detect-only, silent failure, and unjustified abort are V=0. If the denominator is 0 (no valid outcomes), CPVO is undefined and the arm is reported as *no valid outcomes at this (N,p); does not qualify.*

**Persistent quality-qualified crossover (S2):**

  `F^Q_grid(p) = min{ N_j ∈ grid : Q(N_k)=1 AND LCB[B_p(N_k)]>0  for ALL grid N_k ≥ N_j }`.

A positive `B_p` at an isolated N followed by losses at larger N is reported as **"local positivity; no persistent grid crossover,"** never as a crossover. `F^Q_grid` takes a value in {1,3,8,16,32,64} or is **undefined** (no persistent quality-qualified crossover demonstrated in the tested range) — there is no "F\* > 64" value. **Uncertainty of `F^Q_grid`** is obtained by bootstrapping the *entire selection procedure* (resample seeds → recompute Q and LCB[B_p] → recompute `F^Q_grid`), reported as the bootstrap distribution; "spans a regime boundary" is defined on that distribution, not on a fabricated threshold CI.

**Break-even fault probability `p*(N)` at every tested N (general — S3):** `p* = −D⁰/(D¹−D⁰)`, with pre-committed sign cases — (i) D⁰≥0,D¹≥0: V2 cheaper for all p; (ii) D⁰≤0,D¹≤0: V2 cheaper for no p; (iii) D⁰<0<D¹: V2 pays *above* p*; (iv) D⁰>0>D¹: V2 pays *below* p* (reverse); (v) D⁰=D¹: no p-dependent crossing. Uncertainty via the same seed bootstrap. Where Q(N)=0, p*(N) is labeled a **runtime-cost threshold**, not a "pays" point.

**Pre-committed branches (per p; CI-gated):** using `F^Q_grid(p)` —
- **≤ 8** (supervisor-plausible): scrutinize against C(N), probe-volume(N).
- **8–32** (low-swarm, predicted/target): licenses only *the scaling mechanism supports a swarm-range crossover*; deployment claim deferred.
- **32–64** (upper tested only): pays at N=64, not below.
- **undefined** (incl. elasticity giving W_sent ≥ W_batch slope, 1cKG3): does not pay at measured fan-out — the **central economic finding**, full prominence.
Verdicts are per-p; if the `B_p(N)` lower bound straddles 0 at the relevant N, or the `F^Q_grid` bootstrap distribution spans a regime boundary, the result is **indeterminate around that boundary**, not forced. No single unqualified verdict across p; the three p-scenarios and `p*(N)` are reported side by side.

### 6.3 1cKG2 — Detection & recovery scaling (reported outcome; feeds 6.2)

Recall(N), coverage(N), FIR(N) {median/P95/max/per-probe-opportunity}, recovery(N), and SUT-induced clean/injected failure rates(N) — **headline results in their own right.** Detection deterioration at large N (compiler truncation, thinned coverage, scheduling delay, load-induced failure) is a *scaling finding*, not contamination, and feeds 6.2 via Q(N) and the CPVO denominator.

### 6.4 1cKG3 — Mechanism: cost scaling (secondary)

Fit `log W_a(N)=α_a+β_a·log N`; the model predicts **β_batch=β_sent=1** (equal *elasticity*, not equal absolute slope — under the true model slopes differ, 0.0627 vs 0.0400, because ΔW(3)>0). Report β with CIs, test each against 1; equivalently test whether `W_a(N)/W_a(3)` tracks `N/3`. Report C(N), R(N), probe-volume(N) scaling. Any "if W_sent scales faster, no crossover" claim is stated only with its required intercept/monotonicity conditions. Explains the shape behind 6.2; not the economic verdict.

---

## 7. Anti-overfit & integrity machinery (inherited)

All §6 thresholds, quality margins, power-sim target, and `n_seeds` frozen before any N>3 data. Fresh injection seeds the designers never see. Paired seeds across arms. D35/D36 SUT-neutrality diff committed before the first 1c run; both knobs in the consolidated `deviations.md`. Dev-run ledger logs every execution and every (instrument-only) replacement; data embargo before gate freeze. Gates compute once on the complete matrix. Exploratory S2 dominance at any N is a results sentence, not a footnote.

---

## 8. Declared limits (frozen)

1. **Width-scaled synthetic workload** — forced N removes 1b's emergent plan-shape variance; the N=3 bridge quantifies the template's own effect and the §2 fork governs whether the 1b extrapolation still applies.
2. **Mock-floor + probe-volume canary** — probes free in the mock, so W_sent(N) and every "pays" result are *optimistic lower bounds*; probe-volume(N) is the deployment-cost canary.
3. **Topology gap (supervisor ≠ swarm)** — scaling on the supervisor substrate as a proxy; no swarm coordination/contention/failure cost reproduced.
4. **Elasticity tested, not assumed** (1cKG3).
5. **Plan-level p, conservatism scoped (S5)** — fixing p is conservative against the architecture only under the single-fault model with conditional costs held fixed; multiple-fault dynamics need not share that direction.
6. **Cross-matrix** — 1c is not strictly apples-to-apples with 1b; each internally consistent.
7. **Deployment claim deferred** — no 1c branch licenses a swarm-deployment efficiency claim; viability lives in a future swarm-harness + real-suite arm with live probe costs (§8 real-suite study, schedule gate 3). Positive 1c is necessary-not-sufficient; negative 1c is strong evidence against crossover for *this* workload, harness, and range (not universally dispositive).

---

## 9. Reporting rule (frozen)

> The primary Phase-1c result is the quality-qualified net-cost curve over the observed fan-out grid, with uncertainty. We report the smallest tested fan-out at which **persistent, quality-qualified** cost positivity is demonstrated (per fault rate p), or report that no such crossover is demonstrated through N=64, together with the break-even fault probability p\*(N) at each tested N. The continuous fitted crossover and the component scaling (elasticity, C(N), probe-volume(N)) are secondary. No Phase-1c outcome revises the Phase-1b FAIL or licenses a deployment-efficiency claim.
