# TripwireBench Pilot Protocol
## A Pre-Registered Kill-Gate Study for Sentinel Protocol

**Version 1.0 | June 10, 2026 | Freeze thresholds before first run**

**Purpose:** Decide, for under $250 and roughly 9 working days, whether Sentinel Protocol survives contact with reality, before committing August to the full FSE 2027 study. The pilot is designed to falsify, not to demonstrate. Every hypothesis below has a numbered kill gate with a pre-registered threshold and a named consequence.

---

## 1. What Could Make This Not Work

Four failure modes would kill or gut the paper. The pilot exists to surface them early:

- **F1: Compilation garbage.** The sentinel cannot reliably turn a natural-language plan into well-formed, observable tripwires. Everything downstream is moot.
- **F2: Useless judge.** The filter tier adds cost without reducing false interrupts relative to naive escalation. The three-tier claim collapses to two tiers.
- **F3: Overhead swamps savings.** Compile + judge + monitoring costs exceed the wasted work they prevent at realistic fan-out. The amortization thesis fails.
- **F4: Heartbeat parity.** Periodic plan revalidation at matched cost performs as well as compiled tripwires. This is the most dangerous one: it is the cheap, obvious alternative every reviewer will propose, and if it wins, the contribution is dead as framed.

Each maps to a hypothesis and a kill gate in Section 6.

---

## 2. Two-Phase Structure

**Phase 0: Smoke test (qualitative, ~6 hours, < $10).** Run only the sentinel compiler on 4 task plans. No execution. Score the generated tripwires by hand against a rubric. This is the cheapest possible falsification of F1: if the compiled tripwires are garbage, you find out in an afternoon, not after building a harness. Phase 0 can run any free evening before the launch if curiosity wins; it requires only the compile prompt and the DSL schema.

**Phase 1: Quantitative pilot (~7 working days, ~$150-250).** Full mini-harness, 20 tasks, 5 systems, injections, 3 seeds, 600 runs. Produces effect-size estimates for all four kill gates. Runs July 16 to August 1 per the FSE timeline.

---

## 3. Harness Design (Minimal but Honest)

### 3.1 Why synthetic-first, not GAIA-first

The full TripwireBench wraps GAIA, tau-bench, and SWE-bench. The pilot deliberately does not. Real-web tasks introduce flakiness (live endpoints, rate limits, nondeterministic search results) that confounds the one thing a pilot must measure cleanly: the causal effect of a controlled invalidation. The pilot world is therefore **fully mocked and deterministic**: a local FastAPI server simulating APIs, a fixture git repository, and a local document corpus. Injections are exact state mutations triggered at exact tool-call counts. Every run is reproducible. One anchor slice of 3 tau-bench retail tasks is included as an external-validity sanity check, clearly labeled as exploratory.

### 3.2 Components

```
tripwire-pilot/
  world/        FastAPI mock services + mutable state + /admin/inject endpoint
  harness/      LangGraph orchestrator-worker graphs (1 orchestrator, 4 workers)
  sentinel/     compile.py (plan -> tripwires), judge.py (escalation filter), dsl.py (pydantic schema)
  proxy/        tool-call middleware: global call counter, injection trigger, tripwire matcher
  tasks/        20 task specs (yaml): goal, seeded plan shape, assumptions, injection spec
  runs/         JSONL traces, one file per run
  analysis/     metrics.py + notebook
  prereg.md     frozen copy of Section 6 of this document, committed before first Phase 1 run
```

### 3.3 The world server

A single FastAPI app exposing: (i) three mock REST services with OpenAPI specs (inventory, pricing, shipping, for the aggregation archetype), (ii) a mock auth service issuing expirable tokens, (iii) a document store with retrievable passages, (iv) a thin wrapper over a fixture repo for code tasks. An `/admin/inject` endpoint applies one of the supported mutations atomically:

| Injection | Mutation | Ontology category |
|---|---|---|
| endpoint_404 | Route removed; returns 404 with deprecation body | API_SURFACE |
| schema_drift | Response field renamed (e.g., `unit_price` -> `price_cents`, units change) | SCHEMA_DRIFT |
| token_expiry | Auth token invalidated; 401 on next call | PERMISSION_AUTH |
| doc_contradiction | A passage relied on by the plan is replaced with a contradicting one | RETRIEVAL_INTEGRITY |
| gate_skip_trap | A required validation tool starts silently returning success without running checks | TOOL_CONTRACT |

Five categories, not eight. DEPENDENCY_VERSION, QUALITY_GATE, and RESOURCE_BUDGET are deferred to the full study: budget tripwires are trivially detectable (uninformative for the pilot) and dependency/quality injections need the heavier code-execution sandbox.

### 3.4 The proxy and the trigger discipline

All tool traffic from every agent passes through one middleware that (i) increments a global tool-call counter, (ii) fires the injection when the counter hits N_inject, identical across systems and seeds for a given task, (iii) evaluates the active tripwire checklist against each tool response with pure string/JSON predicate matching (no LLM), and (iv) appends every event to the run's JSONL trace. Triggering on call count rather than wall clock is what makes batch vs. sentinel comparable: both worlds break at the same point in the work, not the same point in time.

### 3.5 Models

Fixed for the whole pilot: orchestrator and sentinel-compile on a Sonnet-class model; workers and sentinel-judge on a Haiku-class model; temperature 0 everywhere except worker text generation (0.3). The cheap-judge choice is deliberate: if a small model can filter escalations well, the economics improve, and the pilot tests this directly. One exploratory arm (Section 5) swaps the judge to Sonnet to see if judge quality is the bottleneck.

### 3.6 Execution backend: subscription-funded `claude -p` (Path A) vs. raw API (Path B)

**Path A (default for the pilot):** every agent session is a headless Claude Code invocation billed to the existing Max subscription, not the API. Sentinel compile and judge are single-turn calls; workers are multi-turn sessions whose tool access is restricted to the mock world:

```bash
# sentinel compile (pure text -> JSON, no tools)
cat plan.md | claude -p --bare \
  --model claude-sonnet-4-6 \
  --system-prompt "$(cat prompts/sentinel_compile.md)" \
  --output-format json --max-turns 1 > runs/$RUN/compile.json

# worker session (tools limited to curl against the local world server)
claude -p --bare \
  --model claude-haiku-4-5-20251001 \
  --system-prompt "$(cat prompts/worker.md)" \
  --allowedTools "Bash(curl http://localhost:8400/*)" \
  --max-turns 14 \
  --output-format json "$(cat tasks/$TASK/worker_$i.md)" > runs/$RUN/w$i.json
```

Controls that make Path A defensible: `--bare` (no environment-dependent context), `--system-prompt` (full replacement of the default prompt), pinned CLI version (`npm install -g @anthropic-ai/claude-code@<version>`, version recorded in every trace), pinned full model strings (never aliases), `--max-turns` caps, and `total_cost_usd` from the JSON payload as the consistent API-equivalent accounting unit for the wasted-work metric (verify on the first run that subscription invocations populate it; if not, reconstruct USD from the per-model token usage fields at list prices).

Known costs of Path A, accepted for the pilot: (i) no temperature control, so variance is higher; the kill-gate margins (20% wasted-work, 2x FIR ratios) were already set fat enough to absorb this; (ii) the binding constraint shifts from dollars to subscription rate-limit windows (5-hour rolling plus weekly caps), so concurrency drops from 8 to 2-3 sessions and the run matrix spreads across several evenings; the runner must checkpoint per-run and resume cleanly; (iii) the harness is Claude Code itself, which for the pilot is a feature, not a bug: the workers run on a production agent harness, which is exactly the deployment context the paper motivates with.

**Path B (API, pinned model, temperature 0):** reserved for paper-grade numbers. If all gates pass, re-run only the qualified pairs under S1, S3, S5 at 5 seeds on the API (roughly $60-100, billable to research funding). Pilot decisions on Path A money; published preliminary-study numbers on Path B rigor.

---

## 4. Task Suite (20 tasks, 4 archetypes)

Each task is a yaml spec: a goal, an expected plan shape (so injections can target a real assumption), a list of 4-8 ground-truth assumptions, the injection spec (type, N_inject), and a programmatic success checker (exact-match or schema-validated output, no LLM grading of success in the pilot).

| Archetype | Count | Description | Eligible injections |
|---|---|---|---|
| A. API aggregation | 6 | Workers query 3 mock services, reconcile, produce a structured report | endpoint_404, schema_drift, token_expiry |
| B. Repo migration | 4 | Workers perform a coordinated rename/config migration across a fixture repo | schema_drift (config), gate_skip_trap |
| C. Research synthesis | 6 | Workers retrieve from the document store and synthesize a brief with citations | doc_contradiction, token_expiry |
| D. Document pipeline | 4 | Workers generate, validate, and package documents through a required gate tool | gate_skip_trap, endpoint_404 |

**Manipulation check (mandatory):** before any comparative runs, execute every (task, injection) pair under the batch baseline once. The injection qualifies only if it actually degrades the batch outcome (wrong output, failed checker, or forced full redo). An injection the batch system shrugs off is not plan-invalidating and gets redesigned. Target: 20 tasks x ~1.5 eligible injections each = ~30 qualified (task, injection) pairs.

---

## 5. Run Matrix

### 5.1 Systems under test

| ID | System | Description |
|---|---|---|
| S1 | Batch | Dispatch all, wait, aggregate. Discovers invalidation only at aggregation; orchestrator then redoes invalidated subtasks once. |
| S2 | Naive interrupt | Workers escalate any anomaly (non-200, unexpected field, contradiction heuristic) directly to the orchestrator. No filter. |
| S3 | Heartbeat (cost-matched) | No tripwires. Orchestrator re-validates plan assumptions with a fresh inference call every k worker tool-calls. k is set per-task so heartbeat's expected overhead equals Sentinel's measured compile+judge overhead (calibrated after S5's first seed). This is the strongest fair version of the obvious alternative. |
| S4 | Sentinel, no judge | Tripwires compiled and matched; every tripwire fire goes straight to the orchestrator. Isolates the compiler's value. |
| S5 | Sentinel Protocol (full) | Compile + match + judge + severity/scope routing. |

### 5.2 Conditions and counts

Per qualified (task, injection) pair: one injected variant at N_inject = 50% of the batch baseline's median tool-call count for that task. Per task: one clean (no-injection) variant, used to measure pure overhead.

Runs = [~30 injected pairs + 20 clean tasks] x 5 systems x 3 seeds = **750 runs**.
If budget pressure appears, drop to 2 seeds for S2 and S4 (the diagnostic arms): 650 runs.

Exploratory arms (1 seed each, excluded from kill-gate math): judge-on-Sonnet for 10 injected pairs; 3 tau-bench retail tasks under S1 and S5.

### 5.3 Budget and wall time

**Path A (subscription, default):** marginal dollar cost ~$0; the binding constraint is rate-limit windows. ~5 to 7 headless sessions per run x 750 runs is roughly 4,500-5,000 sessions; at 2-3 concurrent sessions this spreads over 4-6 evenings of unattended batches. Check the current 5-hour and weekly limits for the plan tier at support.claude.com before scheduling, and build the runner to checkpoint per-run so a throttled window just pauses the queue instead of corrupting it. **Path B (API, paper-grade subset only):** ~30 qualified pairs x 3 systems x 5 seeds at an estimated $0.15-0.35 per run lands around $60-100; pre-register a hard stop at $150. Phase 0 adds nothing material under Path A.

---

## 6. Metrics and Pre-Registered Kill Gates

### 6.1 Operational definitions (frozen)

- **Wasted work (W):** tokens + tool calls consumed between the injection event and the system's pause/replan decision, summed over all active workers, **plus** tokens of any partial results discarded by the replan. For S1, the window runs from injection to aggregation. Reported in tokens and USD.
- **Time-to-detect (TTD):** global tool-call count between injection and the first orchestrator-level pause attributable to the injected change. Attribution by trace rule first, manual audit on a 20% sample (plus every disagreement case).
- **Detection recall:** fraction of injected invalidations that produce an attributable pause before task end.
- **False interrupt rate (FIR):** orchestrator interrupts not attributable to the injection (on injected runs) or any interrupt at all (on clean runs), divided by total interrupts.
- **Overhead:** total cost on clean runs minus S1's total cost on clean runs.
- **Success:** programmatic checker passes.

### 6.2 Kill gates (decide before running; do not move after)

| Gate | Question | Threshold (pilot) | If failed |
|---|---|---|---|
| KG0 (Phase 0) | Are compiled tripwires well-formed? | >= 70% of tripwires score 4/4 on the rubric (observable, parameterized, actionable, calibrated) AND for >= 80% of planned injections there exists at least one compiled tripwire that would catch it on paper | One prompt-iteration allowed, then re-score. Second failure: **kill the architecture claim**; salvage as a study of LLM monitor-compilation quality (NIER-scale). |
| KG1 | Do tripwires catch real injections? | Detection recall >= 60% overall AND >= 50% in at least 4 of 5 categories (S5) | 40-60%: drop weak categories, narrow the claim. < 40%: **kill**. |
| KG2 | Does the judge earn its cost? | S5 FIR <= 0.5 x S2 FIR, AND S5 FIR <= 0.7 x S4 FIR | Judge adds nothing: reframe as compile-only architecture (two tiers), revise paper claims, continue. |
| KG3 | Does it pay for itself? | On injected runs: S5 total cost < S1 total cost, OR (S5 cost <= 1.15 x S1 AND S5 success >= S1 success + 15 points). Additionally, clean-run overhead <= 12% of S1 cost. | Fit the break-even model; if it predicts crossover at fan-out <= 8 workers, proceed to full study with fan-out as a primary variable. If no plausible crossover: **kill the efficiency claim**, keep only correctness claims if KG1 passed. |
| KG4 | Does it beat cost-matched heartbeat? | S5 beats S3 on wasted work by >= 20% (median over injected pairs) OR on TTD by >= 2x at equal cost | Parity: the paper pivots to an honest comparative study ("when do compiled tripwires beat periodic revalidation?"), targeted at SEAMS/NIER scale, and the FSE flagship plan is dropped. Decide within 48 hours of seeing the table; do not negotiate with the data. |

### 6.3 Statistical posture

Three seeds cannot power significance tests, and the pilot does not pretend otherwise. Report medians with min-max ranges per cell; gate thresholds are set far above plausible noise (a 20% wasted-work margin, a 2x FIR ratio) precisely so that a pass or fail is legible without p-values. The full study supplies the 5-seed bootstrap protocol.

### 6.4 Phase 0 rubric (score each compiled tripwire 0/1 per property)

- **Observable:** references a signal the proxy can actually evaluate (status code, field name, hash, token state, passage content).
- **Parameterized:** contains concrete values, not categories ("status_in [404,410]" yes; "if the API changed" no).
- **Actionable:** includes a non-empty, plan-relevant replan hint.
- **Calibrated:** severity and scope are present and defensible given the assumption it monitors (audited by you against the task spec).

Also record per plan: tripwire count, compile tokens, compile latency, and coverage of the task's ground-truth assumption list (which assumptions have at least one monitor).

---

## 7. Threats the Pilot Accepts (Knowingly)

- **Synthetic world:** injections are cleaner than nature. Accepted: the pilot estimates mechanism viability, not ecological prevalence; the full study's real-suite wrapping addresses ecology. The tau-bench exploratory arm gives an early external-validity read.
- **Single injection per run:** no compound failures. Accepted for cleanliness; compound injections are a full-study condition.
- **Solo labeling:** attribution audits done by one person. Mitigation: deterministic trace rules do 90% of the labeling; ask Zeynep or a labmate to blind-audit 30 traces; report agreement.
- **Fan-out fixed at 4 workers:** the amortization thesis predicts benefits grow with fan-out, so 4 is conservative. If KG3 is borderline, one supplementary arm at fan-out 8 on 6 tasks is pre-authorized within budget.

---

## 8. Schedule (fits the FSE timeline from proposal v2)

| Days | Work |
|---|---|
| Optional, any June evening | Phase 0: DSL schema + compile prompt + 4 plans, hand-score. ~6 hours. |
| Jul 16-17 | World server + injection endpoint + fixture repo/corpus |
| Jul 18-19 | LangGraph harness (orchestrator + 4 workers) + proxy/counter/matcher |
| Jul 20 | Sentinel compile + judge prompts; DSL validation; trace schema |
| Jul 21 | Task specs (20) + success checkers; manipulation-check runs (S1) |
| Jul 22-23 | Calibrate heartbeat k; full run matrix (750 runs, batched evenings) |
| Jul 24-25 | Metrics, audits, kill-gate table; 48-hour decision window |
| Aug 1 | Decision memo: full study go / pivot / kill, with fitted break-even parameters |

Total: roughly 9 working days of focused effort, parallelizable around launch aftershocks since runs are unattended.

### 8.1 Overnight execution discipline (Path A)

The run matrix executes as unattended overnight batches. One night spans roughly two 5-hour rate windows, so plan for 4-6 nights total at limit-respecting concurrency. Rules:

- **Queue runner.** A single supervisor process in tmux on a machine that stays awake, with a job table (JSONL or SQLite) holding states pending/running/done/failed/throttled. Every session is wrapped in a hard `timeout` and `--max-turns` so one stuck worker cannot eat a window. On a rate-limit error: exponential backoff, then sleep until the window rolls, then requeue. The queue never dies; it waits.

```bash
while job=$(next_pending); do
  if ! timeout 360 run_session "$job"; then
    if was_throttled "$job"; then
      sleep_until_window_rolls; requeue "$job"
    else
      mark_failed "$job"   # inspect in the morning ops report
    fi
  fi
done
```

- **Information-first night ordering.** Night 0: manipulation checks (S1 on all injected pairs, seed 1) plus an empirical measurement of runs-per-window on the actual plan tier; this calibrates every subsequent night and the heartbeat cost-matching. Night 1: S5 + S1, seed 1 (the KG1/KG3 core). Night 2: S3 cost-matched heartbeat (KG4) + S4/S2, seed 1 (KG2). Nights 3-5: seeds 2-3, clean-run overhead measurements, exploratory arms. A dying architecture shows its corpse by morning two; a healthy one earns the remaining nights.
- **Shared-budget rule.** Batch nights draw from the same weekly subscription allowance as daytime usage. Schedule the heavy nights immediately after the weekly reset and keep daytime Claude Code usage light on those days, or the pilot will throttle launch work (and vice versa).
- **Ops vs. science dashboards.** The morning check covers operations only: completions, throttle events, failure rate, malformed traces. Gate metrics are computed exactly once, when the planned matrix completes. Peeking at half-collected gates invites mid-stream prompt tweaks that void the pre-registration; the kill thresholds were frozen precisely so that nobody, including the author at 7am, renegotiates with partial data.

---

## 9. What the Pilot Buys the Paper

If gates pass, the pilot is not throwaway: it becomes the **preliminary study subsection** that SE reviewers expect (motivating the judge-model choice, the category set, and the heartbeat comparison), the manipulation-check methodology transfers verbatim to the full benchmark, and the fitted break-even parameters give the full study its primary hypothesis to confirm out-of-sample. If gates fail, you will have spent under $300 and nine days to avoid spending August on a dead architecture, and KG0/KG1 failure data is itself publishable at NIER scale as a negative result on LLM monitor compilation.

**Pre-registration discipline:** commit `prereg.md` (Sections 6.1, 6.2, 6.4 verbatim) to the repo before the first Phase 1 run. The kill gates were written by the person you are today; the person staring at a near-miss table in late July does not get a vote.
