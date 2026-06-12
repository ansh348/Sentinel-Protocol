# Sentinel Protocol

## Compiling Plan Assumptions into Typed Tripwires for Interrupt-Driven Multi-Agent LLM Systems

**Ansuman Mullick, Bilkent University**

**Status:** Research Proposal **v6.1** — Phase 1 pilot **COMPLETE**; post-verdict adjudication battery **COMPLETE**. Kill gates computed once on the complete 195-cell matrix (2026-06-11): **KG1 FAIL (kill band), KG2 FAIL, KG3 FAIL, KG4 PASS (TTD arm)**. Per the pre-registered branches: the v1 detection claim is killed; the v1 judge tier is falsified as an interrupt filter; **the v1 efficiency claim is killed** (break-even fit: no crossover at any fan-out, §11.4); the architecture's core mechanism — plan-compiled tripwires — survives quantified (3× faster detection than a cost-matched heartbeat where signals recur). The external red-team's rival causal stories and design attacks were adjudicated from the banked traces under pre-committed rules (archaeology v2, §11.11): two refuted, two partially confirmed and absorbed, and a zero-LLM shadow replay validated v2's probe mechanism in-benchmark (projected recall ceiling 78%, upper bound). The project continues as **architecture v2 (probe-primary, two-tier) under a fresh pre-registration (Phase 1b)**; v1's verdict is reported in the paper regardless of v2's outcome.
**Primary target:** FSE 2027 (Research Papers, deadline Oct 2, 2026), **conditional on Phase 1b gates and two pre-committed schedule gates (§13)**. Fallbacks: ICSE 2027 NIER (Oct 23, 2026), SEAMS 2027, ASE 2027.
**Date:** June 12, 2026 (v6.1, post-battery). Priors: v6 (June 12, 2026, post-verdict), v5 (June 10, 2026).

---

## Abstract

Multi-agent LLM systems operate under batch orchestration: an orchestrator dispatches tasks to worker agents, waits for all to complete, then aggregates results. When a plan-invalidating event occurs mid-execution (a dependency renamed, an endpoint removed, a schema drifted, a retrieved fact contradicted), workers continue burning tokens, tool calls, and wall-clock time on a plan that is already dead. Production orchestrator-worker systems consume roughly 15× the tokens of single-agent chat [27], and that multiplier applies to wasted work just as it applies to useful work. The root cause is a cognitive coupling problem: workers cannot simultaneously execute local tasks efficiently and reason continuously about global plan validity.

We propose **Sentinel Protocol**, an interrupt architecture in which a sentinel compiles the orchestrator's plan assumptions into typed, observable tripwire conditions at plan-time, workers pattern-match cheaply against them during execution, and validated invalidations interrupt the orchestrator for replanning. Viewed through the software-engineering lens, it is a MAPE-K loop whose Monitor and Analyze components are generated per-plan by an LLM under an ontology constraint rather than engineered by hand.

A pre-registered pilot of the full v1 architecture — a 195-cell matrix (13 task variants × 5 systems × 3 seeds) over a deterministic injectable world, with frozen kill gates, cryptographic custody pins, manipulation-validated injections (9/9 qualified), and a numbered deviation log — **completed on June 11, 2026**. The verdict, computed once on the complete matrix and confirmed by the mandated attribution audit (13/13 sample agreement):

- **Killed:** the v1 detection claim. Strict recall 35% against a pre-registered 60% bar and a 40% kill floor; one of five failure categories above 50%.
- **Falsified:** the v1 judge tier as an interrupt filter. Median false-interrupt rate 1.0; every escalation that reached the judge was approved, including the noise.
- **Failed as predicted:** clean-run economics at pilot task scale (8–26 tool calls), exactly the regime the paper's own break-even model places below the crossover.
- **Survived, quantified:** where invalidation signals recur on observed surfaces, compiled tripwires detect **3× faster** than a cost-matched periodic-revalidation baseline (median 3 vs 9 tool calls; pre-registered bar 2×).

Exploratory trace archaeology attributes the recall failure not to compilation but to **observation** — and a post-verdict adjudication battery (raw-event replay, cross-system trajectory analysis, zero-LLM shadow replay; §11.11) sharpened the mechanism against external red-team rivals. The injected surfaces were *not* intrinsically single-visit: on identical seeds, baseline systems re-observed every one of them (12/12). What starved observation was the monitor itself — false interrupts, driven by judge credulity on field-shape evidence, consumed the run lifetime in which re-observation would have occurred, and self-injured clean runs (7 of 9 clean-cell failures were sentinel-induced). The battery also refuted two rival explanations outright (telemetry loss: 9/12 starved cells had zero raw post-injection surface observations; horizon failure: 0/17 runs died before the surface was reachable) and corrected one v1 narrative claim: the matcher's defect was not a singleton but a dead-pattern class (84 armed-but-unfireable URL patterns across 8 cells). We state the pilot's two boundedness findings — **monitor compilation is information-bounded** (KG0) and **detection is observation-bounded** (Phase 1), the latter now refined: in budget-bounded agent execution the observation bound was *self-inflicted*, because monitoring precision and recall are coupled through the run's finite lifetime. These are empirical regularities of this setting with known antecedents in partial-observability and runtime-verification theory, not theorems.

Architecture v2 follows mechanically from the trace evidence, and its central mechanism was validated *before being built*: a zero-LLM shadow replay compiled deterministic probes for all nine pilot injections and executed them against byte-identical replayed worlds. Content-shaped categories the raters called structurally unprobeable proved deterministically decidable (8/8 RETRIEVAL_INTEGRITY/TOOL_CONTRACT payloads; RETRIEVAL_INTEGRITY 0/3 → 3/3 projected), the probe-primary corroboration policy blocked all 18 false interrupts, and projected strict recall reached 21/27 (78%) — an upper bound under stated assumptions on the pilot's own injections, not a prediction. The replay also broke one v2 design clause as drafted (second-signal corroboration self-corroborates under noise storms; deleted) and retired the judge tier on its own record (34/34 approvals, two genuine signals suppressed, one hallucinated reading approved at 0.98 confidence). v2 is therefore **compiled active probes on a perturbation-isolated side channel** (periodic revalidation's cadence at tripwire prices), **probe-primary corroboration with a status-coded fast path**, a priced abort policy, and recovery-typed replan hints — measured under Phase 1b's freshly frozen gates, with thresholds inherited verbatim from v1's pre-verdict freeze and held-out injection categories escrowed by a non-implementer. Clean-run economics did not survive: the pre-committed break-even fit found no crossover at any fan-out (P = 1.00 over 1,000 bootstraps), and the v1 efficiency claim is killed in ink; v2's economics must be re-established from scratch with probe overhead booked as waste. A naive anomaly-gated baseline outperformed the v1 architecture on detection (15/27 vs 9/27, at zero false interrupts) — reported prominently, and carried into Phase 1b as a mandatory comparison arm. We additionally propose **TripwireBench** over established suites (GAIA, tau-bench, SWE-bench Verified subsets) for the full study, and a break-even model characterizing when plan-compiled monitoring pays. Sections 11.6–11.11 report the complete pilot and adjudication record.

---

## 1. The Problem

Large language model multi-agent systems decompose complex work across specialized agents. Production systems such as Anthropic's Research feature use an orchestrator-worker pattern: a lead agent plans, spawns parallel subagents, and synthesizes their findings [27]. AutoGPT, CrewAI, LangGraph, AutoGen, and MetaGPT follow analogous patterns.

Two empirical facts frame the economics:

1. **Multi-agent systems are token-hungry.** Agents use roughly 4× the tokens of chat interactions, and multi-agent systems roughly 15× [27]. Every unit of wasted work is amplified by the fan-out factor: when a plan dies, it is not one agent burning tokens on a dead plan but N parallel agents.
2. **Failures are systemic, not incidental.** The MAST study annotated 1,600+ execution traces across seven frameworks and identified 14 recurring failure modes in three clusters [14]. Multi-agent systems fail in patterned, taxonomizable ways; this motivates patterned, taxonomizable defenses.

The failure mode we target emerges when the world changes during execution: a dependency renamed, an endpoint returning 404, a schema drifted, a retrieved document contradicting a planning assumption. In batch orchestration, the orchestrator discovers these invalidations only after all workers report back; recent diagnostic work confirms wasted computation is a measurable, recurring cost in deployed multi-agent systems [16].

The root cause is a cognitive coupling problem: for a worker to recognize that a local discovery invalidates the global plan, it must simultaneously (i) execute its assigned task and (ii) reason about the discovery's global implications. These are two fundamentally different cognitive loads. Existing interrupt mechanisms (e.g., LangGraph's `interrupt()` [22]) provide the plumbing for pausing execution, but not the intelligence for deciding when to pause, what constitutes a plan-breaking event, or how to filter noise. **The mechanism exists. The policy layer does not.** Sentinel Protocol is that policy layer.

**Phase 1 addendum (new in v6; refined in v6.1).** The pilot sharpened the problem statement itself. Detection of a mid-execution invalidation requires not only that a monitor *exist* for the violated assumption, but that the violated surface be *observed again* after the violation. Task-driven execution provides re-observation for free only where the signal recurs (e.g., authentication: every subsequent call fails). Any credible solution must therefore solve two problems: *what to watch* (compilation) and *how the watched surface keeps being seen* (observation). v1 solved only the first. *(v6.1 refinement, from the adjudication battery: in the pilot, the failure of re-observation was not the world's geometry — baseline systems re-visited every starved surface on identical seeds — but the monitor's own noise economy consuming the lifetime in which re-visits would have occurred. The observation problem is real, and v1 manufactured it for itself. §11.11.)*

---

## 2. Positioning: What Sentinel Protocol Is and Is Not

The 2025–2026 literature on agent reliability is crowded. To prevent reviewer mis-shelving, the boundaries are stated explicitly; each row names the nearest neighbor and the delta.

| Adjacent area | Representative work | What they do | What Sentinel Protocol does differently |
|---|---|---|---|
| Safety enforcement | AgentSpec (ICSE'26) [9], Agent-C [10], Pro2Guard [11], ProbGuard [12], LlamaFirewall [13] | Enforce human-written safety rules over agent actions | Monitors machine-compiled plan-validity conditions derived from the orchestrator's own plan; the goal is efficiency and replan-correctness, not action safety |
| Observability & diagnosis | AgentOps [15], LumiMAS [17], wasted-computation diagnosis [16], DiLLS [18] | Instrument, trace, and diagnose failures, largely post-hoc, for humans | Prevents waste in-flight via interrupts; the consumer of the signal is the orchestrator, not a dashboard |
| Schedulers & orchestration | Graph Harness [19], TDP, Plan-and-Act, Routine | Define how plans are structured, dispatched, versioned, recovered | Defines when and whether to trigger those recovery paths; a policy layer that plugs into such schedulers |
| Failure taxonomies | MAST [14], SHIELDA [20] | Describe and classify failures after the fact | Uses a failure ontology generatively, as the inductive bias for compiling monitors before execution |
| Classical execution monitoring | Assumption-based planning [2], plan repair [3] | Monitor preconditions of symbolic plans against a world model | Adapts the paradigm to LLM agents, where the "world" is APIs, repositories, schemas, retrieved knowledge, and the monitor must be synthesized from a natural-language plan |
| Plan-assumption runtime verification | **RVPLAN** [6, 34], Bozzano et al. [35], Bensalem et al. [36], Ferrando & Cardoso 2025 [37] | Mechanically translate formal STRIPS/PDDL preconditions into Past (FO-)LTL monitors over a labeled perception stream; detection-only, noise-free by construction; replanning deferred to future work | Synthesizes the specification itself from a natural-language plan where no formal spec exists; observes unlabeled, single-visit tool telemetry rather than a self-narrating world; and because the resulting signal stream is noisy, adds the judged/priced/probe-corroborated interrupt layer and measures its economics (§9.3 confrontation) |
| Self-adaptive systems | MAPE-K [23, 24, 25] | Engineer Monitor-Analyze-Plan-Execute loops at design time, by hand | Generates the Monitor and Analyze layers per-plan, at runtime, by an ontology-constrained LLM (Section 3.5) |

**One-sentence version:** Sentinel Protocol is an interrupt policy compiler and filter for multi-agent LLM systems, occupying the layer between interrupt mechanisms (which exist) and orchestration recovery protocols (which exist), neither of which decides what to watch for.

**Phase 1 addendum.** The pilot adds an empirical boundary to this table: the policy layer's value concentrates in *detection latency* (validated at 3× vs a cost-matched heartbeat) and is destroyed by *uncorroborated interruption* (falsified: judge-approved noise starved recall and injured clean runs). **v6.1 addendum (post-battery).** The shadow replay revealed the architecture's honest shape: under the probe-primary policy the interrupt stream becomes nearly vestigial (15 of 16 true interrupts suppressed, recall recovered through the probe channel instead). v2 is therefore best described not as a filtered-interrupt system but as **scheduled deterministic verification compiled from the plan, with a status-coded interrupt fast lane** — a narrower, sharper, and more defensible identity than v1 claimed.

---

## 3. Sentinel Protocol: Architecture

> **v6 status note.** This section describes the architecture as designed (v1) with Phase 1 verdict annotations inline. The v2 revision, with each change citing the trace evidence that motivates it, is specified in Section 11.9.

Sentinel Protocol resolves the coupling problem by separating plan-awareness from task execution across tiers. Each tier has exactly one job.

### 3.1 Tier 1: Orchestrator

The Orchestrator holds the global strategy. It produces the plan, dispatches work to subagents, and is the sole entity authorized to replan. It receives only filtered, validated interrupts; when one arrives, it pauses the affected scope, ingests the new information, replans, and redispatches with a fresh tripwire compilation. *(Phase 1: functioned as designed; replan quality, not replan mechanics, was the weak link — see Section 11.8.)*

### 3.2 Tier 2: Sentinel Agents

Sentinel agents perform two functions:

**Compile-time function (expensive, once).** The sentinel receives the plan and reasons about its assumptions, producing typed, observable tripwire conditions formatted for cheap runtime matching — expensive reasoning performed once, amortized across execution. *(Phase 1: substantially validated. One coverage miss (L1) and one matcher defect (L2-true) across 27 injected cells; KG0 would-catch 89%.)*

**Runtime function (filter and judge).** When a subagent escalates a potential match, the sentinel evaluates whether it is genuinely plan-breaking or noise; only validated interrupts propagate, each carrying a recommended replan move. *(Phase 1: **falsified as implemented.** The v1 judge approved all 34 escalations that reached it, including 18 unattributable ones — a rubber stamp, not a filter. KG2 FAIL; see Sections 11.7–11.9.)*

The design principle stands as stated in prior systems: pay expensive inference once at compile time, keep the hot path cheap and deterministic. Phase 1 adds its corollary: the hot path must also *observe* — cheap deterministic probes belong to the compiled output, not only passive predicates (Section 11.9).

### 3.3 Tier 3: Subagents

Subagents execute tasks with a checklist of tripwire conditions. They require no global reasoning; their monitoring obligation reduces to pattern matching against pre-compiled conditions. If a tripwire fires, they escalate to the sentinel with an evidence payload. *(Phase 1: matching worked where signals were observed; the binding constraint was that starved surfaces stopped being observed — Section 11.8, Finding 2, refined in v6.1: the starvation was the monitor's own noise economy, not the world's geometry.)*

### 3.4 Information Flow

| Phase | From | To | Payload |
|---|---|---|---|
| 1. Plan | Orchestrator | Sentinel | Global plan + assumptions |
| 2. Compile | Sentinel | Subagents | Task + typed tripwire checklist |
| 3. Execute | Subagents | (local) | Task execution with tripwire monitoring |
| 4a. Escalate | Subagent | Sentinel | Tripwire match + evidence payload |
| 4b. Filter | Sentinel | (internal) | Noise vs. genuine invalidation judgment |
| 5. Interrupt | Sentinel | Orchestrator | Validated interrupt + recommended action |
| 6. Replan | Orchestrator | All agents | Pause signal + revised plan + new tripwires |

### 3.5 Relation to MAPE-K: What Is Actually New Here

SE reviewers will, correctly, recognize this loop. The MAPE-K reference model has organized the self-adaptive systems field since Kephart and Chess [23], with two decades of elaboration at SEAMS [24], including early proposals to embed LLMs inside MAPE-K agents [25, 26]. We do not claim to have invented the loop. The mapping is exact:

| MAPE-K component | Sentinel Protocol realization |
|---|---|
| Monitor | Subagents pattern-matching compiled tripwires (v2: plus scheduled compiled probes) |
| Analyze | Sentinel's runtime judge (v2: corroboration + priced abort, or removed — two-tier) |
| Plan | Orchestrator replanning on validated interrupt |
| Execute | Orchestrator redispatch with revised plan |
| Knowledge | Failure ontology + tripwire knowledge graph (Section 7) + Phase 1 outcome posteriors (Section 6) |

The claimed novelty is in how the Monitor and Analyze components come to exist: (1) **monitors are compiled, not engineered** — synthesized per-plan, at runtime, by an LLM constrained by a fixed failure ontology and typed DSL; to our knowledge no prior MAPE-K instantiation generates its own Monitor specification from the plan it is monitoring; and (2) **the Analyze tier is an interrupt-economics filter** — token-metered systems make both false interrupts and missed invalidations directly billable. Phase 1 stress-tested claim (2) and broke its v1 implementation while confirming its premise: interrupt economics are real enough that an uncalibrated filter *destroys* value (Section 11.8). This positioning converts the strongest anticipated objection ("this is just MAPE-K") into the framing device, now with the empirical scar to prove the loop's Analyze tier is the hard part.

---

## 4. Tripwire Specification

A tripwire is a pre-compiled, observable condition that a subagent can check cheaply during execution. Four properties distinguish actionable tripwires from vague monitoring wishes:

- **Observable.** Checkable from signals the subagent can actually observe: tool outputs, HTTP status codes, schema versions, file hashes, test results, retrieved content. *(v6: Phase 1 splits this property in two — observable in principle vs. observed in practice. See Section 11.8.)*
- **Parameterized.** Concrete, not poetic. Bad: "If the API changed." Good: "If GET /v1/responses returns status 404 or 410, stop and re-fetch docs."
- **Actionable.** Every tripwire includes a recommended replan move. *(v2: the hint is typed by recovery class — Section 11.9.)*
- **Calibrated.** Severity and scope annotations determine routing behavior.

### 4.2 Severity and Scope Taxonomy

| Severity | Meaning | Action |
|---|---|---|
| CRITICAL | Core plan assumption violated; continuing wastes compute or risks harm | Immediate interrupt to Orchestrator; affected scope pauses |
| WARNING | Plan may need adjustment; ambiguous whether plan survives | Escalate to Sentinel for judgment; subagent continues cautiously |
| INFO | Unexpected observation; not plan-breaking | Log for post-execution review |

Scope is orthogonal: global (invalidates the entire plan) or local (invalidates the current subplan). The two-clause adjudication principle from KG0 governs severity assignment and is preserved in v2: WARNING is defensible when the monitored data plausibly survives in recoverable form; CRITICAL is required when nothing recoverable remains or when continuing invites the agent to fabricate evidence or corrupt a decision.

### 4.3 Tripwire DSL

```json
{
  "id": "tw_api_404_v1_responses",
  "severity": "CRITICAL",
  "scope": "global",
  "assumption": "API endpoint /v1/responses exists and returns 200",
  "signal": {
    "type": "http_response",
    "method": "GET",
    "url": "https://api.example.com/v1/responses",
    "match": { "status_in": [404, 410] }
  },
  "action": {
    "on_trigger": "PAUSE_AND_REPLAN",
    "hint": "Re-fetch API docs; update endpoint + client config"
  },
  "evidence_fields": ["status", "body_snippet", "request_id"]
}
```

Grammar (v1, with v2 extensions marked):

```
tripwire   := id severity scope assumption signal action evidence
              [probe] [recovery_class] [evidence_class]          # v2
severity   := CRITICAL | WARNING | INFO
scope      := global | local(subplan_id)
signal     := source predicate
source     := http_response | tool_output | file_hash | schema_version
            | test_result | retrieval_content | budget_counter | auth_state
predicate  := status_in(list) | regex(pattern) | neq(expected)
            | threshold(metric, op, value) | contradicts(assumption_id)
probe      := { method, target, cadence, cost_class }             # v2: active re-observation
recovery_class := REMAP | REINTERPRET | REDO | RECONCILE | RETREAT  # v2
evidence_class := status_coded | content_shaped | field_shape | counter  # v2: trust prior
action     := PAUSE_AND_REPLAN | ESCALATE_TO_SENTINEL | LOG | ABORT_SALVAGE  # v2 adds ABORT
              [hint: free_text]
```

The deliberate design choice, relative to runtime verification, is to trade full temporal logic (LTL/ptLTL monitor synthesis [4, 5]) for a predicate language over discrete tool-call events. Phase 1 vindicated the predicate language and indicted its *passivity*; the v2 `probe` field is the repair (Section 11.9). Design rule from KG0 Finding 1, retained: every constraint the model must obey lives in schema-visible field descriptions or enums — constraints in comments or prose do not transmit.

---

## 5. Failure Ontology: Typed Tripwire Categories

The failure ontology is the sentinel's inductive bias: compiling tripwires from a plan becomes a bounded checklist traversal rather than open-ended "what could go wrong" reasoning.

| Category | Description | Typical Signals | **Phase 1 strict recall** |
|---|---|---|---|
| DEPENDENCY_VERSION | Library/package/framework version changed | Import errors, deprecation warnings | (not injected in pilot) |
| API_SURFACE | Endpoint changed, removed, unexpected schema | HTTP 404/410, schema validation failures | below 50% (exact: archaeology_v1.md) |
| SCHEMA_DRIFT | Data format diverged from plan assumptions | Column missing, type mismatch | below 50% (exact: archaeology_v1.md) |
| TOOL_CONTRACT | Tool/skill violates declared contract | Quality gate skipped, forbidden op | **1/6** |
| RETRIEVAL_INTEGRITY | Retrieved knowledge contradicts plan assumptions | Stale facts, contradicted context | **0/3** |
| PERMISSION_AUTH | Credentials expired, permissions revoked | HTTP 401/403, token expiry | **5/6 — the passing category** |
| QUALITY_GATE | Output quality check failed | Test failure, malformed output | (folded into TOOL_CONTRACT pair in pilot) |
| RESOURCE_BUDGET | Token/cost/time budget threshold | Counters, accumulators | (not injected in pilot) |

Categories carry soft membership weights; hierarchical gating with per-category escalation thresholds prevents interrupt spam (derived empirically in the pilot build — KG0 Finding 4).

**Phase 1 addendum — signal shape determines detectability.** The per-category results decompose cleanly by *signal shape*, not by ontology quality. PERMISSION_AUTH passed because its signal is loud, sustained, and status-coded: every call after expiry re-observes the violation. RETRIEVAL_INTEGRITY and TOOL_CONTRACT failed because their signals are content-shaped and single-visit: status/path predicates rarely express them, and nothing in task-driven execution re-observes them. The ontology's coverage was nearly complete (one L1 miss in 27 cells); its categories differ enormously in *observability under passive monitoring*. This is the empirical bridge to v2's active probes: the probe field exists to convert every category's signal shape into PERMISSION_AUTH's.

### 5.1 Crosswalk to Existing Taxonomies

MAST [14] taxonomizes agent-endogenous failure (the agents misbehave); our ontology covers the world-exogenous complement (the agents behave; the world the plan assumed has changed). SHIELDA [20] catalogs exceptions at the individual-agent level; our categories operate at the plan-assumption level, and the two compose: SHIELDA-style local handling first, tripwire escalation when local handling cannot preserve the assumption. TripwireBench's annotation schema records both label sets. The ontology's job is not to be the one true taxonomy; it is to be a generative prior over monitors — complete enough to catch most injected invalidations, small enough that compilation stays cheap. Phase 1 measured both halves: completeness held (one L1); "catch" turned out to require observation machinery the prior alone cannot supply.

---

## 6. Sentinel Calibration: The Prior-to-Posterior Problem

A sentinel that produces bad tripwires is worse than no sentinel — **Phase 1 proved this literally** (Section 11.7: seven of nine clean-cell failures were sentinel-induced). The calibration framing stands: the failure ontology is the prior; execution outcomes are the posterior.

- **Initial state (prior).** Default tripwire templates per category, parameterized per plan; solves cold start.
- **Outcome tracking.** Every fire tagged true positive, false positive, or missed detection; stored as edges in the tripwire knowledge base.
- **Template refinement (posterior).** Each category c maintains a Beta(α_c, β_c) posterior over "an escalation in c is genuine"; the escalation threshold for c is a monotone function of the posterior mean with a floor for CRITICAL severities. No RL; conjugate counting.

**v6 status.** In v1 this loop ran cold: no outcome history existed, every prior was uninformative, and the judge inherited no skepticism about any evidence class — the mechanistic root of its credulity (Section 11.7, FIR anatomy). **Phase 1's 195 fully-traced cells are the loop's first real posterior data.** v2 does not merely keep Section 6; it *executes* it: per-category and per-evidence-class posteriors initialized from Phase 1 outcomes, with the before/after delta (v1 measured → calibration applied → v2 measured) reported as a primary result. This converts the paper's weakest v1 moment into its designed two-study structure.

---

## 7. Tripwire Knowledge Base as a Temporal Graph

Compiled tripwires, their outcomes, and fix patterns are stored in a temporal property graph (Neo4j/Graphiti or any property-graph store [30]), enabling retrieval-augmented tripwire generation. Node types: PlanStep, Assumption, Tripwire, Signal, Outcome, FixPattern. Edges: depends_on, monitors, uses_signal, suggests, triggered_in, supersedes. Temporal decay retires tripwires for deprecated surfaces; community detection clusters related failure modes for cluster-level retrieval. *(Unchanged from v5; Phase 1 populates the first Outcome edges.)*

---

## 8. Template Sources: From Specifications to Tripwires

Three high-precision sources that do not require model creativity:

**8.1 Tool contracts and skill specifications** compile directly (e.g., "render and inspect after each meaningful update" → WARNING tripwire on modified-without-render).

**8.2 API documentation and schema definitions.** OpenAPI specs, GraphQL schemas, and migration files compile mechanically into API_SURFACE tripwires for every endpoint the plan touches. *(Empirically validated: KG0 Finding 2 — mechanically supplying the environment surface lifted would-catch coverage from 67% to the passing 89%. Environment surfaces are first-class compiler inputs.)*

**8.3 Historical failure patterns** from the knowledge base (Section 7).

**8.4 (new in v6) Probe templates from the harness's own validation machinery.** The pilot's manipulation-check apparatus included *premise probes* — cheap deterministic re-checks of injected surfaces — and one of them caught the c1/doc_contradiction injection that the compiled passive set was blind to. The manipulation check invented the monitor the compiler lacked. v2 promotes this mechanism into the DSL itself: probes are compiled per-tripwire from the same mechanical sources as 8.2 (a HEAD request per endpoint, a schema fingerprint per consumed format, a gate-status re-read per contract step, a premise re-fetch per load-bearing retrieval), scheduled by the matcher layer at deterministic cost. Structure from the ontology, signal from outcomes, **observation from probes**.

---

## 9. Related Work

*(Carried from v5 with Phase 1 annotations; full prose in v5 archive. All references re-verified at v5; re-verify at submission — SE venues desk-reject fabricated references.)*

**9.1 Self-adaptive systems and MAPE-K** [23, 24, 25, 26]: we instantiate the loop but invert the provenance of Monitor/Analyze — compiled per-plan at runtime by an ontology-constrained LLM (Section 3.5).

**9.2 Execution monitoring and plan repair** [1, 2, 3]: the direct intellectual ancestors; we adapt the paradigm to worlds made of APIs, repositories, schemas, and retrieved knowledge, with assumptions extracted from natural-language plans.

**9.3 Runtime verification and monitor synthesis** [4, 5, 6]: we borrow spec-to-monitor compilation, substituting a practical predicate DSL over discrete tool-call events for full temporal logic. *(v6 note: Phase 1 indicts passivity, not the predicate trade-off; the probe extension keeps the DSL deployable while restoring the RV tradition's insistence that monitors observe.)*

**9.3.1 RVPLAN, confronted (new in v6.1).** Reference [6] — Ferrando & Cardoso's RVPLAN (ICAART 2022; workshop version VORTEX@ISSTA 2021 [34]) — is the named nearest ancestor and is engaged here directly rather than cited in passing. RVPLAN automatically synthesizes runtime monitors from STRIPS/PDDL planning models, translating action preconditions into Past LTL (instantiated, per-plan) or Past FO-LTL (parameterised, per-domain) and compiling monitors via DEJAVU; violations of the planner's assumptions are detected at execution time, with replanning as the intended consumer. The paradigm — *monitor the plan's assumptions at runtime, interrupt for replanning* — is therefore established prior art, with still-earlier roots in on-board-autonomy assumption monitoring (Bozzano et al. [35]) and the V&V-meets-planning survey frame (Bensalem, Havelund & Orlandini [36]); the line remains active (monitor-driven action-specification updating and replanning, Ferrando & Cardoso, VORTEX 2025 [37]). Sentinel Protocol ports this established paradigm to a regime in which each of its three enabling assumptions fails. **First, the specification does not exist.** RVPLAN's "compilation" is linear-time syntactic translation of precondition sets already sitting machine-readable in a domain file; our compiler must *extract and invent* the load-bearing assumptions of a natural-language plan under an ontology prior — synthesis where no formal spec exists, with information-bounded coverage as the measured consequence (Finding 1). **Second, the world does not narrate itself.** RVPLAN's monitor consumes a benevolent perception stream of ground propositions in the monitor's own vocabulary; our monitors observe raw, unlabeled, single-visit tool telemetry, and the pilot's central empirical result (Finding 2, refined in §11.11) concerns precisely the observation gap their setting assumes away. **Third, the signal stream is noisy.** In a deterministic propositional stream a precondition either holds or it does not — RVPLAN's monitors cannot false-fire, so nothing needs filtering, judging, pricing, or aborting; in our regime the interrupt-economics layer is where the architecture lives and where v1 failed measurably. RVPLAN's evaluation is monitor-synthesis timing on one rover example; TripwireBench contributes manipulation-validated injections, recall/FIR/TTD/wasted-work metrics, and the break-even model. The confrontation strengthens rather than threatens the contribution: an established paradigm, demonstrated in classical planning, breaks on contact with the LLM-agent regime in three measurable ways, and this work characterizes what it takes to survive there.

**9.4 Runtime enforcement and guardrails for LLM agents** — the closest contemporary cluster: AgentSpec [9], Agent-C [10], Pro2Guard [11], ProbGuard [12], LlamaFirewall/Task Shield [13]. All enforce externally authored constraints, predominantly for safety. Deltas unchanged: provenance (compiled from the plan), objective (validity and efficiency), response (validated interrupts → replanning). Weak-to-strong monitoring [8] supports selective filtering over exhaustive review.

**9.5 Failure taxonomies** — MAST [14], SHIELDA [20]: descriptive and agent-endogenous; our ontology is generative and world-exogenous (crosswalk in 5.1).

**9.6 Observability and diagnosis** — AgentOps [15], LumiMAS [17], wasted-computation diagnosis [16], DiLLS [18], Watson (ASE'25, cognitive observability): this line measures and explains waste for humans; Sentinel Protocol acts on it in-flight. The wasted-computation results independently validate the premise that post-invalidation burn is first-order.

**9.7 Orchestration frameworks and interruptible execution** — LangGraph `interrupt()` [22] (mechanism without policy); Graph Harness [19] (escalation ladders that consume validated interrupts); parallelized planning-acting [7]; learning to interrupt [21]; Anthropic's production economics [27].

**9.8 Author's prior work (one paragraph, self-contained).** Sentinel Protocol applies an architectural principle validated in two prior systems: fixed abstract ontologies constraining local LLM inference with deterministic global structure — LexCGraph (doctrine ontology constraining legal-graph extraction [28]) and Fortunate Recall (behavioral ontology conditioning memory decay [29]). Here, a failure ontology constrains monitor compilation. Each system stands alone; the recurrence is evidence the principle generalizes. *(Kept at exactly this length per v5's note.)*

---

## 10. Claims, Stated Explicitly — Now With Empirical Status

SE reviewers reward papers that name their deltas. v6 additionally names what the pre-registered pilot did to each claim.

1. **Plan-to-monitor compilation.** Tripwires compiled from a natural-language plan's assumptions, ontology as inductive bias, DSL as output type. Nearest neighbors, now confronted by name: RVPLAN's STRIPS-to-LTL monitor synthesis [6, 34] (§9.3.1), RV monitor synthesis [4, 5], AgentSpec [9] (human-authored specs). **The claim as narrowed by the red-team and the RVPLAN read:** not "monitors compiled from plans" (done, 2021) and not "LLM-generated monitors" (an active cluster), but *specification synthesis where no formal spec exists, observation over unlabeled single-visit telemetry, and interrupts that must be judged and priced because the stream is noisy — with the interrupt economics measured.* All three conditions are false in the classical-planning regime and load-bearing here. **Phase 1 status: substantially validated and sharpened.** 89% would-catch (KG0); one live coverage miss (L1) across 27 injected cells; but compilation alone is insufficient — detection is observation-bounded (Finding 2). *(v6.1: the "one matcher defect" half of this status is corrected — the defect was a class, not a singleton; §11.11.)* The claim narrows to: *compilation determines what can be detected; observation determines what is.* v2 compiles both, and the battery's shadow replay establishes the mechanism's in-benchmark feasibility (8/8 content-shaped payloads deterministically decidable at zero LLM cost; §11.11).

2. **Sentinel as interrupt filter (compiler and judge).** **Phase 1 status: falsified as implemented (v1). v6.1 status: resolved by adjudication.** The uncalibrated judge approved 34/34 escalations, including all 18 false ones; median FIR 1.0; KG2 FAIL. The battery completed the post-mortem: across the corpus the judge supplied *negative* semantic value — zero correct filtering, two genuine signals ruled NOISE (the L4 cells), and one hallucinated misreading approved at 0.98 confidence (§11.11's specimen). Per the pre-committed KG2 branch and pre-commitment P3, **the two-tier (no-judge) configuration is the designated primary architecture**; the rebuilt judge survives only as an exploratory arm. Corroboration is redesigned **probe-primary**: the shadow replay showed the drafted second-signal clause self-defeats (noise storms self-corroborate — 6/18 false interrupts passed it, two on a clean cell) while probe confirmation blocks 18/18 false with identical projected recall; the status-coded fast path is retained (zero false interrupts in-corpus carried status ≥ 400). The premise survives — interrupt economics are real and uncorroborated interrupts destroy value — and v2 implements it through deterministic verification rather than semantic adjudication.

3. **Failure ontology as generative prior with conjugate calibration.** **Phase 1 status: mixed, informative.** Generative coverage held (one L1 miss); detectability varies by signal shape, not category quality (Section 5 addendum); and the calibration loop — which ran cold in v1 — now possesses its first genuine posterior data. The v1→v2 delta *is* the claim's test.

4. **TripwireBench.** Injection-based benchmark over established suites measuring wasted work, time-to-detect, false-interrupt rate. **Phase 1 status: strengthened.** The pilot contributes manipulation-validated injections (9/9 qualified — injections proven to wound the baseline before any system was measured), a qualification rule upgrade for v2 (*bites the batch AND an oracle recovery exists*, with deliberately unrecoverable cells retained as labeled retreat-condition cells measuring abort quality), and a salvage-score secondary metric.

**New claims earned by Phase 1 (5–8):**

5. **Two boundedness findings for compiled monitoring** *(v6.1: "findings," not "laws" — the rater adjudication stands: these are empirical regularities of this setting with named antecedents in partial observability, monitorability, and diagnosability theory [4, 5, 36], not theorems).* Compilation is information-bounded (KG0 Finding 2: coverage rises mechanically with supplied environment surface) and detection is observation-bounded (Phase 1: 12 of 18 misses were armed, correct tripwires whose surfaces were never re-observed). **v6.1 refinement (battery, §11.11):** the observation bound in the pilot was *self-inflicted* — on identical seeds, baselines re-observed every starved surface (12/12); the sentinel's own noise economy consumed the lifetime in which re-observation would have occurred. Together the findings define the design space any plan-compiled monitor must occupy, with the coupling (claim 6) as the mechanism connecting them.

6. **Precision-recall coupling through run lifetime (H1).** In budget-bounded agent execution, false positives starve recall: noise storms consumed runs before true signals arrived (172 non-surface fires in a single cell), and early false interrupts replanned worlds in which no results yet existed. Monitoring precision and recall are not independent dials; they share the run's finite attention. **v6.1: confirmed as the dominant starvation mechanism by the trajectory analysis (7 of 12 L2 cells noise-consumed; 1 replan-recompile coverage drop; 0 replanned-away; §11.11), with the b1+schema_drift/s2 specimen as its purest exhibit.**

7. **Detection-latency economics of compiled monitoring.** Where signals recur on observed surfaces, compiled tripwires detect 3× faster than a cost-matched periodic-revalidation baseline (median 3 vs 9 tool calls; bar 2×; KG4 PASS). The surviving v1 result, and the kernel v2 generalizes via probes. **v6.1: the latency claim now stands alone — the v1 *efficiency* claim is killed per KG3's resolved branch.** The pre-committed break-even fit found no crossover at any fan-out (ΔW = −$0.072: the sentinel wasted *more* than batch; P = 1.00 over 1,000 bootstraps; §11.4). Speed did not convert to savings under v1's interrupt machinery, and the shadow replay's measured probe overhead (up to 2,322 probe calls against 107 run calls at the pre-committed cadence) establishes that v2's economics must be re-earned under event-gated cadence with probe cost booked as waste — a frozen Phase 1b gate, not an assumption.

8. **A pre-registration apparatus for agent-systems research, exercised through a kill verdict.** Frozen gates with pre-committed failure branches, custody pins, manipulation checks, a numbered deviation log, a-priori interpretation rulings, cross-vendor blind rating, and a mandated attribution audit — held intact while returning a negative verdict on the authors' own architecture. The methodology is reported as an artifact in its own right. **v6.1 extension:** the apparatus now additionally includes binding external red-team adjudication (every [FATAL]/[MAJOR] finding empirically tested from traces or routed to a written disposition), pre-commitments committed before results were readable, a dev-run ledger and data embargo, and an instrumentation-integrity replay — all exercised, §11.11.

**New finding earned by the adjudication battery (9):**

9. **Naive anomaly-gated escalation is a strong baseline, and the field should know it.** S2 — workers escalate anomalies directly to a self-adjudicating orchestrator, no compiler, no judge — detected 15/27 (56%) at a false-interrupt rate of 0.0, beating or tying the full v1 architecture in *every* failure category. Sophistication actively hurt at this task scale. This result is reported prominently rather than buried, sets the honest competitive floor for v2 (S2 is a mandatory head-to-head arm in Phase 1b), and stands as an independent contribution: published baselines for interrupt-driven monitoring should include the naive policy, which is nearly free and surprisingly hard to beat.

---

## 11. Evaluation: TripwireBench and the Pre-Registered Pilot

### 11.1 Construction (full study, unchanged in design)

TripwireBench wraps established suites in an orchestrator-worker harness with an environment proxy that mutates the world at controlled tool-call counts: GAIA (tool-use), tau-bench (retail/airline tool-agent-user), SWE-bench Verified subset (repository tasks); target ~150–200 tasks. Conditions per task: no-injection control plus one injection per applicable category at early/mid/late points. Harness: conductor pattern over a pinned production agent CLI (validated in the pilot), LangGraph as second framework for generality.

**v6 qualification rule (from Phase 1):** every injection must (a) demonstrably wound the batch baseline (manipulation check, as in the pilot's 9/9) **and** (b) admit an oracle recovery, **or** be explicitly labeled a *retreat-condition cell* measuring abort quality and salvage rather than recovery. Phase 1 discovered that several qualified injections were unwinnable by construction (e.g., hard token expiry with issuance suspended); these cells are scientifically valuable — they measure who notices the world is dead and stops paying for it — but must be labeled ex ante so success-differential metrics retain statistical power.

### 11.2 Baselines

1. **S1 Batch** — dispatch, wait, aggregate. 2. **S2 Naive interrupt** — workers escalate anomalies directly; orchestrator self-adjudicates. 3. **S3 Periodic revalidation (heartbeat)** — orchestrator re-checks every k steps, k cost-matched to the sentinel's measured compile-plus-judge overhead (conservative in the baseline's favor). 4. **S4 Self-monitoring workers** — full plan context in every worker. 5. **S5 Sentinel Protocol** plus ablations: no-judge (two-tier), no-ontology, no-KB, judge-model-size, held-out-ontology (answers the circularity objection).

**v6 baseline finding (H5), closed in v6.1.** Phase 1 found S2 *intrinsically low-noise*: 40 interrupts across its arm, exactly 1 on a clean cell, 4 false in total — workers given no filter escalate rarely and largely accurately at this task scale. The folk premise "naive escalation = interrupt spam," which KG2's ratio-form gate encoded, was empirically false here. **The battery closed the open item: S2's strict recall is 15/27 (56%), at FIR 0.0, beating or tying S5 in every category — the naive baseline outperformed the v1 architecture on detection (Finding 9, §10).** Consequences: (i) S2 is a **mandatory head-to-head comparison arm in Phase 1b** — v2 must be reported against the naive policy, not only against batch and heartbeat; (ii) Phase 1b noise gates use absolute caps rather than ratios to a baseline that may itself be quiet; (iii) "anomaly-gated escalation is cheaper and better than expected" is reported as a finding, not buried.

### 11.3 Metrics

Wasted work (post-invalidation tool calls + tokens not contributing to the final successful plan); time-to-detect (steps from injection to first validated detection); detection recall/precision; false-interrupt rate; success rate; replan quality; total cost. **v6 additions:** salvage score (fraction of required outputs delivered, visible partial recovery), abort quality (for retreat-condition cells), and probe overhead as a separately accounted line. Statistical protocol for the full study: ≥5 seeds, means with 95% CIs, paired bootstrap over tasks; the pilot ran n=3 by design and its gates were therefore written on medians.

### 11.4 Break-Even Analysis

Sentinel Protocol is cost-positive when `C + J + p·R < p·(W_batch − W_sent)`, with compile cost C, judging cost J, replan overhead R, invalidation probability p, and waste terms scaling with fan-out n and horizon h (W ~ n·h·burn_rate). The model predicts payoff in high-fan-out, long-horizon, volatile, expensive-worker regimes — and predicts failure for short single-worker tasks in stable environments. **Phase 1 status: the pilot landed in the predicted below-crossover regime and KG3 failed accordingly (clean overhead OVER the 12% cap; the model's own forecast).** **v6.1 — the pre-committed fit is complete and the branch is resolved: the v1 efficiency claim is killed.** With the model form committed before fitting, parameters estimated from the 195-cell corpus yield **no crossover at any fan-out**: the waste differential itself is negative (ΔW = −$0.072 — v1's interrupt machinery wasted *more* than batch, leaving nothing for overhead to amortize against), with P = 1.00 across 1,000 bootstrap resamples. This is the model's harshest possible verdict and it is reported as such. Two consequences: (i) v2's economics start from zero — no element of v1's cost story carries forward; (ii) the binding constraint shifts from detection to economics, because the shadow replay measured probe overhead at up to 2,322 probe calls against 107 worker calls under the pre-committed naive cadence (§11.11) — v2 therefore adopts event-gated cadence with probe cost booked in the waste column, and Phase 1b's economics gate is written against that accounting. v2 additionally operationalizes the inequality at runtime: the abort policy consults it before authorizing recovery rounds (Section 11.9).

### 11.5 Threats to Validity

Carried from v5 (construct: injected vs natural invalidation distributions; internal: LLM stochasticity; external: framework generality; conclusion: benchmark-builder bias — mitigated by pre-existing suites and a released artifact), with three v6 additions stated plainly:

- **Benchmark information leak into v2.** Architecture v2 was designed from Phase 1's traces on these nine injections. Mitigations: Phase 1b re-draws injection fire-counters and varies payload parameters; the full study's held-out-ontology arm and natural-failure study remain the principal anti-overfit instruments; the leak is acknowledged in the paper rather than laundered.
- **Pilot scale.** 8–26-call tasks at $0.10–0.40 sit below the break-even crossover by the model's own arithmetic; pilot economics generalize only through the fitted model, not directly.
- **Gate-form pathology.** Ratio-form gates against an unexpectedly quiet baseline (KG2 vs S2) can be structurally unpassable; Phase 1b gates use absolute caps where the comparison quantity is itself under test (H5).
- **Projection optimism (new in v6.1).** The shadow replay's 78% projected recall is an *upper bound* computed under stated assumptions (A1–A4 in archaeology_v2.md), with mechanically constructed probes the LLM compiler has not yet been asked to produce, on the same nine injections v2 was designed from. It validates a mechanism's feasibility, not a system's performance, and is quoted nowhere in this document as a prediction. Phase 1b's gates — frozen thresholds, held-out injection categories authored and seed-escrowed by a non-implementer, compiler-generated probes — exist precisely to convert this ceiling into a measurement.

### 11.6 Phase 1 Results: Verdict (June 11, 2026 — final)

The pre-registered pilot per the companion protocol ran June 10–11, 2026. Operational record: **195/195 manifest cells banked**; 220 queue jobs total (209 done; 11 failed = 9 night-0 checker-crashes + 2 void runs, every one with a banked replacement cell); zero throttle backoffs across the entire continuous matrix; zero malformed trace lines; queue spend $120.05; cumulative project live spend ≈ **$131 of the $300 envelope**. The gates module computed once, on the complete manifest, immediately after close. Verbatim:

```
=== KILL GATES (computed once, on the complete planned matrix) ===
KG1 recall: 35% (>=60%) | categories >=50%: 1/5 (>=4) -> FAIL
KG2 FIR: S5=1.0 S2=0.0 S4=1.0 (S5<=0.5*S2 and S5<=0.7*S4) -> FAIL
KG3 cost: S5 med $1.178952 vs S1 med $0.340831; success S5=4% S1=22%; clean overhead OVER (<=12%) -> FAIL
KG4 vs heartbeat: wasted med S5=15014.0 S3=7950 (>=20% better) | TTD med S5=3 S3=9 (>=2x) -> PASS
```

**Pre-committed branches, executed as frozen (prereg §6.2):**

- **KG1 at 35% falls in the "< 40%: kill" branch.** The v1 detection claim is killed; the flagship plan as originally conceived (full study claiming the v1 architecture) is dropped.
- **KG2 FAIL:** "Judge adds nothing: reframe as compile-only architecture (two tiers), revise paper claims, continue."
- **KG3 FAIL:** fit the break-even model; if no plausible crossover at fan-out ≤ 8, kill the efficiency claim. (Fit owed to the decision memo.)
- **KG4 PASS via the TTD arm:** S5 detects 3× faster than the cost-matched heartbeat (median 3 vs 9 tool calls) — **the surviving claim**. The wasted-work arm did not pass (S5 median 15,014 vs S3 7,950 tokens): detection speed did not convert to savings under v1's interrupt machinery.

**Mandated attribution audit (prereg §6.1), completed before any number was cited:** 20% sample (seed 11; 13 of 64 pause-bearing injected cells) → **13/13 manual agreement, zero disagreements**; the one subtle case (d1/S2/gate_skip_trap/s3, two pauses) correctly attributed. S2's FIR = 0.0 is instrument-confirmed, not a deviation: dismissed interrupts are in the denominator; S2 simply produced almost no noise (H5, §11.2). One denominator footnote: one cell's injection never fired (L0) and was excluded by the gate's recall denominator — 9/26 = 35% as printed; per-cell 9/27 = 33%; identical verdict either way.

**Interpretation discipline.** Strict-reading rulings (detection = judge-confirmed orchestrator-level pause; FIR at 0/0 defined as 0; KG3 read as written, compile included, no amortization) were logged a priori, before the gates computed, under the fraction-rule precedent. The dual-reported generous count appears in §11.7. The 48-hour decision window opened with the table; the decision memo executes the branches above.

*(Build-phase record retained from v5: KG0 PASS on both clauses — 89% empirical would-catch vs 80% bar; 79% rubric full-marks vs 70% bar, two cross-vendor raters at 95.1% agreement, author adjudication under the stated two-clause principle — plus the six build findings: the five-instance schema-transmission family; information-bounded compilation; proven-not-assumed isolation; empirically derived hierarchical gating; the four-link interrupt chain; validated measurement infrastructure including the gates module's live refusal to compute on an incomplete matrix. See v5 §11.6 for full text.)*

### 11.7 Phase 1 Failure Archaeology (exploratory; verdict untouched)

Post-verdict trace analysis per the standing boundary: everything below is labeled EXPLORATORY, feeds diagnosis and v2 design only, and recomputes no gate quantity. Every claim carries a run-dir pointer in `analysis/archaeology_v1.md` (commit 8d5a864); six hypotheses (H1–H6) are recorded there with trace evidence.

**Chain of death (centerpiece).** Each of S5's 27 injected cells was classified as DETECTED (strict) or assigned a link of death along the detection chain *compile → fire → escalate → judge → route/pause → attribute*:

| Outcome | Count | Reading |
|---|---|---|
| DETECTED (strict) | 9 | concentrated where signals recur (see per-category) |
| L0 — injection never fired | 1 | excluded from gate denominator; instrument footnote |
| L1 — no covering tripwire compiled | 1 | the only true coverage miss; ontology prior largely intact |
| L2 — compiled, never fired live | **12** | **the dominant class — see decomposition below** |
| L4 — escalated, judge ruled NOISE | 2 | judge false-negatives: rare |
| Routing/remainder | balance | per the full 27-row table in archaeology_v1.md; the strict-vs-soft delta (2 cells) bounds the routing-class loss |

**L2 decomposition — starvation, not blindness** *(v6.1: two claims in this paragraph are corrected by the adjudication battery; the original text is preserved with its errata for audit continuity — see §11.11)*. Probing the twelve L2 cells: most are *surface starvation* — the tripwire was armed and correct, and the injected surface was simply never observed again. Three mechanisms: (i) **noise storms** consumed the run's lifetime before any worker revisited the injected surface (172 non-surface fires in one cell); (ii) **upstream pipeline collapse** — the run died before reaching the injected surface; (iii) **single-visit access** — the surface's only visit predated the injection's fire counter. *(ERRATUM 1, v6.1: mechanism (iii) is withdrawn — the same-seed trajectory analysis found TRUE-SINGLE-VISIT 0/12; baselines re-observed every starved surface. The starvation reapportions to 7 noise-consumed deaths, 1 replan-recompile coverage drop, and upstream collapse; §11.11 Task B.)* Exactly **one** probed L2 is a true matcher defect: a1+token_expiry/s1, seven observed 401s under an armed covering tripwire with zero fires — a D5/D8-family (dialect/transport) suspect, flagged for v2 as an instrument-class fix. *(ERRATUM 2, v6.1: "exactly one" was wrong — the raw-event replay found a dead-pattern **class**: 84 armed url_patterns that could never fire under the live dialect, 61 host-qualified, 19 of them covering tripwires, across 8 cells. GPT-5.5 Pro's [FATAL] attack on this sentence HOLDS; the fix expands from a singleton repair to a class repair with a compile-time pattern-liveness regression sweep; §11.11 Task A. The verdict is unaffected — these are misses either way — but the diagnosis's instrument-vs-architecture apportionment shifts toward instrument.)*

**Strict vs. soft recall (pre-committed dual report).** Generous reading (WARNING annotations and non-pausing escalations counted): 11/27 vs strict 9/27. The generous reading recovers two cells. **The recall failure is real sensor silence, not attribution strictness** — the consolation hypothesis that the strict ruling was the main loss is dead.

**False-interrupt anatomy.** All 34 S5 orchestrator-level interrupts were judge-GENUINE — the judge approved everything that reached it. 18 of 34 were unattributable (noise); 14 of those 18 rode field-absence/shape evidence. **Judge credulity on field-class evidence is the FIR engine.** D11 cooldowns engaged and worked as designed, but novel-evidence noise (each anomaly hashing fresh) kept arriving past deduplication — the high-entropy-evidence mechanism from build Finding 4, at matrix scale.

**Self-injury ledger.** S5 clean-cell success 3/12 vs S1's 9/12. Of S5's nine clean failures, **seven were sentinel-induced**: five escalation-cap grinds and two replan-churn deaths in which D15 result-carryover was empty at interrupt time — the carryover mechanism worked; the false interrupt arrived before any results existed to carry. Two failures were base-rate agent noise. An uncalibrated monitor did not merely fail to help; it actively injured healthy runs.

**Per-category strict recall.** PERMISSION_AUTH **5/6** — the passing category, exactly where the D19 redesign made the signal loud, sustained, and status-coded (every post-expiry call re-observes the violation). RETRIEVAL_INTEGRITY **0/3** and TOOL_CONTRACT **1/6** — content-shaped signals that status/path predicates rarely express and single-visit access never re-observes. API_SURFACE and SCHEMA_DRIFT landed below the 50% clause (exact figures in archaeology_v1.md).

### 11.8 Diagnosis: Two Boundedness Findings and a Coupling *(v6.1: "findings," per the rater adjudication — empirical regularities with antecedents in partial observability and monitorability, not theorems)*

**Finding 1 — compilation is information-bounded** (KG0, build Finding 2). A compiler cannot monitor a surface it was never told exists; mechanically supplying the environment surface lifted would-catch from 67% to 89%. Environment surfaces are first-class compiler inputs. *(v6.1: the battery showed probes inherit this bound — under the strict pattern dialect 2/26 injected surfaces were PROBE-UNCOVERED; the dead-pattern class fix closes both to 0/26; §11.11.)*

**Finding 2 — detection is observation-bounded** (Phase 1; **refined by the battery**). A compiled monitor cannot detect a violation on a surface nobody observes after the violation. v6 attributed the missing observations to the world's geometry (single-visit surfaces); the same-seed trajectory analysis corrected this: **baselines re-observed every starved surface (12/12) — the observation bound in the pilot was self-inflicted.** The sentinel's own noise economy consumed the lifetime in which re-observation would have occurred. KG1's kill and KG4's TTD pass remain the same finding from opposite sides — compiled tripwires detect fast *where the signal recurs* — but the refined statement is sharper and harder: the architecture did not merely fail to solve the observation problem; it *manufactured* it.

**The coupling (H1) — precision and recall share the run's lifetime.** False positives are not merely a cost line: noise storms consumed runs before true signals arrived, and early false interrupts triggered replans of worlds in which no results yet existed. In budget-bounded execution, every false fire spends attention, turns, and lifetime that detection itself needed. The v1 system was a *coupled failure*: judge credulity (cold priors, Section 6) generated noise; noise starved observation; starvation killed recall; grinds and churn killed clean runs and the wasted-work arm of KG4. One mechanism, four gate symptoms.

**Recovery taxonomy (the five R's), recorded for v2's replan hints.** The pilot's five injections induce five distinct recovery semantics: **Remap** (404: the address died, not the data — rediscover the route), **Reinterpret** (schema drift: apply a deterministic transform anchored on a sanity reference), **Redo** (gate skip: run the skipped step yourself), **Reconcile** (doc contradiction: adjudicate or surface the conflict explicitly), **Retreat** (hard token expiry: nothing recoverable — salvage partials, report gaps, stop paying). Four R's presuppose environmental redundancy; the fifth is the abort case. The two-clause severity principle was secretly a recovery-class selector: recoverable-by-remap ↔ WARNING; nothing-recoverable ↔ CRITICAL/RETREAT.

**What this adjudicates.** The "pure engineering failure" hypothesis is half-confirmed: the compiler, ontology, and matcher are largely vindicated (one L1, one matcher bug), and the judge's failure is a calibration failure with a designed fix (Section 6, now fed). But two v1 *design* decisions are indicted as architecture: passive monitoring (no active observation) and an uncorroborated, unpriced interrupt path (no trust priors, no abort). Both are revised in v2 — by trace evidence, not by taste.

### 11.9 Architecture v2 Specification — Each Change Cites Its Wound

Unifying thesis: **v1's monitoring cost was fixed while its value scales with work-at-risk; v2 makes cost scale too, and makes observation active.** One sentence for the core mechanism: *the heartbeat's cadence at tripwire prices.* S3 had the right temporal model (keep checking) with a ruinous cost model (LLM re-inference); S5 had the right cost model (compiled predicates) with no temporal model (wait and pray). v2 marries them.

| # | v2 change | Wound it heals (trace evidence) |
|---|---|---|
| 1 | **Compiled active probes.** Each tripwire may carry a `probe` (method, target, cadence, cost class): deterministic HEAD requests, schema fingerprints, gate-status re-reads, premise re-fetches — compiled from the same mechanical sources as the tripwire (§8.2/§8.4), scheduled and executed by the matcher layer, no LLM inference on the probe path. Probe overhead is separately metered. | L2 starvation, 12/18 misses; PERMISSION_AUTH 5/6 as the existence proof that recurring observation detects; the qualification premise probe that caught doc_contradiction. |
| 2 | **Evidence-class trust priors + corroboration.** Every tripwire/escalation carries an `evidence_class`; field-shape evidence starts low-trust and cannot trigger an interrupt without corroboration (a second independent signal or one confirming probe). Status-coded evidence retains fast-path routing. | FIR anatomy: 14/18 false interrupts rode field-absence/shape evidence through a credulous judge. |
| 3 | **Calibration loop executed, not described.** Per-category and per-evidence-class Beta posteriors initialized from Phase 1 outcomes (§6); thresholds therefore start informed, with CRITICAL floors. The v1→v2 delta is a reported result. | The judge ran on cold priors; Section 6 existed on paper only. |
| 4 | **Priced ABORT/RETREAT verdict.** The judge (or two-tier policy) gains an abort path: triggered by the nothing-recoverable clause, by repeated same-class fires post-replan, or when projected recovery cost exceeds remaining task value per the break-even inequality evaluated at runtime. On ABORT: salvage partials, report gaps explicitly, stop. | Five escalation-cap grinds; KG4 wasted-work arm (15,014 vs 7,950); unwinnable retreat-condition cells. |
| 5 | **Recovery-typed replan hints + checkpointed salvage.** `recovery_class` ∈ {REMAP, REINTERPRET, REDO, RECONCILE, RETREAT} compiled per tripwire; workers emit structured partial results continuously so replans inherit a salvage manifest. Interrupts may not fire a replan into an empty world without an explicit salvage check. | Two replan-churn deaths with empty D15 carryover; replan-into-wounded-world weakness (detection ≠ recovery). |
| 6 | **Two-tier vs rebuilt-judge, settled empirically.** Per KG2's branch, the no-judge (two-tier) configuration is a first-class Phase 1b arm beside the rebuilt judge; whichever wins on the frozen gates is the architecture the full study carries. | KG2 FAIL; judge approved 34/34. |
| 7 | **Matcher defect fix (instrument-class).** The a1+token_expiry/s1 dialect/transport bug (seven observed 401s, zero fires) is repaired, regression-tested against its trace, and deviation-logged. | The single true matcher miss. |
| 8 | **Tiered compilation by work-at-risk.** Plan-time estimate of fan-out × horizon × burn rate selects monitoring depth: small plans get a minimal tripwire set and no judge below CRITICAL; large plans get the full apparatus. | KG3: fixed compile/judge overhead drowning toy-scale runs, as the break-even model predicted. |

Harness graduations (permanent, all systems): strict reply schemas both directions, void-run invariant, launcher probe, version pin, canary isolation.

**v6.1 amendments to the eight changes (post-battery; each amendment cites its adjudication):**

- **#1 amended — probes move to a perturbation-isolated side channel with event-gated cadence.** The replay measured three concrete perturbation vectors through which probes would alter the world they measure: the injection-clock counter (probe calls advance the counter that schedules injections), the deterministic token stream, and the validated_docs sentinel (G7, HOLDS). Probes therefore execute on a side channel touching none of the three, with non-perturbation a **hard Phase 1b gate**. The pre-committed naive cadence is withdrawn on economics (up to 2,322 probe calls vs 107 worker calls, G15) and on coverage (zero sweeps reached b1-length runs before death — three of the six residual projected misses are cadence starvations): v2 adopts event-gated, work-at-risk-weighted cadence with a guaranteed pre-completion sweep, and probe overhead is booked in the **waste** column, not a separate line.
- **#2 rewritten — corroboration is probe-primary; the second-signal clause is deleted.** The drafted clause ("a second independent same-window signal or one confirming probe") is broken as written: noise storms self-corroborate — 6 of 18 false interrupts passed it, two on a clean cell (G11, HOLDS). Probe-primary corroboration blocks 18/18 false interrupts at identical projected recall. The status-coded fast path is retained, now validated in-corpus: zero false interrupts carried status ≥ 400 (G10, attack REFUTED).
- **#6 resolved — two-tier is the designated primary architecture; no post-selection.** Committed as pre-commitment P3 *before* the battery's results were readable, and independently confirmed by the judge's corpus record: 34/34 approvals, two genuine signals ruled NOISE, one hallucinated misreading approved at 0.98 (G16 — "two-tier loses the judge's semantic fallback" REFUTED in-corpus: there was no semantic fallback to lose). The rebuilt judge runs as the exploratory arm only.
- **#7 expanded — from singleton fix to dead-pattern-class fix.** GPT's [FATAL] held (G2): 84 dead armed url_patterns across 8 cells, 19 covering. The repair is instrument-class as before, but now includes a compile-time **pattern-liveness regression sweep** (every compiled pattern must demonstrably match its own surface's canonical traffic before arming), which simultaneously closes probe-derivation coverage (PROBE-UNCOVERED 2/26 → 0/26, G8).
- **#8 descoped from Phase 1b.** Tiered compilation by work-at-risk drew convergent [FATAL]s (the estimator can withhold monitoring exactly where single-visit catastrophes live) and is deferred to the full study as an explicitly exploratory arm; Phase 1b runs the full apparatus on every cell.

### 11.10 Phase 1b Protocol — Honest Iteration, Pre-Registered

Phase 1b is the legitimate rerun path articulated *before* the verdict existed: report v1 as it stands, diagnose from traces, change the design with cited evidence, and re-measure under fresh pre-registration. Its integrity rules, in ink:

1. **v1's verdict appears in the paper regardless of v2's outcome.** The paper's empirical core is the two-study structure: v1 measured → calibration and redesign applied from outcomes → v2 measured. This is Section 6's designed mechanism, executed — not iterate-until-pass.
2. **Fresh gates frozen before any v2 data exists** — **v6.1: pre-commitments are in ink (repo commit 823549e, written and committed before any battery result was readable).** P1: Phase 1b inherits v1's pre-verdict thresholds verbatim for all shared quantities (strict recall ≥ 60%; ≥ 50% in ≥ 4/5 categories; kill floor 40%; TTD ≥ 2×) — no threshold derives from anything the battery reported. P2: new-gate rationales drafted and committed (values remain [freeze] placeholders for author ratification at 1b freeze): 1bKG2 noise/self-harm — **absolute** caps including median, **P95, and max-false-fires-per-cell, plus a no-escalation-cap-grind clause** (the 172-fire storm and the clean-cell grinds are the warrant), an **absolute clean-success floor** alongside parity with S1; 1bKG1 detection — recall thresholds per P1, category clauses reported with **Wilson lower bounds** at small n, **probe validity as a HARD gate** (every probe-generated interrupt audited as targeted, fresh, non-perturbing, and independent; semantic-vs-deterministic basis marked), and a **recovery-quality gate** (detect-only, detect-and-recover, detect-and-abort counted separately — abort cannot launder parity); 1bKG3 economics — probe overhead in the **waste** column, amortization ruled both ways in advance; 1bKG4 vs heartbeat — TTD ≥ 2× **and** wasted-work parity, probe costs included. An **instrumentation-integrity replay gate** is standing: raw-trace-to-label replay (the battery's Task A is its prototype) runs on 1b's matrix before gates compute. P3: **the two-tier configuration is the designated primary arm; the rebuilt judge is exploratory; no post-selection.**
3. **Anti-overfit measures:** injection fire-counters re-drawn from fresh seeds; payload parameters varied; v2 designers do not see the drawn values before freeze; retreat-condition cells labeled ex ante; **and (v6.1, adopting the convergent red-team tightening as binding) Phase 1b includes two held-out injection categories absent from Phase 1 — RESOURCE_BUDGET and DEPENDENCY_VERSION — authored and qualification-checked under the manipulation rule, with seeds escrowed by a non-implementer (advisor or co-founder), so that part of 1b's recall denominator is structurally unseen by the v2 design.** The full study retains the held-out-ontology and natural-failure arms as the principal generalization tests. A **data embargo** is defined: no benchmark-world output is observed before gate freeze; every execution involving any v2 component is logged in the standing dev-run ledger (started June 12, in repo).
4. **Cross-vendor red-team — executed, and binding (v6.1).** The diagnosis and v2 specification went to GPT-5.5 Pro and Gemini 3.1 Pro for blind adversarial review per the KG0 pattern. Under the pre-committed adjudication principle (severity by trace evidence and rebuttal-resistance, never by rater or direction), every trace-testable [FATAL]/[MAJOR] claim was empirically adjudicated by the archaeology-v2 battery (§11.11: 18 claims — refuted, partial, and holding dispositions all represented); every design-level claim is routed to a written disposition (pre-registration clause or explicit waiver) in the decision log. Opinions were sought on artifacts, never on verdicts.
5. **Instrument-vs-system boundary continues:** the matcher bug (#7) is instrument-class and fixed with regression evidence; all other changes are system-under-test changes and exist only in v2, measured only by 1b gates. The numbered deviation log continues uninterrupted.
6. **Standing priority order unchanged:** the product launch (July 15) outranks the matrix; the queue pauses losslessly on demand.

Open items at v6 freeze, now closed (v6.1): the KG3 break-even fit (**done — no crossover; efficiency claim killed; §11.4**); S2's strict recall (**done — 15/27 at FIR 0.0; §11.2, Finding 9**). Remaining for the decision memo: 1b threshold *value* ratification (structure and rationales committed per P1/P2); incorporation of hypotheses H2–H4 and H6 verbatim from archaeology_v1.md.

### 11.11 Archaeology v2 — External Adjudication and the Pre-Build Battery (June 12, 2026; exploratory)

The two external red-team reviews proposed rival causal stories for the Phase 1 failure and attacked the v2 design. Rather than accepting or rebutting them rhetorically, every trace-testable claim was adjudicated empirically by a pre-build battery executed by a fresh agent instance against the banked corpus — under the standing boundary (exploratory; verdict untouched; instrument-vs-system; report-never-repair), at **$0 LLM spend** (pure deterministic replay), with **pre-commitments P1–P3 and the operationalized corroboration policy, probe definitions, and break-even model form all committed before any result was readable** (commit 823549e; battery results at 508772f; one candidate deviation D22, lossy request-body decode, report-only). Full tables with run-dir pointers: `analysis/archaeology_v2.md`.

**Foundations.** All 27 injected-cell worlds replay byte-identically from their configs (the precondition for everything below). The dev-run ledger opened with the battery and stands for the project's remainder.

**Rival-story adjudication (Tasks A–D).**

| Rival story (rater) | Verdict | Discriminating evidence |
|---|---|---|
| **A.** "Starvation" is telemetry/normalization loss — evidence reached the raw stream but died before the matcher (both raters; Gemini's context-erasure variant) | **REFUTED** | Raw-event replay through the armed matcher: 9/12 L2 cells had **zero** raw post-injection observations of the injected surface — the evidence never existed to lose |
| **B.** False interrupts replanned the injected surface out of the live plan (GPT) | **PARTIAL** | REPLANNED-AWAY 0/12 — the specific mechanism is refuted; but 7/12 were **noise-consumed deaths** and 1 was a **replan-recompile coverage drop**, and on identical seeds **baselines re-visited the surface 12/12** — confirming the coupling (H1) as the dominant mechanism and refining Finding 2: the observation bound was self-inflicted |
| **C.** The bottleneck is content semantics — predicates cannot express the violation; re-observation returns ambiguous blobs ("L1.5") (both raters) | **PARTIAL** | L1.5 = 2 cells; the ambiguous bin is **empty**; all 8 RETRIEVAL_INTEGRITY/TOOL_CONTRACT payloads are **deterministically decidable** by content fingerprint, anchored value, or field re-read — no LLM required in-benchmark |
| **D.** Runs died before the injected surface was reachable — base-agent/horizon failure, not monitor failure (GPT) | **REFUTED** | Died-before-oracle 0/17 |

**The dead-pattern class (Task A; erratum to §11.7).** GPT's [FATAL] on the "one matcher defect" sentence **holds**: the 401 singleton generalizes to a class — 84 armed url_patterns that could never fire under the live dialect (61 host-qualified), 19 of them covering tripwires, across 8 cells. Instrument-class; repaired in v2 by the #7 class fix with a compile-time pattern-liveness regression sweep. The verdict is unaffected; the engineering-vs-architecture apportionment in §11.8 shifts toward instrument.

**The zero-LLM shadow replay (Task E; centerpiece).** Deterministic probes were mechanically constructed for all nine pilot injections (status probes; schema fingerprints; anchored-content fingerprints; gate-field re-reads) from each armed tripwire's target surface plus same-seed clean-world baselines — an **upper-bound feasibility test of the mechanism, explicitly not a test of LLM compilability** — and executed against re-instantiated mutated worlds with interrupts disabled. The pre-committed corroboration policy was then replayed offline over Phase 1's actual 34-interrupt stream plus the probe outputs:

| Quantity | Full policy (fast ∨ 2nd-signal ∨ probe) | Probe-primary (fast ∨ probe) |
|---|---|---|
| Of 18 false interrupts, blocked | 12 | **18** |
| Of 16 true (attributable) interrupts, suppressed | 10 | 15 |
| Projected strict recall | 21/27 (78%) | **21/27 (78%)** |
| Gate-denominator equivalent | 21/26 (81%) | 21/26 (81%) |

Readings, in order of consequence. (i) **The drafted second-signal clause is broken**: 6 false interrupts self-corroborate under it, two on a clean cell — noise storms vouch for themselves (G11). It is deleted; **probe-primary is adopted** (§11.9 amendment #2). (ii) **Detection migrates channels**: probe-primary suppresses 15/16 true interrupts and recall *rises* anyway, because probes recover what interrupts lose — RETRIEVAL_INTEGRITY 0/3 → 3/3 projected; per-category projection API 6/6, AUTH 6/6, RI 3/3, TC 4/6, SD 2/6. The raters' coupled-knobs [FATAL] was mechanically right and consequentially wrong; Gemini's "100% false negatives for omissions" is refuted (gate-field re-reads carry TOOL_CONTRACT to 4/6). (iii) **Residual projected misses** (6): two status-only probe bases, three cadence starvations on b1-length runs, one L0 — driving the #1 cadence amendment. One v1 detection is lost under the policy (b1+schema_drift/s3). (iv) **Perturbation is real and measured** (G7): probes as drafted would touch the injection-clock counter, the deterministic token stream, and the validated_docs sentinel — hence the side-channel requirement and the hard non-perturbation gate. (v) **Probe overhead is measured** (G15): up to 2,322 probe calls against 107 worker calls at the pre-committed cadence — economically untenable, driving event-gated cadence with probe cost as waste. (vi) **The status-coded fast path is validated** (G10): zero false interrupts in-corpus carried status ≥ 400. **All projections are upper bounds under assumptions A1–A4, computed on the nine leaked injections; none is a gate quantity or a prediction (§11.5, projection optimism).**

**The judge's post-mortem (G16).** Corpus record: 34/34 escalations approved; the only two genuine signals it ever down-ruled were ruled NOISE (the L4 cells); and in b1+schema_drift/s2 it approved a hallucinated misreading of a file listing at 0.98 confidence — whereupon the resulting replan-recompile dropped all surface coverage **twelve seconds before the injection fired**. That cell is the coupling's purest specimen and the paper's opening exhibit: the architecture confidently destroyed its own sensor coverage moments before the event it existed to detect. The judge supplied negative semantic value; its retirement (P3, two-tier primary) costs nothing the corpus can find.

**Adjudication summary.** Eighteen trace-testable [FATAL]/[MAJOR] claims were dispositioned (HOLDS / PARTIAL / REFUTED, each with a trace pointer): both raters scored roughly half holds and half refutations — the empirical justification for adjudicating external review rather than deferring to it or dismissing it. Design-level claims (probe staleness, calibration leakage, abort economics, five-R coarseness, novelty narrowing, protocol tightenings) are routed to written dispositions; several are already executed by P1–P3, the ledger, the embargo, and the held-out categories. Two v1 narrative errata are recorded in §11.7. **What the battery does not establish:** LLM compilability of probes, performance on held-out categories, live (non-replay) behavior under probe-primary, and long-horizon cadence economics — all of which is precisely Phase 1b's jurisdiction.

---

## 12. Open Research Questions

1. **Tripwire completeness.** What fraction of plan-invalidating events can a sentinel anticipate from a plan specification? Coverage bounds as a function of plan complexity and ontology size?
2. **Probe scheduling economics (new; sharpened in v6.1).** Optimal probe cadence as a function of work-at-risk, surface volatility, and probe cost class — the observation-side twin of the break-even model, now with a measured floor: the naive cadence cost 20× the worker's own traffic (§11.11). When does active observation itself stop paying — and what does a perturbation-isolated probe side channel cost in real deployments, where the analogue of the injection clock is rate limits, caches, and audit logs?
3. **Adaptive sentinels.** Incremental recompilation as early results reveal new assumptions, without blocking execution.
4. **Hierarchical scoping.** Scope lattices for deeply nested plans.
5. **Adversarial robustness.** Can a malicious tool response suppress a genuine interrupt or trigger a false one? Phase 1 demonstrated that *accidental* noise starves recall; the battery added a sharper exhibit: correlated noise **defeats second-signal corroboration by self-corroborating** (§11.11) — a result any adversary could manufacture deliberately (denial-of-detection). The probe channel narrows this surface but adds a new one (probe-response spoofing). Natural follow-up with the security community.
6. **Cross-context transfer.** Do tripwires and outcome posteriors learned in one deployment improve monitoring in another?
7. **Formal semantics for the DSL.** Coverage proofs reconnecting the practical DSL (now with probes) to runtime-verification guarantees [4, 5, 6].

---

## 13. Venue Strategy and Timeline (June 12, 2026 Reality)

| Venue | Deadline | Assessment |
|---|---|---|
| FSE 2027 Research (Shenzhen) | Oct 2, 2026 | **Primary target, conditional on Phase 1b gates.** ~16 weeks. The paper is now two-study + economics: v1 verdict, diagnosis and laws, v2 re-measurement, break-even crossover. |
| ICSE 2027 NIER (Dublin) | Oct 23, 2026 | Fallback if 1b fails or slips: 4-page emerging-results paper carrying the boundedness findings, the coupling finding with its specimen, the S2 result, the TTD result, and the methodology. Cannot coexist with an FSE full submission of the same work. |
| SEAMS 2027 (Dublin, co-located ICSE) | ~Oct 2026 (verify CFP) | Strong fit via MAPE-K framing; the "generated Monitor that starved" story is native SEAMS material. |
| ASE 2027 | ~Mar 2027 | Resubmission target; advisor's lab has two fresh ASE main-track acceptances (venue playbook exists). |
| ICSE 2028 | ~Jun 2027 | Long-cycle target for the expanded formal version. |

Compliance note unchanged: hand-verify every reference at submission (SE venues desk-reject fabricated references).

**Working timeline toward FSE (Oct 2, 2026), revised June 12 (v6.1) — now carrying three pre-committed schedule kill gates, so the deadline itself is falsifiable rather than aspirational:**

- **Jun 12 (done):** archaeology-v2 battery complete; **schedule gate 1 PASSED** — the shadow replay was decisive in the direction of proceed (mechanism feasible in-benchmark; §11.11).
- **Jun 12–13:** 48-hour decision memo, written with the battery in hand (verdict + branches resolved + adjudication + Phase 1b authorization + 1b threshold value ratification per P1/P2). Matrix-close checklist executes after the memo.
- **Jun 13–22:** v2 build (eight changes as amended in §11.9, each regression-anchored to its trace; #8 descoped); held-out categories (RESOURCE_BUDGET, DEPENDENCY_VERSION) authored, qualification-checked, seeds escrowed with a non-implementer; Phase 1b pre-registration frozen. Data embargo and dev-run ledger in force throughout. *(Buffer: this window precedes the Jun 23–30 product-launch sprint, which is protected.)*
- **Jun 23 – Jul 15 (launch month, minimal bandwidth):** Phase 1b matrix runs unattended (continuous, concurrency 1, pause-on-demand); zero decisions scheduled in this window by design. Queue time is machine time; launch week consumes hands, not queue.
- **~Jul 16–18:** Phase 1b gates + 48-hour decision. **Schedule gate 2: a 1b verdict in hand by ~Jul 18, or the submission retargets per the fallback chain — pre-committed now.** (Still ~3 weeks ahead of the original Aug 7 checkpoint.)
- **On 1b go — Jul 20 – Aug 31:** real-suite onboarding (GAIA first), 150+ tasks, held-out and natural-failure arms, calibration loop, fan-out arm. **Schedule gate 3: a frozen minimum count of validated onboarded tasks by Aug 31, or the full study descopes — count fixed in the decision memo.**
- **Sep 1–18:** full runs (5 seeds), ablations, v2 break-even fit and out-of-sample crossover validation, failure analysis.
- **Sep 19 – Oct 2:** writing (this document is ~70% of related work; §§11.6–11.11 seed the two-study core and the adjudication appendix), artifact packaging, internal review by Dr. Tüzün, submit.
- **On 1b fail:** the honest-negative-results + findings + benchmark + methodology paper retargets NIER (Oct 23) or SEAMS; ASE 2027 remains the net. Either way, a paper exists — the only branch with no paper is the one where the apparatus bends, and that branch is fenced off in ink.

---

## 14. References

Unchanged from v5 ([1]–[33]) with v6.1 additions [34]–[37]; re-verify all entries at submission time. **[6] is now identified by name and confronted in §9.3.1: Ferrando, A. & Cardoso, R.C., "RVPLAN: Runtime Verification of Assumptions in Automated Planning," ICAART 2022 (Vol. 2), pp. 67–77, DOI 10.5220/0010776500003116 — full text read and verified June 12, 2026.** New entries: **[34]** Ferrando & Cardoso, "RVPLAN: a general purpose framework for replanning using runtime verification," VORTEX@ISSTA 2021, pp. 22–25, DOI 10.1145/3464974.3468447. **[35]** Bozzano, Cimatti, Roveri & Tchaltsev, "A comprehensive approach to on-board autonomy verification and validation," IJCAI 2011, pp. 2398–2403. **[36]** Bensalem, Havelund & Orlandini, "Verification and validation meet planning and scheduling," STTT 16(1):1–12, 2014. **[37]** Ferrando & Cardoso, "Runtime Monitoring of Action Specifications for Replanning in Classical Planning," VORTEX 2025 (verify final publication venue/pages at submission). Additions still queued for the related-work sweep before the August build: Watson (ASE 2025, cognitive observability) alongside §9.6; ABRV/NuRV (Cimatti, Tian & Tonetta, FMSD 2022) alongside §9.3; Cohen & Peled (AISoLA 2024 / RV 2025), nl2spec (CAV 2023), NL2TL (arXiv:2305.07766) for the NL-to-monitor cluster; fresh adjacent-work sweep repeated at submission per the standing checklist. *(Standing verify-before-cite rule: "LLMon" remains unconfirmed by name and is not cited until located.)*

*(Full reference list as in v5: [1] Dunlap et al., execution monitoring survey; [2] Davis-Mendelow et al., AAAI 2013; [3] Bercher et al., ICAPS 2014; [4] Bauer/Leucker/Schallhart, ACM TOSEM; [5] Havelund/Rosu, TACAS 2002; [6] RV of assumptions in automated planning, 2022; [7] arXiv:2503.03505; [8] Scale AI, arXiv:2508.19461; [9] AgentSpec, ICSE 2026, arXiv:2503.18666; [10] Agent-C, arXiv:2512.23738; [11] Pro2Guard, arXiv:2508.00500; [12] ProbGuard, arXiv:2602.19844; [13] LlamaFirewall, arXiv:2505.03574; [14] MAST, arXiv:2503.13657; [15] AgentOps, arXiv:2411.05285; [16] wasted-computation diagnosis, arXiv ID to confirm; [17] LumiMAS, AAMAS 2026, arXiv:2508.12412; [18] DiLLS, CHI 2026, arXiv:2602.05446; [19] Graph Harness, arXiv:2604.11378; [20] SHIELDA, arXiv:2508.07935; [21] Learning to Interrupt, arXiv:2604.06452; [22] LangGraph interrupts docs; [23] Kephart/Chess, IEEE Computer 2003; [24] Weyns 2020; [25] Nascimento et al., arXiv:2307.06187; [26] ACM TAAS roadmap, doi:10.1145/3686803; [27] Anthropic Engineering, multi-agent research system; [28] Mullick et al., LexCGraph, under review; [29] Mullick et al., Fortunate Recall, NeurIPS 2026 submission; [30] Zep, arXiv:2501.13956; [31] GAIA, arXiv:2311.12983; [32] tau-bench, arXiv:2406.12045; [33] Karnofsky, Carnegie Endowment.)*

---

## Appendix A–D

Changelogs v1→v5 retained in the v5 archive (reframing for SE venues; positioning and novelty sections; MAPE-K concession-as-framing; related work rebuild; TripwireBench over established suites; break-even model; KG0 closure; build completion and matrix-readiness).

## Appendix E: Changelog from v5 (June 12, 2026)

1. **Phase 1 verdict recorded as final.** §11.6 rewritten around the complete 195-cell matrix: kill-gate table verbatim (KG1 FAIL in the kill band; KG2 FAIL; KG3 FAIL; KG4 PASS via TTD), pre-committed branches executed, mandated attribution audit reported (13/13; S2's FIR instrument-confirmed; L0 denominator footnote). Operational close-out: 220 jobs, zero throttles, zero malformed traces, ~$131 of $300 cumulative.
2. **New §11.7 (failure archaeology):** chain-of-death table (L2 starvation dominant, 12/18; one L1; two L4; one true matcher bug a1+token_expiry/s1), strict-vs-soft recall (9/27 vs 11/27 — the silence was real), false-interrupt anatomy (34/34 judge-GENUINE; 14/18 false on field-shape evidence), self-injury ledger (7 of 9 clean failures sentinel-induced: 5 grinds, 2 empty-carryover churns), per-category recall (PERMISSION_AUTH 5/6; RETRIEVAL_INTEGRITY 0/3; TOOL_CONTRACT 1/6).
3. **New §11.8 (diagnosis):** the two boundedness laws (information-bounded compilation; observation-bounded detection), the precision-recall coupling through run lifetime (H1), the five-R recovery taxonomy, and the explicit engineering-vs-architecture adjudication (compiler/matcher/ontology largely vindicated; passive monitoring and the uncorroborated interrupt path indicted as design and revised by evidence).
4. **New §11.9 (architecture v2):** eight changes, each citing its wound — compiled active probes ("heartbeat's cadence at tripwire prices"), evidence-class trust priors with corroboration, the calibration loop executed from Phase 1 posteriors, the priced ABORT/RETREAT verdict, recovery-typed hints with checkpointed salvage, the two-tier-vs-rebuilt-judge arm, the matcher fix, tiered compilation by work-at-risk. DSL grammar extended (probe, recovery_class, evidence_class, ABORT_SALVAGE).
5. **New §11.10 (Phase 1b protocol):** v1 reported in ink regardless; fresh gates frozen before v2 data with author-ratified thresholds (candidate structure listed; H5 lesson — absolute caps, plus a new anti-self-injury gate); anti-overfit measures; cross-vendor red-team of diagnosis and spec before build; open items owed to the decision memo (break-even fit, S2 strict recall, H2–H4/H6 incorporation, threshold ratification).
6. **Claims section (§10) annotated with empirical status** and extended with four claims earned by Phase 1 (boundedness laws; precision-recall coupling; detection-latency economics; the exercised pre-registration apparatus). Abstract, header, §1, §2, §5, §6, §11.2, and threats (§11.5: benchmark leak, pilot scale, gate-form pathology) updated to the split verdict. Timeline (§13) revised: Phase 1b inside June–July, FSE conditional, NIER/SEAMS carrying the negative-results paper if 1b fails — a paper exists on every branch.

## Appendix E.2: Changelog from v6 → v6.1 (June 12, 2026, post-battery)

1. **New §11.11 (archaeology v2):** the external red-team's trace-testable claims adjudicated by a pre-build battery under pre-commitments committed before results were readable ($0 LLM; commits 823549e → 508772f). Rival stories: telemetry-loss and horizon-failure REFUTED; trajectory-distortion and semantic-insufficiency PARTIAL and absorbed. Zero-LLM shadow replay: probe mechanism feasible in-benchmark (8/8 content payloads deterministically decidable; projected recall ceiling 78%, upper bound under A1–A4); second-signal corroboration clause broken and deleted; probe-primary adopted (18/18 false blocked); judge retired on its corpus record; three perturbation vectors measured; probe overhead measured (2,322 vs 107 calls). Eighteen claims dispositioned with trace pointers; rater scoreboard ~half holds, half refutations.
2. **Two errata recorded in §11.7** (audit-continuity style — original text preserved): the "single-visit access" starvation mechanism withdrawn (baselines re-visited 12/12; starvation reapportioned to noise-consumption per Task B), and "exactly one matcher defect" corrected to the dead-pattern class (84 dead armed patterns, 19 covering, 8 cells).
3. **§11.8 reframed:** "laws" → "boundedness findings" (rater adjudication accepted); Finding 2 refined — the observation bound was self-inflicted via the noise economy. §1 and the abstract updated to match.
4. **§11.9 amended post-battery:** #1 probes on a perturbation-isolated side channel with event-gated cadence and overhead-as-waste; #2 rewritten probe-primary with the second-signal clause deleted (G11) and the status fast path validated (G10); #6 resolved — two-tier primary per P3 and the judge post-mortem (G16), no post-selection; #7 expanded to the dead-pattern-class fix with a pattern-liveness regression sweep (also closing probe coverage, G8); #8 descoped from Phase 1b.
5. **§11.10 hardened to executed status:** P1–P3 in ink (thresholds inherited verbatim from v1's pre-verdict freeze; new-gate rationales committed — tail FIR caps, no-grind clause, absolute clean floor, Wilson bounds, probe-validity HARD gate, recovery-quality gate, instrumentation-integrity replay gate); held-out categories RESOURCE_BUDGET and DEPENDENCY_VERSION adopted as binding with non-implementer seed escrow; data embargo defined; dev-run ledger standing; red-team converted from advisory to binding with every finding adjudicated or dispositioned.
6. **Verdict ledger completed:** KG3's branch resolved — break-even fit found no crossover at any fan-out (ΔW = −$0.072; P = 1.00/1,000 bootstraps); the v1 efficiency claim is killed in ink (§11.4). H5 closed: S2 strict recall 15/27 at FIR 0.0, beats/ties S5 everywhere; S2 promoted to mandatory 1b comparison arm; new Finding 9 (§10) reports naive-baseline competitiveness as a contribution.
7. **§2 and §9 rebuilt around the named nearest ancestor:** RVPLAN confronted from the full ICAART 2022 text (§9.3.1) — translation-vs-synthesis, self-narrating vs unlabeled worlds, noise-free vs judged/priced interrupts; new positioning row; references [34]–[37] added (RVPLAN VORTEX'21; Bozzano 2011; Bensalem 2014; Ferrando & Cardoso 2025); verify-before-cite rule logged (LLMon uncited until located).
8. **§13 timeline now self-binding:** three schedule kill gates pre-committed (gate 1, the battery — PASSED Jun 12; gate 2, 1b verdict by ~Jul 18 or retarget; gate 3, frozen onboarding count by Aug 31 or descope). New threat added (§11.5): projection optimism — all shadow-replay numbers are upper bounds, quoted nowhere as predictions.
