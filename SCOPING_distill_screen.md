# SCOPING — few-shot distillation screen for the Sentinel check-writer

**Mission:** feasibility only. Can the expensive Sonnet check-writer ("sentinel
compile") be imitated by a cheap small model via **few-shot** (teacher
plan→reasoning→checklist examples in a small model's context), while preserving
(a) checks still FIRE on injected faults and (b) they still TRANSFER to the
sealed held-out fault types? This is a **capability screen**, not a cost
measurement and not a fine-tune.

**Status of this document:** read-only investigation. **No LLM calls were made
and no money was spent** — every quantitative figure below was extracted from
already-recorded run traces (`runs/`). No sealed parameter value was read (the
four sealed files were never opened). I did **not** run the one optional writer
smoke-test; see the end.

---

## 0. THE GATING NUMBER + GO / NO-GO (read this first)

**Genuinely distinct plan SHAPES available as teacher/eval examples: FOUR.**

- The confirmatory benchmark is exactly **4 task archetypes**, one structural
  plan shape each:
  - **a1** — API aggregation (`tasks/a1.yaml`)
  - **b1** — repo migration (`tasks/b1.yaml`)
  - **c1** — research synthesis (`tasks/c1.yaml`)
  - **d1** — document pipeline (`tasks/d1.yaml`)
- Confirmed by the pre-registered matrix draw spec: *"12 clean cells: 4 tasks ×
  3 seed slots"* and *"27 original-injected cells: 9 qualified pairs × 3 seed
  slots"* (`benchmark/matrix_draw_spec.md:19-26`). The 9 qualified pairs are just
  (task × injection) combinations over these same 4 plans.
- A **5th** task exists — `benchmark_1c` (demand allocation) — but it is
  explicitly *"BUILD / NOT FROZEN / NOT CONFIRMATORY"* (`tasks/benchmark_1c.yaml:3`)
  and is a **degenerate** shape: 32 identical one-shard reads + 1 aggregate. It
  adds width, not structural diversity.
- Structurally the four collapse further: **a1/c1/d1** are the same skeleton
  (auth → N parallel GETs → aggregate; c1/d1 add a validate+package gate), and
  **b1** is the lone read-modify-write+gate shape. So there are really **~2–3
  structural families across 4 archetypes.** A handful, exactly as the mission
  feared.

**Nuance that changes the verdict:** the plan is **not** a fixed string — it is
generated per run by the orchestrator LLM (`make_plan`, Sonnet,
`conductor/run_one.py:519-529`) from `goal + task_context + fan_out`. Real
recorded plans vary in decomposition (observed: a1→3 workers, b1→**1** worker,
c1→3, d1→2), so the writer's *input distribution* has more than four points —
but they **cluster into the four archetypes**, and the dependencies the writer
must extract (surfaces + fields) are **goal-locked**, not decomposition-locked.

### Verdict

- **NO-GO** for any claim of the form *"the few-shot student generalizes to
  unseen plan SHAPES."* With only ~4 clustered shapes, a leave-one-shape-out
  design is n=1 per fold across wildly different shapes (write-migration vs.
  read-aggregate); such a "transfer" number would be meaningless. **Say this
  plainly in any writeup: this benchmark cannot measure plan-shape
  generalization.**

- **QUALIFIED GO** for the experiment *as the mission actually frames it*, because
  the benchmark's held-out axis is **fault TYPE, not plan shape**. The writer is
  **category-blind** (it emits 6 general change-shapes, never fault categories —
  `sentinel_v2/compile_probes.py:1-22`, `prompts/v2_compile.md:31-42`), the
  frozen few-shot is **seen-categories-only** by construction and enforced by a
  test (`tests/test_v2_fewshot.py:60-71`), and the two sealed mechanisms are
  scored on these same 4 plans. So *"does a cheap junior's category-blind
  checklist still FIRE on injected faults and TRANSFER to the held-out
  MECHANISMS"* is a legitimate, measurable question at 4 plan shapes — and it is
  scoreable in **replay at $0**. The plan-shape confound is real but is a
  **controllable confound, not a fatal blocker** (guardrails in §8).

**One-line bottom line:** GO to run the fire+fault-transfer screen; NO-GO to
market it as plan-shape generalization. The gate clears for the mission's stated
goal.

---

## 1. Plan diversity — where plans live, and the count

- **Task specs:** `tasks/{a1,b1,c1,d1,benchmark_1c}.yaml`. Each has one
  `archetype`, one `goal`, `fan_out`, and a reference `plan:` (documentation +
  used by qualification / the V2nc ablation, **not** compiled verbatim).
- **The compiled plan is orchestrator output, not the YAML.** `make_plan`
  renders `prompts/orchestrator.md` with `{task_goal}`, `{task_context}`,
  `{fan_out}` and asks Sonnet to *"decompose the goal into at most {fan_out}
  parallel worker subtasks"* (`prompts/orchestrator.md:17-22`). The YAML plan
  steps are **not** given to the orchestrator, so the shape is driven by the
  goal (which names the exact endpoints/fields) + fan_out.
- **Observed real plans** (extracted from `runs/{a1,b1,c1,d1}-S1-clean-s1/trace.jsonl`,
  `orchestrator/plan` events): a1 = 3 worker steps, b1 = 1, c1 = 3, d1 = 2 —
  decomposition varies run-to-run, dependency structure does not.
- **The writer's second input is deterministic per task:** `enriched_context`
  = lean YAML `task_context` + a mechanically derived surface appendix (the world
  server's OpenAPI paths for the services the plan text touches, + the docs
  corpus index) (`world/surface.py:44-69`). Not run-varying.

**Count for teacher/eval purposes:** 4 confirmatory shapes (+1 degenerate,
non-confirmatory). This is the gate. See §0 for the GO/NO-GO.

---

## 2. The writer step (check-writer / "sentinel compile")

| Property | Finding | Location |
|---|---|---|
| Function | `compile_assumptions(plan, surface_appendix, trace, runner=run_claude, **kw)` | `sentinel_v2/compile_probes.py:108-139` |
| Model | **`claude-sonnet-4-6`** (`COMPILE_MODEL`) | `conductor/sessions.py:51` |
| Reasoning/thinking model? | **No.** Plain `claude -p`, `max_turns=1`, `no_tools=True`, no extended-thinking flag. Single-shot completion. | `compile_probes.py:116-117`, `sessions.py:221-268` |
| Input (plan object) | `plan_text()` = `"Goal: …\n\nPlan:\n1. [s1] (w1) <subtask>…"` (sent via stdin), plus the surface appendix (in the system prompt) | `run_one.py:554-558`, `run_v2_loop.py:127` |
| Output (schema) | `SoftAssumptionSet` = `{plan_id, assumptions:[{plan_step, world_fact, surface, pointer?, recovery_hint?}]}`, pydantic `extra="forbid"` (cannot smuggle probe/lens/firing fields) | `compile_probes.py:56-71` |
| Static-prefix + variable-suffix? | **Yes.** Template order = instructions → `{output_schema}` → `{fewshot}` (both static) → `{plan}` → `{surface_appendix}` (variable, last). Filled by literal `.replace()` (not `str.format`, because the schema/few-shot carry literal JSON braces). | `prompts/v2_compile.md:44-57`, `compile_probes.py:88-98` |
| Retry policy | 1 retry on schema-invalid output (`MAX_ATTEMPTS=2`) | `compile_probes.py:51,115` |

**Typical token counts for one writer call** (extracted from 30 recorded compile
events across `runs/matrix_1b/runs/a1-V2-*/trace.jsonl`):

- **Output tokens: min 3,411 · median ≈ 6,700 · mean ≈ 7,400 · max 15,225.**
- **Input tokens ≈ 7,600** (true value; the raw `input_tokens` field reads `3`
  because the large system prompt lands in prompt-cache and `trace_usage` records
  only raw input/output, dropping cache fields — see §6). Nearly all cache-write
  on the fresh-home single call.
- **Cost ≈ $0.13 / call** (Sonnet, output-dominated: ~6.7k out × $15/Mtok ≈
  $0.10). Matches the paper's cited "Sonnet compile $0.1376/cell"
  (`paper/fse_draft.md:147`).
- **Per-run writer total** (incl. replan recompiles; compiles/run median 1, max
  3): median **$0.17**, mean $0.21, max **$0.50** (43 recorded v2 runs).

**Why "the writer is nearly the entire cost":** in the mock world, probe traffic
is effectively free (side-channel reads), so the sentinel's overhead ≈ the
compile call (`CompileEconomics.overhead_usd = compile_cost + probe_cost≈0`,
`compile_probes.py:452-475`), measured against the ≤12% clean-overhead cap. One
verbose Sonnet call against cheap Haiku workers is what pushes overhead over the
cap. **The lever:** the writer's cost is dominated by ~6.7k *output* tokens; a
Haiku writer emitting the same output is 3× cheaper on output ($5 vs $15/Mtok,
`sessions.py:58-63`).

---

## 3. Reasoning-trace capture

- **Chain-of-thought is NOT currently emitted.** The prompt instructs *"HOW TO
  THINK (do this silently; emit only the assumptions)"* and *"you emit only the
  assumption objects, never the reasoning"* (`prompts/v2_compile.md:21,48-50`),
  and the output schema forbids extra fields (`compile_probes.py:59`). Extended
  thinking is not enabled, and `SessionResult` captures only `result_text` +
  `usage` — no thinking blocks (`sessions.py:295-305`). So today you get answers,
  not the thinking.

- **BUT the (plan→reasoning→checklist) format already exists — curated.** The
  frozen few-shot `prompts/v2_compile_fewshot.json` is exactly
  `{change_shape, reasoning, assumption}` triples: 6 worked examples, one per
  change-shape, seen-surfaces-only, teaching the *shape reasoning* the model
  should imitate. `render_fewshot` renders them as `[shape] / reasoning / emit`
  blocks into the prompt (`compile_probes.py:76-85`). This is the exact vehicle
  the mission wants for putting teacher reasoning into a student's context — it
  is already wired.

- **Partial rationale is already in the output.** `world_fact` (why the step
  trusts this) and `recovery_hint` (the replan move) are compressed per-check
  rationale that ship in every assumption.

- **To capture REAL per-plan teacher reasoning** (to distill thinking on the 4
  plans, not just the 6 curated examples), you need a **prompt change**: add a
  `reasoning` field to a CoT-eliciting variant of the compile prompt (and relax
  `extra="forbid"` on a screen-only schema), OR enable extended thinking on the
  Sonnet compile and add thinking-block capture to `SessionResult`. Either is a
  small, isolated change — but for a *minimal* screen you can skip it and reuse
  the frozen 6 examples (see §8).

---

## 4. Writer modularity — the swap seam

**The seam is clean and already exercised.** `V2Conductor.compile_and_arm`
branches on the **source of the soft set**, and *everything downstream is
byte-identical* (`conductor/run_v2_loop.py:116-193`):

```
if self._deterministic_select:                        # V2nc ablation
    soft = select_region_value_assumptions(...)       # deterministic, $0, no model
else:
    soft, sessions = compile_assumptions(...)         # the Sonnet writer
# ... identical from here: compile_pipeline → arm → barriers → corroboration → replan
```

- **The V2nc ablation is a working existence-proof of a non-Sonnet writer.**
  `sentinel_v2/deterministic_select.py` produces a `SoftAssumptionSet` with **no
  model call** and plugs into the same seam; it even emits a mirrored `compile`
  trace event so accounting/replay are identical
  (`deterministic_select.py:41-73`). A few-shot small-model writer is the same
  move with a third branch (or by parameterizing `compile_assumptions`' model +
  few-shot).
- **The contract a replacement must satisfy is tiny:** produce a valid
  `SoftAssumptionSet` from `(plan_text, surface_appendix)`. The deterministic
  `compile_pipeline` (ground → provenance-gate → attach/lens/type/arm) and the
  entire detection/scoring stack are **writer-agnostic and category-blind**
  (confirmed: `sentinel_v2/probes.py:1-21`, `corroboration.py:20-22`).
- **For a pure capability screen you need not touch the run loop at all.** The
  candidate writer can run **offline**: emit a `SoftAssumptionSet` → feed
  `compile_pipeline` → score against recorded broken worlds (§7). Cleanly
  isolated; not entangled.

---

## 5. Detection scoring + sealed types

**How a check is judged to have "fired":** two reconciled ground-truths.

1. **M6 trace-attribution** (`analysis/metrics.py`): `detected = time_to_detect
   is not None` (`metrics.py:226`), i.e. a `pause` event after the injection
   that is *attributable* to the injected surface via `surface_predicate`
   (`metrics.py:56-115`).
2. **V2 probe corroboration** (`sentinel_v2/arms.py:run_v2_detection`,
   `arms.py:175-235`): `detected = bool(invalidations)`. A probe fires
   INTERRUPT-grade via (a) gate-shadow hard invariant, (b) a well-formed status
   ≥400 fast path (excl. 400/405/422), or (c) the typing+corroboration stack
   (`corroboration.py:114-144`; the D28 two-look persistence rule).
   Reconciled: `res.detected = bool(v2_interrupts) or M6_detected`
   (`arms.py:291-292`).

**Metrics:** detection/recall = KG1 (`analysis/matrix_gates.py:114-236`); FIR =
`metrics.interrupts` → KG2 (`matrix_gates.py:241-302`); TTD = `metrics.time_to_detect`
→ KG4 (`matrix_gates.py:327-351`); "right reason" = the attribution rule **plus**
a deterministic 20% probe-validity audit (`PROBE_AUDIT_SEED=1102`,
`matrix_gates.py:156-183`).

**Where sealed types are scored (plumbing only — no values read):**
`conductor/escrow_loader.py` hash-verifies the sealed files against public
custody pins and returns `SealedCell`s whose drawn values are `repr=False`
opaque overrides (`escrow_loader.py:66-156`); `analysis/matrix_runner.py:188-200`
forwards them as `injection_params=` into the run, which the world applies via
`world/injections.py` `_quota_cliff` / `_silent_minor_bump`. Scoring reads only
the **seal-safe ledger** `runs/matrix_1b/results.jsonl` (public identity +
outcomes); `matrix_gates` never reads escrow.

**Transfer measurable WITHOUT touching sealed params — YES.** The writer is a
black box strictly upstream of injection; swap it, run the cells (escrow hash-
verified but never read), read `detected`/`grades` from the ledger. The injection
mechanism and scoring are independent of writer identity.

**Two measurement-instrument gaps to know (not seal violations, fixable without
reading any value):**

1. `surface_predicate` has **no branch for `quota_cliff`/`silent_minor_bump`** —
   it falls through to `return False` (`metrics.py:77`). So on held-out cells the
   **M6** metric can't attribute a pause → baseline arms read `detected=False` by
   construction, and TTD/FIR are un-attributed. For the screen, rely on the **v2
   probe/`grades`** signal, not M6, for the held-out types.
2. On held-out cells `res.detected` credits **INTERRUPT-grade only**
   (`arms.py:291-292`). `quota_cliff` → HTTP 429 → status fast path → INTERRUPT
   (robust, essentially writer-insensitive). `silent_minor_bump` stays **HTTP
   200 with no status tell** (`injections.py:115-129`), so a persistence-based
   CAUTION-grade fire is recorded in `grades` but does **not** flip `detected`.
   **⇒ For the DEPENDENCY_VERSION case, score from `grades` (INTERRUPT *or*
   CAUTION), not the `detected` boolean.**

**Injection mechanics (seen types)** for reference: `endpoint_404` (route→404),
`schema_drift` (rename+unit swap / drifted settings.yaml), `token_expiry`
(revoke-all + issuance lock), `doc_contradiction` (swap passage `content`),
`gate_skip_trap` (gate stops enforcing; seen via read-only shadow),
`single_shard_value_mutation` (benchmark_1c; one region's numeric value only)
— `world/injections.py:39-149`. Held-out: `quota_cliff` (RESOURCE_BUDGET),
`silent_minor_bump` (DEPENDENCY_VERSION) — **sealed params, not enumerated.**

---

## 6. Token logging

**Already recorded per writer call.** Every `compile` trace event carries
`usage = trace_usage()` = `{input_tokens, output_tokens, cost_usd, model,
session_id}` plus `trace_payload()` = both cost numbers, turns, timing
(`compile_probes.py:130-136`, `sessions.py:168-191`). `reconstruct_cost_usd`
already rebuilds USD from tokens × list prices, and the price table **already
contains the Haiku entry** (`sessions.py:58-63,119-140`) — so a Haiku candidate's
cost reconstruction works out of the box.

**Minimal gap (identify only, do not build):** `trace_usage` keeps only raw
`input_tokens`/`output_tokens` and drops `cache_read_input_tokens` /
`cache_creation`, which is why recorded `input_tokens=3` understates the true
~7.6k input. `cost_usd` (and `cost_usd_reconstructed`) already fold the cache
tokens in, so **cost is already reconstructable**; only the raw *input-token
count* is lossy. If you want faithful input-token accounting per writer call
later, the one-line fix is to add `cache_creation_input_tokens` +
`cache_read_input_tokens` to the `trace_usage` dict (`sessions.py:168-177`).

---

## 7. Replay battery — offline, zero-LLM scoring

**Confirmed: a candidate writer's checklist can be scored against recorded broken
worlds at $0 marginal LLM cost.** The infrastructure exists and is tested.

- **Compile replay (no LLM):** `replay_compile` → `read_recorded_soft_set` →
  `compile_pipeline` reconstructs probes from a recorded soft set with no model
  call (`compile_probes.py:419-438`); tested byte-identical in
  `tests/test_v2_compile_replay.py:32-100`.
- **World+probe replay (no LLM):** two offline engines re-stand the world
  in-process via `fastapi.testclient.TestClient` + `create_app(RunConfig)`,
  inject, and execute probes deterministically —
  `analysis/probe_replay.py::run_worlds` (`:186-208`) and
  `analysis/replay_check.py::replay_cell` (`:72-188`). The detection tier is
  LLM-free by design (V2 judge disabled; "DETERMINISTIC detection path ($0 LLM
  beyond the compile/plan/worker calls)", `run_v2_loop.py:15-16,70-77`).
- **World is byte-identical from `world_config.json`** (seed → all fixtures via
  `random.Random(seed)`, `world/state.py:294-321`; injection is an atomic
  deterministic mutation). The "27/27 byte-identical" result is the Phase-0
  replay over the 27 injected cells (`analysis/replay_check.py`,
  `analysis/dev_run_ledger.md:14-15`); unit guard
  `tests/test_determinism.py:54-60`.
- **The ONLY LLM call in the loop is the candidate writer** emitting one
  `SoftAssumptionSet` **per plan**, reused across *all* recorded broken worlds at
  $0. A working template of exactly this offline pattern already exists:
  `analysis/benchmark_1c_compile_fidelity_v2.py` (one real compile → offline
  grounding/arming coverage scoring).
- **The paper's rule is explicit:** side-channel probes *"were validated by
  zero-LLM shadow replay before construction"* (`paper/fse_draft.md:38`), with a
  STOP-gated phasing discipline (`decisions/v2_on_benchmark_build_scope_2026-06-25.md:154-170`).

**One caveat:** the banked `matrix_1b` V2 runs did **not** persist
`soft_assumptions` (their `tripwire_set` came straight from the run loop, not
`record_compile`), so you cannot `replay_compile` the *incumbent Sonnet* output
from history. For a head-to-head you re-run the incumbent once on the chosen
plans (cheap) or add `record_compile` going forward.

---

## 8. Proposed MINIMAL experiment (if the gate clears — it does, for fire+fault-transfer)

**Question it answers:** *Given the expensive writer's teacher examples, does a
cheap model (Haiku 4.5, already the worker/judge model, `sessions.py:52-53`)
produce checklists that (a) FIRE on the 5 seen injected faults and (b) TRANSFER
to the held-out MECHANISMS (quota_cliff / silent_minor_bump)?* — measured
entirely in replay, without touching sealed params.

**Steps**

1. **Teacher examples — reuse what exists ($0).** Use the frozen
   `prompts/v2_compile_fewshot.json` (6 reasoning-per-change-shape examples) as
   the student's in-context teacher set. It is already Rule-Zero clean (no
   held-out leakage) and already the vehicle the incumbent uses.
   *Optional richer variant (~$1):* generate ~8 real per-plan teacher traces (4
   tasks × 2 plan variants) with a CoT-eliciting compile prompt (§3) to distill
   plan-level thinking — only if the 6 curated examples prove too thin.
2. **Candidate writer (Haiku), offline.** Run the same prompt (static prefix +
   few-shot + plan + surface appendix) with `model=claude-haiku-4-5` on **real
   recorded orchestrator plans** (extract from `runs/*/trace.jsonl` — free — to
   reflect production input, not the YAML plans). ~4 tasks × 3 plan variants =
   **~12 candidate compiles** × ~$0.035 ≈ **$0.4**.
3. **Incumbent head-to-head (Sonnet), offline.** Same 12 plans through the
   current Sonnet writer for a paired baseline (history didn't persist soft
   sets). ~12 × $0.13 ≈ **$1.6**.
4. **Score in replay ($0 LLM).** For each candidate/incumbent `SoftAssumptionSet`:
   `compile_pipeline` → probes → execute against recorded broken worlds for each
   injection (seen types + the two held-out **mechanisms** at the visible
   qualification seeds, e.g. `*-quota_cliff-s901+`, `*-silent_minor_bump-s901+`,
   or re-stand from `world_config.json`). Template:
   `analysis/benchmark_1c_compile_fidelity_v2.py`.
5. **Metrics (paired, candidate vs incumbent):** probe **fire/`detected`** on the
   5 seen types; **transfer** = INTERRUPT-grade on quota_cliff and
   **INTERRUPT-or-CAUTION `grades`** on silent_minor_bump (per the §5 gap); plus
   **surface/pointer coverage overlap** (does the junior name the same
   load-bearing surfaces and value pointers the senior does?).

**Teacher examples to generate:** 0 (reuse the 6 frozen) for the minimal screen;
~8 if you add per-plan CoT traces.
**Rough total cost:** **≈ $2–4**, essentially all in the ~24 head-to-head
compiles; **all scoring is $0**. Well within a validate-in-replay budget.

### Blockers / guardrails to flag

- **Do not read or consume sealed params.** Score the held-out **mechanisms**
  using the existing qualification-seed recorded worlds (visible qualification
  defaults) or re-stood `world_config.json` worlds. The sealed confirmatory
  numbers stay reserved for the one-shot matrix (out of scope). Escrow files must
  remain byte-identical (loader hash-checks them, `escrow_loader.py:100-109`).
- **Rule Zero on the few-shot.** Any teacher examples placed in the student's
  context must not leak held-out tokens/categories — enforced by
  `tests/test_v2_fewshot.py:60-71`. Reusing the frozen set keeps this automatic.
- **Score silent_minor_bump from `grades`, not `detected`** (§5 gap 2), and don't
  use the M6 metric for held-out types (§5 gap 1).
- **Frame results honestly (the §0 confound):** with 4 clustered shapes the
  screen shows *"the junior reproduces senior-quality checklists on known shapes
  and those checks fire on novel FAULTS,"* **not** plan-shape generalization.
  Keep teacher examples as *shape-reasoning* (as the frozen set is), not
  plan→answer-key pairs, to avoid the student merely copying. A leave-one-task-out
  sanity pass is worth eyeballing but is n=1/fold — report it as anecdote, not a
  transfer statistic.
- **Exclude `benchmark_1c`** from the screen (non-confirmatory, degenerate, and
  usually served by the V2nc deterministic selector anyway).
- **Incumbent soft sets weren't banked** — re-run incumbent once for the paired
  baseline (or turn on `record_compile`).

---

## 9. Smoke test result (RAN — one plan, Haiku, ~$0.17 total)

Ran the optional smoke: the real recorded **a1** orchestrator plan through
`compile_assumptions` with **Haiku 4.5 swapped in via the documented `runner`
seam** (no experiment code modified), then the deterministic `compile_pipeline`
on the junior's output. (Two calls: the first was marred by a cosmetic Windows
console-encoding crash *after* a successful parse; the second is the clean run
below. Total spend ≈ $0.17.)

**PASS on capability:**
- **Schema-valid `SoftAssumptionSet` on the first attempt** (exit 0, no retry) —
  the cheap model obeys the output contract.
- **Grounds and arms cleanly:** `compile_pipeline` → **35 probes, 0
  telemetry-only, 0 passive, 0 uncovered, 0 hallucinated** (no `GroundingError`).
  Surfaces named: `/auth/token`, `/inventory/items`, `/pricing/quote/{sku}`,
  `/shipping/rates/{sku}` — all correct; the junior even used the family
  **template** form and the D32 grounding armed all 6 SKUs per family.
- 15 assumptions (vs. Sonnet's typical 20–40); returned JSON well-formed, ~4,027
  chars / ~1.2k tokens.

**Two flags that change the experiment's framing:**

1. **Cost win is partial, not 3×.** Haiku billed **12,912 then 19,129 output
   tokens** (highly variable) for a **~1.2k-token** checklist, at **$0.075 /
   $0.098** per call — only **~30% under** Sonnet's ~$0.137, not the naive 3×.
   The billed output vastly exceeds the returned JSON, i.e. most of the writer's
   cost is generation **not present in the checklist** — consistent with model
   **reasoning/thinking tokens** (which `run_claude`/`SessionResult` do not
   capture; `sessions.py:295-305`). Sonnet shows the same pattern more mildly
   (~6.7k billed for ~2k of JSON). **Implication:** the screen must measure and
   control output/reasoning length (cap `max_tokens`, or disable/limit thinking);
   a naive model swap alone does not clear the 12% overhead cap. Corollary: this
   hidden generation may be exactly the **reasoning trace §3 wants to distill** —
   worth capturing rather than suppressing.
2. **This junior checklist pinned 0 value-pointers.** It would catch
   structure/status/vanished/relation shapes but **not a pure value-swap**
   (`doc_contradiction`, and potentially the value-shaped part of
   `silent_minor_bump`). Harmless for a1 (its faults are 404 / schema_drift /
   token_expiry — all structure/status). But it previews the real risk the
   screen must quantify: **does the junior emit the VALUE lens where it matters?**
   n=1 — do not over-read, but the transfer metric must check value-pointer
   coverage, not just probe count.

Artifacts (scratchpad, not in repo): `haiku_smoke.py`, `haiku_smoke_soft.json`,
`haiku_smoke_raw.txt`, `haiku_smoke_trace.jsonl`.

---

## 10. GPT-5.5 writer smoke (RAN — API-keyed, Responses API, ~$1.73 total)

Added GPT-5.5 as a writer candidate **through the existing `runner=` seam only**
— no benchmark port, no experiment-code/sealed-param/prereg changes. Metering
used the **raw OpenAI API via direct HTTPS (outside Codex)**, so the documented
ChatGPT-sub / API-key collision (issues #2733, #3286) cannot occur. An
`OPENAI_API_KEY` (project key) was present in the parent `.env`.

### 10.1 Research — verified live 2026-07-01 (developers.openai.com), not from training data

| Fact | Verified value |
|---|---|
| Model ID | **`gpt-5.5`**; pinned snapshot **`gpt-5.5-2026-04-23`** (used here) |
| `-codex` variant | **Does not exist for 5.5** (API model list + docs; the codex line stops at `gpt-5.3-codex`). Delta vs the mission's assumption. |
| Pricing (standard) | **$5.00 / 1M input · $0.50 / 1M cached input · $30.00 / 1M output** (reasoning tokens billed as output). `gpt-5.5-pro` = $30/$180, no cache — not used. |
| Context | 1,050,000 in / 128,000 max out |
| Reasoning-token field | Responses API `usage.output_tokens_details.reasoning_tokens` (used); Chat Completions `completion_tokens_details.reasoning_tokens` |
| Cached-input field | Responses `usage.input_tokens_details.cached_tokens` |
| Reasoning control | `reasoning.effort` ∈ **{none, low, medium(default), high, xhigh}** → capped-reasoning arm is possible |

Sources: `developers.openai.com/api/docs/pricing`, `.../models/gpt-5.5`,
`.../guides/reasoning`; availability cross-checked against the account's own
`GET /v1/models` (returned `gpt-5.5` and `gpt-5.5-2026-04-23`). Nothing was
unverifiable; GPT-5.5 is available via API, so no fallback to 5.2/other.

### 10.2 What a GPT-5.5 runner must implement

The seam hands the runner `(model=COMPILE_MODEL, system_prompt, stdin_text=plan,
max_turns=1, no_tools=True)` and expects a `SessionResult`-shaped object with
`exit_code / is_error / result_text` (+ `trace_usage()/trace_payload()`) so
`compile_assumptions` can `parse_soft_assumptions(result_text)` unchanged. The
GPT-5.5 runner: ignores the handed Claude model → POSTs `/v1/responses` with
`instructions=system_prompt`, `input=plan`, `reasoning={effort}`; maps
`output_text`→`result_text` and `usage`→the 5-field usage dict. Downstream
(`compile_pipeline`, grounding, arming, scoring) is byte-identical.

### 10.3 Measurement — 12 calls, medium effort, 4 recorded shapes × 3 reps

All 12 valid on the first attempt, all `status=completed`, 0 retries,
0 telemetry-only (every assumption carried a recovery hint).

| shape | reasoning tok (min/med/max) | visible out (med) | value-pointers (min/med/max) | cost/call $ (min/med/max) | n_assump (med) | probes (med) |
|---|---|---|---|---|---|---|
| a1 | 1034 / 1034 / 1552 | 2060 | 3 / 3 / 3 | 0.090 / 0.112 / 0.115 | 37 | 87 |
| b1 | 516 / 1034 / 1552 | 1896 | 8 / 9 / 16 | 0.091 / 0.101 / 0.116 | 31 | 34 |
| c1 | 1034 / 2070 / 2070 | 1949 | 6 / 6 / 9 | 0.086 / 0.123 / 0.143 | 36 | 33 |
| d1 | 1034 / 1468 / 1552 | 3810 | 14 / 16 / 18 | 0.151 / 0.156 / 0.194 | 64 | 108 |
| **overall** | **516 / 1251 / 2070** | 2049 | **3 / 8 / 18** | **0.086 / 0.115 / 0.194** | 36 | 57 |

- **Reasoning as a fraction of total output: 0.21 / 0.34 / 0.52** (median 34%).
- **Grounding clean:** 0 hallucinated across all 12. `uncovered` (b1 5–6, c1 0–3,
  d1 8–12) are §4 **gate-shadow** surfaces that go UNCOVERED because the offline
  `compile_pipeline` was run with `world=None` (no live trapdoor) — the *same*
  condition as the Haiku smoke, expected, **not** a writer defect (a1, which has
  no required gate, shows 0).
- **Capped-reasoning arm** (a1, `reasoning.effort=none`, 2 reps): reasoning
  **= 0** (dial confirmed), cost **$0.057 / $0.079**, still valid, still
  **3–5 value-pointers**, clean grounding. So the floor with reasoning off is
  ~$0.068 on a1 — ~50% under Sonnet — with quality intact.

### 10.4 Head-to-head (same recorded plans, offline grounding)

| writer | reasoning burn | total output tok | **value-pointers** | **cost/call (median)** |
|---|---|---|---|---|
| **Sonnet** (incumbent, recorded) | hidden, not reported (~6.7k billed output for ~2k JSON) | ~6.7k | uses the value lens | **$0.137** |
| **Haiku** (§9 smoke) | hidden; billed output **12.9k–19.1k** for a ~1.2k-token checklist | 12.9k–19.1k | **0** | $0.075–0.098 |
| **GPT-5.5** medium | **reported: 516 / 1,251 / 2,070** | 2.4k / 3.4k / 5.3k | **3 / 8 / 18** | **$0.115** |
| GPT-5.5 `effort=none` (a1) | **0** | ~1.8–2.0k | 3–5 | $0.057–0.079 |

### 10.5 Verdict on the two questions this pilot exists for

**(A) Does the reasoning-IS-the-cost coupling REPLICATE on GPT-5.5? — NO.**
GPT-5.5 spends a *minor, bounded* slice on reasoning: median 1,251 tokens, only
~34% of output, transparently reported. Haiku's pathology — billed output ≈ 10×
the delivered checklist — is **absent**. GPT-5.5 reaches an equal-or-richer
checklist without burning most of its cost on hidden thinking.

**(B) Is the reasoning burn low enough to be a genuine ESCAPE candidate that
could clear the 12% cap? — QUALIFIED YES, but the lever is verbosity, not
reasoning.** At medium effort GPT-5.5 (~$0.115) already lands **~16% under
Sonnet** ($0.137) *despite* 2× output pricing, because it emits ~half the tokens;
with reasoning capped to `none`, cheap shapes drop to ~$0.068 (~50% under Sonnet)
with quality intact. **Caveats, do not overclaim:** (i) GPT-5.5's cost is driven
by **visible-output verbosity** (27–72 assumptions), not reasoning, so the
reasoning dial helps only modestly and the *verbose* shape (d1, ~$0.16) stays
near Sonnet — the real cost lever for GPT-5.5 is output discipline, not the
reasoning cap that mattered for Haiku; (ii) whether ~$0.09–0.12/call actually
clears the 12% cap depends on the run's worker cost, which this offline smoke
does **not** measure; (iii) n=3/shape, grounding scored offline (`world=None`).

**Bottom line:** unlike Haiku (a false economy — cheap-looking but reasoning-
bloated and **0 value-pointers**), GPT-5.5 is a **credible candidate on both
axes**: comparable-to-modestly-cheaper cost *and* markedly better checklist
quality — it emits the VALUE lens (median 8 value-pointers) that the transfer
question needs (value-swaps: `doc_contradiction`, the value-shaped side of
DEPENDENCY_VERSION). The natural next step is a replay-scored fire+transfer run
(§8) with GPT-5.5 at `effort ∈ {none, low, medium}`, treating **output verbosity**
as the cost dial.

**Spend:** GPT-5.5 total ≈ **$1.73** (1 validation + 12 battery + 2 capped),
API-metered, within the single-digit budget. (Haiku §9 smoke was a separate
~$0.17.) No experiment code, sealed params, or pre-registration touched.

---

## 11. GPT-5.5 fire + transfer (offline replay — the DECIDING measurement, $0 scoring)

The §10 smoke gave cost + grounding; this gives **detection**. GPT-5.5 checklists
(generated via the `runner=` seam, pinned `gpt-5.5-2026-04-23`) scored offline
against the recorded broken worlds, head-to-head with Sonnet and Haiku through the
**identical** scorer.

### 11.0 Wiring gate (STEP 1) — BOTH CLOSED before any scoring

- **1a sealed-type attribution → CLOSED.** The detection seam `run_v2_detection`
  returns `grades` + `invalidations` (INTERRUPT/CAUTION; `arms.py:233-235`,
  `corroboration.py:75-144`). My scorer reads **grades**, not the lossy `detected`
  boolean or the M6 rollup (which still has no held-out branch —
  `metrics.py:77`; I do **not** use it). Demonstrated: a value-blind checklist on
  `doc_contradiction` → **fire=False**; add a `/content` pointer → **fire=True**.
- **1b value-pointer coverage → CLOSED.** Value-lens coverage is scored from the
  compiled probes (FIELD_READ / pointer / VALUE_CHANGED) on the attributable
  surface, and it discriminates (the value-blind checklist misses the value-swap).

### 11.1 Method + fidelity caveats

`compile_pipeline` (real arming, incl. §4 gate probes via an in-process world
handle) → clean baselines captured pre-injection → `/admin/inject` → for
`quota_cliff` the family is driven to exhaustion via **worker-path** GETs (the
probe path never decrements, `server.py:542`) → `run_v2_detection` → **grades**.
In-process `create_app` (seed 1, `world_rev=4`, `probe_channel`), $0 LLM.
Scorer validated on synthetic checklists with known answers (all correct).
- **RB (RESOURCE_BUDGET/quota_cliff) qualified host = a1; DV
  (DEPENDENCY_VERSION/silent_minor_bump) qualified host = b1** (decisions/
  holdout_qualification; RB is a1-only, DV is b1-only). Other tasks' held-out
  cells reported as robustness.
- Caveats, stated plainly: **(i)** measures **probe-fire**, not full-run
  worker/validate detection; **(ii)** offline RB is **coverage-bound** (I fully
  exhaust the family) — it isolates *capability* from live *sweep-timing*, so RB
  reads 8/8 here vs the live **3/5** baseline (timing, not coverage); **(iii)** 2
  reps/setting; **(iv)** held-out uses the yaml **qualification defaults** — no
  sealed value read or printed.

### 11.2 The effort-dial table (the real question: does detection track cost?)

Cells = tasks×reps where the injection applies (offline replay, grade-read).

| writer | reason tok | cost/call | value-ptr (med) | assump (med) | **SEEN fire** | **RB transfer** | **DV transfer** |
|---|---|---|---|---|---|---|---|
| Sonnet (incumbent) | hidden | $0.101 | 3 | 27 | **16/18** | 8/8 (a1 2/2) | **0/8** |
| Haiku | hidden | $0.088 | 2 | 18 | 15/18 | 8/8 | 0/8 |
| GPT-5.5 **medium** | 1,415 | $0.105 | 8 | 35 | **16/18** | 8/8 | 0/8 |
| GPT-5.5 **low** | 143 | $0.076 | 6 | 33 | **16/18** | 8/8 | 0/8 |
| GPT-5.5 **none** | 0 | **$0.064** | 6 | 31 | **16/18** | 8/8 | 0/8 |

Per-seen-type (interrupt/cells, all writers unless noted): `endpoint_404` 4/4 ·
`token_expiry` 4/4 · `gate_skip_trap` 4/4 · `schema_drift` **2/4** (a1 pricing
rename caught; **b1 repo-config drift missed by ALL writers** incl. Sonnet — it's
a content-in-YAML change needing a content-hash probe none reliably arm; a shared
probe-blind spot) · `doc_contradiction` Sonnet 2/2, GPT-5.5(all efforts) 2/2,
**Haiku 1/2** (its 0-value-pointer rep misses it — the §10 value-lens gap, now
costing a detection).

### 11.3 Verdict on the ONE question

**Does fire+transfer SURVIVE at a GPT-5.5 setting cheap enough to plausibly clear
12%? → YES. Detection is FLAT across the entire effort dial.**

GPT-5.5 at `effort=none` (**$0.064/call, ~37% below Sonnet, reasoning=0**) returns
the **identical** fire (16/18 seen) and transfer (RB 8/8, DV 0/8) as GPT-5.5
medium ($0.105) and as Sonnet. Coverage — value-pointers (6–8) and assumptions
(31–35) — barely moves as cost halves. **→ real ESCAPE candidate on the detection
surface.** The capability-cost coupling the §10 cost smoke flagged does **not**
bind detection: the reasoning tokens are not load-bearing for fire/transfer, so
zeroing them (the cheap setting) costs nothing measurable in detection. The
coupling in §10 was via *output verbosity* (assumption count = coverage), and
here coverage holds down to the cheapest setting — so on this surface the coupling
does **not** hold. Per the mission's framing this is the "YES" branch: next step
is a **priced full run** to measure the actual overhead ratio (the worker-cost
denominator, which this does **not** measure).

**Sharp caveats — the "YES" is about cost, not about cracking the hard fault:**
- **DV (DEPENDENCY_VERSION) is a wall for EVERYONE — 0/8, GPT-5.5 included**, even
  at medium with a value lens present on b1. The silent bump changes list
  page-size + a version *header*, not the body value at any pinned pointer, and
  the soft-assumption format cannot reach a header lens. GPT-5.5 does **not**
  improve DV transfer; it matches the "missed by every system" baseline. The
  escape is on cost, not on solving DV.
- **RB 8/8 is coverage-bound** (offline exhausts the family). The live **3/5**
  reflects run timing; offline isolates that away. GPT-5.5's RB result is
  "complete family coverage at every effort," not a new capability over the live
  baseline.
- Probe-fire only (not full-run); 2 reps/setting; b1 `schema_drift` shared blind spot.

**Net:** GPT-5.5 ≥ Sonnet and > Haiku on detection (Haiku's 0-value-pointer habit
costs it a `doc_contradiction`), at ≤ Sonnet cost even at medium and ~37% cheaper
at `none` — **with detection fully preserved as the writer is cheapened.** The
deciding question resolves **YES (escape candidate); the coupling does not hold on
the detection surface; DV remains an unsolved wall for all writers.**

**Spend:** GPT-5.5 **$2.23** (24 checklists, API-metered) + Sonnet $0.99 + Haiku
$0.73 (self-consistent baselines, Claude path) + **$0 scoring** (170 offline
cells). Read-only on experiment code / sealed params / prereg throughout; no
sealed value read or printed.

---

## 12. V3 priced full run (LIVE) — the real overhead ratio

**This is a LIVE run** (real workers, real orchestrator, real timing, real GPT-5.5
money) against the frozen `V3_PRICED_RUN_PREREG.md`. **Reported separately from
§11 (offline, byte-identical, reproducible).** §11 measures probe capability in
replay; this measures the deployment fact — cost overhead + whether the monitor
fires during full worker execution. Reasoning fixed at `effort=low`; the varied
lever is **checklist coverage** (a general, fault-blind assumption-count cap:
full / cap-12 / cap-6). Workers priced at real token cost (list-price
reconstruction). Reduced matrix per deviation **D-V3-1** (1 seed × 4 tasks clean;
6 faults × 3 coverage injected; 34 runs). Spend: **$2.86 OpenAI** (writer) over
30 monitored runs, **under the $12 cap** — no cap hit.

### 12.1 Overhead ratio vs the frozen ≤12% bar (clean-run median)

Batch (S1) clean median = **$0.2219** (denominator, measured live).

| coverage | assumptions (med) | writer $ (med) | monitored total (med) | **overhead — frozen** | overhead — writer/batch |
|---|---|---|---|---|---|
| full  | 40 | 0.093 | 0.297 | **+33.9%** | +42.0% |
| cap-12 | 12 | 0.049 | 0.268 | **+20.6%** | +21.9% |
| cap-6 | 6 | 0.038 | 0.272 | **+22.4%** | +17.1% |

- **No setting clears 12%.** The frozen estimator `(monitored−batch)/batch` is
  worker-noise-dominated at 1 seed (cap-6 reads noisier than cap-12 — worker cost
  varies run-to-run and swamps the writer savings; the D-V3-1 limitation). The
  **writer/batch-worker decomposition** (the clean monitor-overhead on clean runs,
  where monitored = batch-worker + writer) is the robust reading and shows the
  monotone slope **42% → 22% → 17%** — all **> 12%**.
- **Floor:** even at 6 assumptions the writer costs ~$0.038, dominated by
  **uncached input** (~$0.019). Prompt-caching of the static prefix did **not**
  engage this run (cached_tokens ≈ 0); a warm cache could lower the cap-6 floor
  toward ~6%, but that was **not achieved here** and is not a result of this run —
  a lever for a future run.

### 12.2 LIVE detection vs coverage (fire on the recorded faults, during execution)

| fault | full | cap-12 | cap-6 |
|---|---|---|---|
| endpoint_404 | FIRE | FIRE | **miss** |
| token_expiry | FIRE | FIRE | FIRE |
| gate_skip_trap | FIRE | FIRE | FIRE |
| doc_contradiction | FIRE | **miss** | **miss** |
| quota_cliff (RB) | FIRE | FIRE | FIRE |
| silent_minor_bump (DV) | miss | miss | miss |
| **catchable fired** | **5/5** | **4/5** | **3/5** |

- **Detection degrades monotonically as coverage/cost drops: 5 → 4 → 3.** cap-12
  loses `doc_contradiction` (the cap dropped the value-pointer on the *specific*
  injected passage pol-returns — value-lens probes present elsewhere but not where
  the swap lands); cap-6 additionally loses `endpoint_404` (the 6-assumption
  checklist dropped the pricing surface entirely, value-lens=0 on a1).
- **RB (quota_cliff) fires at every coverage** — the family (/inventory,/pricing,
  /shipping) is broad enough that even 6 assumptions cover a member → 429 →
  interrupt. (This is the LIVE reading; §11 offline was 8/8 coverage-bound — live
  agrees it's robust to the cap. Note: LIVE RB here reads *stronger* than the live
  3/5 paper baseline because the injected cell fires early enough that a probe
  sweep reaches the exhausted 429 state within the run.)
- **DV = 0 at every coverage** (the wall; no reachable lens), constant across
  arms — excluded from the slope, as pre-registered.

Coverage verification (not INCONCLUSIVE): assumptions fell 40 → 12 → 6 (≥25%
drop) and writer cost fell $0.093 → $0.038, so the cap materially reduced
coverage.

### 12.3 VERDICT — against the frozen bar: **COUPLING CONFIRMED (LIVE)**

Both frozen COUPLING conditions hold: **(1)** detection degrades as coverage/cost
drops (5→4→3 catchable faults), **and (2)** every coverage setting stays **above
12%** overhead. The one setting with full detection (full coverage, 5/5) has the
**worst** overhead (+34–42%); cheapening via the coverage cap lowers writer cost
but **loses faults** (doc_contradiction at cap-12, +endpoint_404 at cap-6) and
**still never reaches 12%**. You cannot buy ≤12% overhead without sacrificing
detection — and sacrificing it doesn't get you to 12% anyway. **Capability and
cost are coupled through coverage.**

This is the deciding result and it **contradicts the §11 offline "escape"
optimism at its load-bearing point.** §11 showed detection flat across the
*reasoning* dial — because reasoning is detection-free. But the actual cost lever
that could clear 12% is **coverage**, and coverage is **detection-bearing**: the
faults that need a specific surface/value probe (doc_contradiction, endpoint_404)
are exactly the ones a length cap drops. GPT-5.5 is a genuinely cheaper and
higher-quality *writer* than Sonnet/Haiku (§10–§11), but as a **monitor that must
clear 12% live**, it does not escape the overhead cap in this run — the coupling
held, via verbosity-as-coverage rather than reasoning tokens. A cheaper writer
whose overhead still exceeds 12% and whose detection erodes as coverage shrinks
is a real, publishable finding, not a disappointment.

**Caveats (do not overclaim):** 1 seed (D-V3-1) → the frozen total-median
overhead is noisy; the writer-decomposition is the robust reading (both >12%).
Prompt-caching not engaged (a possible future lever to lower the floor). Live
detection is timing-variant and single-seed per injected cell; the *slope*
(5→4→3) is the robust signal, individual cells less so. §11 (offline) and §12
(live) are different measurements and are reported separately by design.

**Spend:** V3 ≈ **$3.2 OpenAI** ($2.86 matrix + ~$0.3 harness smoke); Claude
workers/orchestrator on subscription. No sealed value read; execution deviations
logged in `V3_PRICED_RUN_PREREG.md` (D-V3-1).

### 12.4 — Detection slope, multi-seed (robustness extension)

The §12 injected detection cells were single-draw (seed 50011). This extension
re-runs the **injected cells only** at **2 additional seeds (50012, 50013)** —
identical writer (`gpt-5.5-2026-04-23`, `effort=low`), identical coverage caps
(full/cap-12/cap-6, same fault-blind directive), identical scorer and
live-detection definition, same resumable chunked execution and $12 cap. Clean
cost cells were **not** re-run (the overhead conclusion rests on the robust
writer/batch-worker decomposition, §12.1). The §12 verdict is **not reopened**.
Cumulative spend after the extension: **$6.54 OpenAI**, under the $12 cap; no cap
hit.

**Seed-variation gate — PASSES (with an honest note on the source).** More seeds
are only meaningful if they vary the run dynamics that made live detection
timing-variant, not just cosmetic fixture data. They do: **5 of 18 (fault ×
coverage) cells flipped their fire outcome across the three seeds**, the writer's
checklists differed in size (e.g. full endpoint\_404: 41 / 37 / 31 assumptions
across 50011/50012/50013), and probe-target order differed. These are genuinely
different live executions, **not** byte-identical replays. Caveat on the source:
the dominant driver is **live LLM non-determinism** (the orchestrator, workers,
and GPT-5.5 writer are unseeded live calls that vary run-to-run), with the world
`seed` contributing fixture-data and token-stream variation on top. Byte-identity
is an *offline-replay* property (§11); a live run has no fixed stream to replay.
So the three draws test robustness to exactly the live-execution variation that
made §12 timing-variant — which is what we want — while not being three
independent draws of the world seed alone.

**Fire across the 3 seeds** (F = fires, m = miss; order 50011 / 50012 / 50013):

| fault | full | cap-12 | cap-6 |
|---|---|---|---|
| endpoint_404 (API\_SURFACE) | FFF | FFF | mmm |
| token_expiry (PERMISSION\_AUTH) | FFF | FFF | FFF |
| gate_skip_trap (TOOL\_CONTRACT) | FFF | FFF | FmF |
| doc_contradiction (RETRIEVAL\_INTEGRITY) | FmF | mFm | mmF |
| quota_cliff (RESOURCE\_BUDGET) | FFF | FFF | FmF |
| silent_minor_bump (DEPENDENCY\_VERSION) | mmm | mmm | mmm |

**Catchable-fired count** (of 5; DV excluded, constant 0/3 everywhere):

| coverage | s50011 | s50012 | s50013 | median | range |
|---|---|---|---|---|---|
| full   | 5 | 4 | 5 | **5** | 4–5 |
| cap-12 | 4 | 5 | 4 | **4** | 4–5 |
| cap-6  | 3 | 1 | 4 | **3** | 1–4 |

(The s50011 column reproduces §12.2 exactly, as it must.)

**Does 5→4→3 hold across seeds?** At the **median it holds exactly: 5 → 4 → 3**,
and the **direction is robust on every seed** — full > cap-6 on all three
(5→3, 4→1, 5→4). What is *not* seed-stable is the exact count and the midpoint:
the per-cell fire outcome flips on 5 cells, and seed 50012 is even **non-monotone**
(4 → 5 → 1), because the timing-fragile fault flips up at cap-12 before collapsing
at cap-6. The fragility is concentrated:

- **`doc_contradiction` is fragile everywhere** — fires 2/3 at full, 1/3 at
  cap-12, 1/3 at cap-6. The value-shaped fault that needs a probe on the *one*
  swapped passage is timing-sensitive even at full coverage; the cap only makes it
  worse. This is the coupling's own logic showing up as noise.
- **`endpoint_404` is robust until it isn't**: 3/3 at full and cap-12, then
  **0/3 at cap-6** — the cap-6 loss of the removed-endpoint fault is robust across
  all three seeds.
- **`gate_skip_trap` and `quota_cliff` (RB)** are 3/3 through cap-12 but drop to
  **2/3 at cap-6** — cap-6 begins to shed even the broadly-covered faults, seed-dependent.
- **`token_expiry`** is 3/3 at every setting (a global auth lock 401s every
  authed surface, so any surviving probe catches it); **DV** is 0/3 at every
  setting (the wall, constant across arms — excluded from the slope, as
  pre-registered).

**Verdict handling — unchanged; this STRENGTHENS the direction and ADDS a
documented nuance.** The §12 verdict (COUPLING CONFIRMED, LIVE) rests on two
things, both unaffected here: (a) detection degrades as coverage/cost drops —
**strengthened**: full > cap-6 now holds on every seed, and the median slope is
monotone 5→4→3; and (b) overhead never clears 12% — untouched (from the clean
cells, not re-run). The added nuance is that the **exact catchable count at each
coverage is seed-variable** (full 4–5, cap-12 4–5, cap-6 1–4) and individual
cells flip — most of all `doc_contradiction`, whose fragility is itself part of
the finding. Single-cell flips on a new draw do **not** move the verdict; the
slope's *direction* and the >12% overhead do, and both hold.

---

## Appendix — files that matter

- Writer: `sentinel_v2/compile_probes.py` (`compile_assumptions`, `compile_pipeline`,
  `replay_compile`); prompt `prompts/v2_compile.md`; few-shot
  `prompts/v2_compile_fewshot.json`.
- Swap seam: `conductor/run_v2_loop.py:116-193`; existence-proof
  `sentinel_v2/deterministic_select.py`.
- Model/pricing/token capture: `conductor/sessions.py`.
- Plan generation: `conductor/run_one.py:519-558`; `prompts/orchestrator.md`;
  surface appendix `world/surface.py`.
- Scoring: `analysis/metrics.py`, `analysis/matrix_gates.py`, `sentinel_v2/arms.py`,
  `sentinel_v2/corroboration.py`.
- Sealed plumbing (do not read values): `conductor/escrow_loader.py`,
  `analysis/matrix_runner.py`; injections `world/injections.py`.
- Replay: `analysis/probe_replay.py`, `analysis/replay_check.py`,
  `analysis/benchmark_1c_compile_fidelity_v2.py`; determinism
  `world/state.py`, `tests/test_determinism.py`, `tests/test_v2_compile_replay.py`.
- Matrix spec: `benchmark/matrix_draw_spec.md`; tasks `tasks/*.yaml`.
