# Scoping: wiring the FULL V2 arm to the benchmark_1c task (V2-on-benchmark)

**Status: SCOPING / DRAFT / NOT FROZEN / NOT CONFIRMATORY — review before any code or spend.**
Date 2026-06-25. Purpose: the CV pilot needs `B_p = K_S1 − K_V2` on the benchmark at forced width, but
V2 has never been wired to benchmark_1c (only S1). This is the concrete plan to wire + qualify it.
Grounded in an architecture read of the live V2 stack (file:line below). NO code written, NO spend.

**RE-SCOPE 2026-06-29:** added the **no-LLM-compiler ablation arm (V2nc)** per an external reviewer's
strongest objection (is the expensive LLM compile *necessary*, or would deterministic re-observation
detect nearly as well far cheaper?) — see new §2A; folded in the resolved R1 determination (named-id
grounding bypasses the cap); updated qual gates, cost, and phasing. Still PLANNING ONLY — no build, no spend.

Carry forward the ACCEPTED caveat: Railway is Linux, 1b is Windows; the worker tool-catalog OS delta
({Glob,Grep,PowerShell}) is documented and non-executable for the curl-gated worker — do not re-investigate.

---

## 0. What's already done vs missing
- **DONE:** benchmark world generator (`analysis/benchmark_1c_world.py`), §6 exact-rational oracle, §4 anomaly
  audit, S1 path + S1 qualification (clean 9/9, injected 9/9), Railway-Linux pipeline (image/volume/persist,
  pin 2.1.177), the §3.5-relevant facts (S1 only; V2 untouched).
- **MISSING (this scope):** the benchmark as a *conductor task* the V2 stack can run — world service, task
  YAML, the §4 single-shard VALUE injection, the two prereg knobs (D35/D36), the deterministic reducer +
  §6 checker, the §3.5 information-boundary audit, and the §9 V2-qualification.

## 1. Good news — core SUT needs NO changes
Per the architecture read, the conductor/compile/arms/matrix layers run a NEW task with **no SUT edits**
(this matters: benchmark §3.6/E2 FORBID modifying treatment code to fit the benchmark):
- task load is automatic (`run_one.py:334` `yaml.safe_load`); world started from `world_rev` (`:426`);
- surface appendix auto-derived from plan text prefixes (`world/surface.py:44-65`);
- compile grounds family templates automatically (`compile_probes.py:192-225`); arms resolve automatically.
So everything below is **benchmark/world-side additions** (allowed) + **prereg knobs** (D35/D36, SUT-neutral),
NOT SUT surgery.

## 2. Components to BUILD (benchmark/world side — allowed)
| # | Component | Integration point | Notes |
|---|---|---|---|
| 2.1 | `world/services/regions.py` | register at `world/server.py:~663` `include_router` | GET `/regions` (list) + GET `/regions/{id}/evidence` serving the §-B shard reports |
| 2.2 | `WorldState` region fixtures | `world/state.py:~290-327` | the N demand shards (μ=5000,σ=1200,4-digit) from `benchmark_1c_world`, seeded; per-`world_rev` |
| 2.3 | **NEW injection type** `single_shard_value_mutation` | handler in `world/injections.py:132-146` (`_HANDLERS`) | the §4 toward-mean VALUE mutation on ONE shard, holding status/schema/length/provenance invariant (NOT any of the 7 existing types). World-side = allowed. |
| 2.4 | task YAML `tasks/benchmark_1c.yaml` | loaded at `run_one.py:334` | goal + assumptions; the **D36 width-scaled plan** naming the N region surfaces; injection list |
| 2.5 | deterministic reducer + §6 checker | `checkers/benchmark_1c.py` + aggregate step | reduce `T=Σd_i` and exact-rational shares MUST be deterministic (no LLM) — verify the conductor's aggregate is syntactic for this task, else add a task-specific deterministic reducer |

## 2A. NO-COMPILER ABLATION ARM (V2nc) — added 2026-06-29 per external reviewer

**Why (a design requirement, not a result):** v2's honest identity is "scheduled deterministic
re-observation **compiled from the plan by an LLM**." The 1b cost failure is monocausal in that LLM compile
step (`cost_autopsy_v3`: compile $0.1376 ≈ 100% of clean overhead); the probe substrate is ~free. The
reviewer's strongest objection: **is the LLM compiler necessary, or would generic active re-observation
(no LLM) detect nearly as well at a fraction of the cost?** Without a baseline that isolates the compiler's
contribution, the result is rejectable on "missing obvious baseline" regardless of pre-registration quality.
So we add a no-compiler arm that **replaces** the LLM compile (not removes-and-breaks it).

**V2nc = V2's substrate, LLM compile swapped for a DETERMINISTIC selection rule.**
- **Surface-selection rule (deterministic, non-LLM):** arm a per-surface VALUE baseline-diff probe on
  **every shard endpoint the plan touches** — enumerated statically from the world's OpenAPI samples
  (`surface_appendix.openapi_paths_for_rev(world_rev)` / `path_samples_for_rev`) restricted to the plan's
  `/regions/*` prefix → all N `/regions/{id}/evidence` surfaces. Lens assigned uniformly: every shard
  surface → `field_read` + `BASELINE_DRIFT` on the demand value — the **same `probe_spec.Probe` shape V2's
  compile emits for a value surface** (`fault_shape=VALUE_CHANGED, lens=field_read, comparison=BASELINE_DRIFT`).
  No `compile_assumptions` LLM call, no lens inference: a fixed "arm every touched shard, watch its value vs baseline."
- **Everything else byte-identical to V2:** arm-time baseline capture, probe-primary cadence (D29),
  corroboration (D28), barrier + pre-completion sweep, interrupt→replan. Only the *what-to-arm* step differs.
- **§3.6 compliance — NOT SUT surgery:** V2nc is a **NEW ARM** (parallel to S1/S2/S3/S4/V2/V2J in
  `sentinel_v2/arms.py`), wired as a branch at compile-and-arm: `if arm.no_compiler: deterministic_select(world_rev, plan)
  else: compile_assumptions(...)`. **V2's compile branch stays byte-identical** (verified in the same
  `sut_neutrality_diff.json`); probe/matcher/corroboration code untouched. Arm-side addition, not a modification
  of the frozen treatment — same category as S1–S4 being separate arms.
- **Cost shape:** V2nc per cell = N workers + orchestrator/replan **MINUS the Sonnet compile** ($0.1376) —
  i.e. cheaper than V2 by ≈the compile cost, which is exactly the quantity the objection is about.
  detection-vs-cost(V2) vs detection-vs-cost(V2nc) isolates the compiler's marginal value.

**R1 interaction (fold-in of the resolved determination):** R1 is RESOLVED — **plan-named ids BYPASS
`FAMILY_MEMBER_CAP=24`** (named 32→32 armed; bare template→24 capped + 8 overflow→UNCOVERED; code path +
local test, ledger 2026-06-25).
- **V2 coverage** is compile-dependent: full N IF the compile names all N ids (the bypass), else capped at 24
  under a bare `{region_id}` template — a **compile-fidelity** property to verify.
- **V2nc coverage** is governed by its OWN enumeration rule, **not** `FAMILY_MEMBER_CAP` → it arms all N shard
  endpoints unconditionally.
- **Reportable contrast:** at N=32/64, if V2's compile lapses to a template it covers 24 while V2nc covers N —
  the deterministic rule can **out-cover** the LLM compiler. That contrast (compiler fidelity/cap-dependent vs
  deterministic-full) is a finding the ablation surfaces independent of cost.

**Two further ablations the reviewer named (flagged, NOT committed):**
- **probes-without-compiler = V2nc itself** — the cheap add-on defined here (same world/substrate, new
  selection rule). In scope as an arm.
- **compiler-without-probes** — run the LLM compile but check its expectations *passively at aggregation*
  (no active re-observation). Needs a NEW detection path (compile-output → passive expected-state check), not
  an arm swap → a **separate build**, not a cheap add-on. Flagged for later; not in this scope.

---

## 3. PREREQUISITES (prereg knobs — must be SUT-neutral, diff artifact per prereg §4)
- **D35 — executor width knob:** `run_one.py:953` `ThreadPoolExecutor(max_workers=4)` → `max_workers=N`.
  Required for forced width N∈{8,32}. Must be proven SUT-neutral (compile/probe/arming/cadence/detection
  byte-identical) via `runs/matrix_1c/sut_neutrality_diff.json` BEFORE any width-scaled cell.
- **D36 — width-scaled plan template:** the plan must emit N shards (plan input only; the compiler grounds
  what it's handed). Interacts with the grounding cap — see Risk R1.
- Both knobs logged as deviations at freeze (prereg §4); built + diffed BEFORE the pilot.

## 4. QUALIFICATION GATES (benchmark §9 + §3.5; before any B_p/CV use)
- **§3.5 information-boundary capability audit (HARD, abandon-don't-modify):** prove (a) baseline values stay
  sealed in side-channel conductor state, never exposed to compiler/worker/orchestrator/any LLM; (b) the
  matcher has NO cross-surface aggregate-reduction operator. Artifact `runs/matrix_1c/information_boundary_audit.json`.
  **If any aggregate path exists in the FROZEN V2 system → ABANDON the single-shard claim and report the
  estimand as "baseline-derived aggregate-or-shard diff" — NO SUT surgery** (§3.6). *Likely passes* (probes
  are per-surface baseline-diff; baselines live in `run_v2_loop` Python state, not in any LLM prompt) but
  must be verified, not assumed.
- **Structural qual (every N∈{8,16,32}):** already green for the S1/world path; re-confirm under the task YAML.
- **V2-qualification (NEW):** V2 detects the single-shard VALUE change *for the right reason* (per-surface
  baseline-diff: arm-time baseline@clean < injection < detection_read), clean runs QUIET, at N∈{8,16,32}.
  Benchmark §9 hard rule: **V2 performance is NOT qualification; a miss is a result** — misses at high N are
  reported, never engineered away.
- **V2nc-qualification (NEW, §2A parallel arm):** same right-reason gate as V2 (detect the single-shard VALUE
  change via per-surface baseline-diff, clean QUIET) at N∈{8,16,32}; **plus** confirm V2nc arms all N shards by
  enumeration (full coverage, cap-independent). Same §9 hard rule — a miss is a result. The §3.5 audit covers V2nc
  too (it shares V2's sealed-baseline substrate; V2nc adds no new baseline-exposure or aggregate path).

## 5. RISKS / architectural tensions (honest)
- **R1 — RESOLVED 2026-06-29 (det. 2026-06-25): plan-named ids BYPASS `FAMILY_MEMBER_CAP=24`.** Code + local
  grounding test: `ground_surface` applies the cap in EXACTLY ONE branch — `all_bounded` (`compile_probes.py:218`,
  `bounded[:FAMILY_MEMBER_CAP]`); the `plan_named` branch (`:217`, `members=named`) and `concrete` branch (`:222`)
  are uncapped. Local test: named 32→**32 armed**; bare `{region_id}` template→**24 armed + 8 overflow→UNCOVERED**.
  **So full N=32 coverage is achievable via a named-id D36 plan with NO SUT surgery.** **Compile-fidelity residual
  RESOLVED 2026-06-29 (real Sonnet compile, $0.40):** given a named-id N=32 plan the compile emits all **32 distinct
  concrete ids** (+ a template) → SUT grounding arms **32/32** — V2's full-coverage path is **REAL**, the LLM does
  not collapse to ≤24. **Rider:** that named-id compile cost **$0.397 (~2.9× the 1b median $0.1376** — 133 assumptions),
  so full coverage at high N is *more expensive*, which **sharpens the V2-vs-V2nc cost contrast** (V2nc compile = $0).
  So the live V2/V2nc contrast is **cost, not coverage** (equal coverage when the compile is faithful). The bare-template
  ceiling (24) remains a separately reportable property V2nc dominates (§2A); raising the cap stays FORBIDDEN (§3.6) and is unnecessary.
- **R2 — new injection vs the 7 hardcoded types.** `single_shard_value_mutation` is world-side (allowed), but
  must fire on exactly ONE shard via a path-gated handler and hold all §4 invariants; needs its own handler +
  validation (`world/injections.py`).
- **R3 — deterministic reducer.** The conductor's aggregate may be LLM-synthesized for existing tasks; the
  benchmark requires a *deterministic* reduce + exact-rational shares (§6). Must confirm/add a syntactic reducer.
- **R4 — port pool (8) / one-world-per-run** (`run_one.py` 8400-8407): fine for a sequential CV pilot; would
  bottleneck a large matrix.
- **R5 — OS caveat (accepted):** runs on Railway-Linux; not request-identical to the Windows 1b SUT (catalog
  delta). Confirmatory-platform decision still open (separate flag).

## 6. EFFORT + COST estimate (rough, for your go/no-go)
- **Effort:** ~**4–6 focused days**, untested integration with debugging: world service+injection (~1d),
  D35/D36 + SUT-neutrality diff (~1d), reducer/checker (~0.5d), §3.5 audit (~0.5d), V2-qualification runs +
  debugging (~1–2d), then the CV pilot (~0.5d).
- **Spend:** V2-qualification (right-reason detection at N∈{8,16,32}, few seeds) ≈ **$10–20**; the CV pilot
  itself (S1+V2 × N∈{8,32} × clean/injected × ~10 seeds) ≈ **$42** (probe-measured per-worker $0.011–0.027 +
  Sonnet compile $0.1376/cell). **Combined ≈ $55–65 — already exceeds the CV pilot's $50 cap.**
- **V2nc ablation delta (marginal, not a new harness — reuses the §2 world/injection/reducer + substrate):**
  V2nc cells (N∈{8,32} × clean/injected × ~10 seeds) ≈ workers **$16** + orchestrator/replan **~$4**, **NO compile**
  → **≈ $20 marginal** (+ a few $ for V2nc-qualification). **Revised combined ≈ $75–85.** Effort delta **~+0.5d**
  (the `deterministic_select` function + arm registration; substrate reused). The ablation *adds* the
  reviewer-baseline at the cost of one extra (cheaper) arm — not a separate build.

## 7. Recommended phasing (each gate can stop cheaply)
1. **R1 — RESOLVED (bypass).** Remaining design call: have the D36 plan name all N ids, and verify compile-fidelity
   (does a real compile name all N from a named-id plan?) — a cheap one-call check, separate from this $0 doc.
2. Build world service + fixtures + single-shard injection + task YAML + reducer/checker, **+ the V2nc
   `deterministic_select` function + arm registration** (reuses the substrate); **validate locally** (laptop,
   small N) — no Railway, ~$1.
3. Build D35/D36; commit the **SUT-neutrality diff** artifact (covering that V2's compile branch + the probe/
   matcher code are byte-identical, V2nc added only as a parallel branch); STOP if not byte-neutral.
4. Run the **§3.5 information-boundary audit** (covers V2 and V2nc); STOP-and-abandon-single-shard if an aggregate
   path exists.
5. **V2-qualify AND V2nc-qualify** at N∈{8,16,32} (right-reason detect + clean quiet; V2nc full-coverage) on
   Railway-Linux; STOP if either can't detect for the right reason (itself a reportable result).
6. Only then run the **CV pilot** (S1 + V2 + **V2nc**) under the ratified frozen formula (H=$0.015, B=$450).

Each phase is a natural checkpoint. Recommend sign-off on the **revised combined ~$75–85 budget** (S1+V2+V2nc,
over the $50 cap) + the compile-fidelity check before phase 2. The ablation arm is the cheap part; the budget
overage is mostly the existing V2-qualification prerequisite.
