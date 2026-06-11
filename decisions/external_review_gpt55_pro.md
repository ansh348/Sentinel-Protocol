# External red-team review — GPT-5.5 Pro (adjudication input of record)

Provenance: blind adversarial review of sentinel_protocol_v6.md (diagnosis §11.7–§11.8 +
v2 spec §11.9 + Phase 1b protocol §11.10), per §11.10 item 4. Received 2026-06-12 via the
author; ingested verbatim below. Attribution basis: this review contains Rival Stories B
(trajectory distortion) and D (horizon confound), which the author's task brief attributes
to GPT-5.5 Pro alone. Adjudication governed by decisions/rater_adjudication_principle.md.
Nothing in this file alters the Phase 1 verdict (decisions/kill_gates_final.md).

---

I treat §11.6's Phase 1 verdict as final. Everything below is prospective for §11.9–§11.10 and paper framing. Section pointers refer to the attached v6 document. 

## 1. Attack the causal diagnosis (§11.7–§11.8)

### Rival causal story A: the real failure is telemetry/normalization mismatch, not surface starvation

[FATAL] §11.7 classifies 12 cells as L2 "compiled, never fired live," then says most were "surface starvation"; only one was a true matcher defect. That conclusion depends on an implicit equivalence: "the worker did not observe the injected surface" = "the matcher had no valid event to fire on." That equivalence is not proven in the document. A surface can be observed in the raw trace but lost at the event-normalization layer: transformed field name, different transport dialect, cached response wrapper, tool adapter eliding status, JSON stringification, nested result field, truncated body, or post-processing into a semantic summary. The one explicit matcher defect, a1+token_expiry/s1 with seven observed 401s and zero fires, is exactly the kind of symptom that should make you suspect more hidden normalization failures, not conclude the rest are starvation. §11.7's "one matcher defect" claim is too strong without raw-event-to-normalized-event replay evidence. 

What would discriminate it: for every L2 cell, I would need the compiled tripwire AST, raw tool event stream, normalized matcher input stream, predicate evaluation log, and exact injection-fire counter. A convincing archaeology table would show, per post-injection tool call: raw observation present/absent, normalized event present/absent, predicate applicable/not applicable, predicate result, and why. Without that, §11.7 could have misclassified "observed but not normalized" as "not re-observed."

Where L2 probing could have misclassified: if the probe looked for semantic re-contact with the injected surface at the task/world level, but the matcher only saw a lossy tool-output abstraction, it could label the cell "starved" even though the worker encountered the relevant evidence. This is especially plausible for §5's content-shaped categories and §4.3's `tool_output`, `retrieval_content`, and `test_result` signals, where the matchable surface is not a clean HTTP status.

### Rival causal story B: the failure is trajectory distortion by the sentinel, not passive observation per se

[FATAL] §11.8 says false positives consumed run lifetime, which starved observation. That is plausible, but a different mechanism fits the same facts: false interrupts changed the execution trajectory so the original injected surface was no longer on the live plan. In that case, "never re-observed" is not a sensor failure; it is a replan-induced counterfactual mismatch between the original benchmark injection and the post-interrupt plan. §11.7's self-injury ledger already says two clean failures were replan-churn deaths with empty carryover, and §11.8 says early false interrupts replanned worlds with no results. That can create L2 labels even if passive monitoring would have worked under the original trajectory. 

What would discriminate it: I would need, for each L2 miss, a timeline showing first false fire, first replan, original planned surface visits, post-replan planned surface visits, and whether the injected surface remained causally relevant after replan. Then compare S5's path against S1/S2/S4 on the same seed. If S1 or S2 later visits the injected surface but S5 does not because S5 replanned away from it, §11.8's "observation-bounded" law is contaminated by intervention-induced path drift.

Where L2 probing could have misclassified: a post-hoc L2 probe may ask, "Was the original injected surface observed after fire?" But if the system had already changed the plan, that question is not the right counterfactual. The correct question is: "Given the actual post-interrupt plan, was there still a live assumption tied to that surface?" If no, the miss belongs under recovery/trajectory corruption, not surface starvation.

### Rival causal story C: the main bottleneck is content semantics, not observation

[MAJOR] §11.7 says RETRIEVAL_INTEGRITY was 0/3 and TOOL_CONTRACT was 1/6 because content-shaped signals are single-visit and status/path predicates rarely express them. §11.9 responds with active premise re-fetches and gate-status re-reads. That assumes the missing piece is re-observation. But for RETRIEVAL_INTEGRITY, the hard part is deciding whether a new document contradicts a plan premise; for TOOL_CONTRACT, the hard part may be deciding whether a required quality step actually happened, not just whether a field says `checks_run == 0`. Those are semantic classification problems. Re-observation can deliver another ambiguous content blob, not a deterministic predicate. 

What would discriminate it: I would need L2 traces split into "surface not revisited," "surface revisited but semantically ambiguous," "surface revisited but predicate too weak," and "surface revisited but judge/matcher failed." For content-shaped misses, show the exact evidence payload that an ideal active probe would have produced and whether a non-LLM deterministic predicate could have classified it.

Where L2 probing could have misclassified: if the archaeology's "armed and correct tripwire" label means the tripwire text conceptually covered the failure, but the actual predicate did not express contradiction or contract violation, then the L2 label is inflated. That is not starvation; it is L1.5: compiled natural-language intent without executable semantic discriminant.

### Rival causal story D: the recall failure is partly base-agent/horizon failure, not sentinel failure

[MAJOR] §11.7 notes upstream pipeline collapse as an L2 starvation mechanism. That is not the same causal class as "surface was single-visit." If runs die before reaching the surface because the base agent is weak, the monitor is being evaluated under an execution horizon too short to expose the invalidation. §11.5 already admits pilot tasks are tiny and below crossover; §11.3 says medians were used because of n=3. The diagnosis may be conflating "monitor cannot observe" with "agent never gets far enough to be monitorable." 

What would discriminate it: for every missed injected cell, I would need the oracle planned visit index of the injected surface, the actual baseline visit index distribution, and whether the run would have reached that point absent sentinel overhead. If many misses happen after base-task failure, then §11.8's Law 2 is too broad: detection is not merely observation-bounded; it is competence- and horizon-bounded.

Where L2 probing could have misclassified: "upstream pipeline collapse" should not be merged with "single-visit access." A v2 active probe can fix single-visit surfaces; it may not fix an agent that collapses before producing useful partials.

## 2. Attack each v2 change (§11.9), including interactions

| v2 change | Strongest failure mode | How it undermines another change |
| --- | --- | --- |
| [FATAL] **1. Compiled active probes (§11.9 #1; §8.4).** | The probe compiles the wrong thing. A HEAD request proves an endpoint exists, not that the endpoint still satisfies the plan's semantic contract. A schema fingerprint proves the shape changed, not that the current plan is invalid. A premise re-fetch proves content changed, not contradiction. A gate-status re-read proves a field value, not that the quality gate was meaningfully executed. For RETRIEVAL_INTEGRITY and TOOL_CONTRACT, the proposed probes smuggle semantic judging back into a "deterministic" path. | Undermines #2 because the "confirming probe" may not be independent corroboration; it may be the same weak field-shape signal repeated. Undermines #8 because probe overhead is exactly what tiered compilation is supposed to suppress. Undermines #4 because repeated probe anomalies can trigger ABORT loops. |
| [FATAL] **1a. Probe staleness (§11.9 #1; §8.2/§8.4).** | Probes are compiled from plan-time mechanical sources. If docs, schemas, tools, or retrieved facts move, the probe can validate a stale target while the worker uses a live different target. This gives false reassurance and can create false negatives. | Undermines #3 calibration: posteriors trained on Phase 1 surfaces will not tell you when a v2 probe is stale. Undermines #5 recovery hints: salvage may inherit a "validated" stale premise. |
| [MAJOR] **1b. Probe world perturbation (§11.9 #1).** | "Cheap deterministic" is not "non-interfering." HEAD requests, auth checks, schema fetches, repeated retrievals, and gate re-reads can mutate caches, refresh tokens, trip rate limits, update last-access timestamps, or alter ranking. The monitor can change the world it is measuring. | Undermines #4 ABORT/RETREAT because self-induced 401s, throttles, or stale-cache contradictions can look like real same-class repeated fires. Undermines #2 because probe corroboration is no longer independent if the probe created the second signal. |
| [FATAL] **1c. Probe targeting limits (§11.9 #1; §11.8 Law 1).** | Active probes do not escape information-bounded compilation. If the compiler was not told the surface exists, or the load-bearing premise is implicit, no probe will be generated. §11.8's Law 1 remains, but §11.9's language makes v2 sound as though probes convert every category into PERMISSION_AUTH. They do not. | Undermines #8: small plans with minimal monitoring are exactly where implicit assumptions and single-visit facts will be omitted. |
| [FATAL] **2. Evidence-class trust priors + corroboration (§11.9 #2).** | The cure for false positives can become a false-negative machine. TOOL_CONTRACT's strongest signal may be field-shaped: `checks_run == 0`, missing artifact, absent validation line, empty result manifest. If field-shape evidence "cannot trigger an interrupt without corroboration," then the real skipped gate is suppressed precisely because the expected second signal does not exist. | Directly undermines #1 and KG1 in §11.10: active probes were added to recover recall, but corroboration can block the recovered evidence. Also undermines #6 because the two-tier arm cannot mean the same thing if corroboration gates are judge-like. |
| [MAJOR] **2a. Status-coded fast path (§11.9 #2).** | §11.9 keeps status-coded evidence on a fast path because PERMISSION_AUTH passed. That bakes in Phase 1's category distribution. Status-coded signals can still be benign: transient 404, intentional 403, expected 401 refresh, schema endpoint disabled but payload still usable. | Undermines #4: status-coded fast-path errors can cause premature aborts. Undermines #3: Beta priors by evidence class may over-trust the one category that happened to pass in v1. |
| [FATAL] **3. Calibration loop from Phase 1 posteriors (§11.9 #3; §6).** | You are initializing v2 from the same failed trace distribution used to design v2. The posteriors are not neutral calibration; they are part of the model selection procedure. Worse, Phase 1 outcomes conflate category, evidence class, payload, worker trajectory, and v1 instrumentation. A low posterior for field-shape evidence may encode v1 judge credulity, not v2 signal validity. | Undermines §11.10 anti-overfit. Also undermines #2 because the prior can suppress rare true field-shaped signals before v2 has any chance to observe them. |
| [MAJOR] **4. Priced ABORT/RETREAT (§11.9 #4).** | ABORT can make economics look better by giving up. Without a hard separation between "valid retreat," "premature abandonment," and "failure concealed as salvage," wasted-work parity can be won by lowering task ambition. The break-even inequality depends on projected recovery cost and remaining task value—both easy to tune. | Undermines #5 because recovery-typed replans and checkpointed salvage matter only if the system does not abort early. Undermines 1bKG1 in §11.10 if abort is allowed to count as detection or if retreat labels remove hard cases from recall. |
| [MAJOR] **5. Recovery-typed hints + checkpointed salvage (§11.9 #5).** | The five-R taxonomy is too coarse. Real cells can require REMAP then REINTERPRET, or REDO plus RECONCILE. Forcing one recovery class at compile time can route the orchestrator into the wrong recovery branch. Continuous partial-result emission also creates new stale evidence: salvage manifests must themselves be validated. | Undermines #8 by adding overhead to small tasks. Undermines #4 because a bad salvage manifest can make abort look responsible. Undermines #1 because probes now need to validate both original surfaces and salvage surfaces. |
| [FATAL] **6. Two-tier vs rebuilt judge selected by gates (§11.9 #6; §11.10 item 2).** | "Whichever wins" is post-selection. It is not one architecture being tested; it is a small model-selection tournament on a distribution already shaped by Phase 1. If both arms share compiler/probes/calibration, the winning arm can exploit a specific gate profile without generalizing. | Undermines §11.10's self-binding claim. It also undermines #2: if no-judge wins, evidence-class corroboration is still a judge-like policy, just relabeled. |
| [MAJOR] **7. Matcher defect fix (§11.9 #7).** | Calling the 401 bug "instrument-class" is dangerous. The presence of one raw-observed/no-fire case proves the instrumentation can lie. Fixing the known trace with a regression test does not bound the class of dialect/transport defects. | Undermines §11.7–§11.8 causal diagnosis: if matcher defects are undercounted, v2 is repairing the wrong dominant mechanism. Also undermines #3 because Phase 1 posterior data were collected through the defective matcher. |
| [FATAL] **8. Tiered compilation by work-at-risk (§11.9 #8).** | Pre-execution work-at-risk is itself an uncertain model output. Small tasks can have catastrophic single-visit assumptions; large tasks can tolerate cheap batch fallback. If the estimator is wrong, the policy withholds monitoring where it is most needed. | Direct conflict with #1: active probes are the proposed fix for single-visit surfaces, but #8 removes them from "small" tasks—the exact pilot regime where single-visit failures appeared. It also undermines 1bKG1 if recall is measured on tasks that got the minimal tier. |

### The specific false-positive/false-negative trade you should fear

[FATAL] §11.9 #2 tries to suppress false positives by downgrading field-shape evidence, but §11.7 says TOOL_CONTRACT failed badly and §5 says TOOL_CONTRACT is content/field-shaped. A skipped quality gate often has no second independent signal; the absence is the evidence. Requiring corroboration will reduce the exact false positives that killed KG2, but it can also kill the exact true positives needed to pass KG1. This is the central v2 interaction bug: false-positive control and recall repair are not separable knobs. 

## 3. Attack the Phase 1b protocol (§11.10) as self-binding

[FATAL] **Threshold ratification is still inside author control (§11.10 item 2).** "Values to ratify, not yet frozen" is a loophole. A motivated reasoner can choose FIR caps, clean-parity margins, amortization rules, and category clauses after internal build intuition but before "v2 data" formally exists. Tightening: freeze exact thresholds, formulas, censoring rules, amortization, retreat handling, and confidence intervals before v2 implementation begins, not merely before the matrix runs. 

[FATAL] **"No v2 data exists" is undefined (§11.10 item 2).** A developer can run smoke tests, local dry runs, replay tests, synthetic fixtures, probe-target checks, compiler validation, and "instrument tests" that are functionally v2 performance data but not counted as matrix data. Tightening: define a data embargo. Allow only unit tests on synthetic non-benchmark fixtures; log every run using v2 compiler/probes/policy; publish a dev-run ledger; prohibit looking at any benchmark-world output before freeze.

[FATAL] **The anti-overfit plan is insufficient because the intervention was designed from the test (§11.5; §11.10 item 3).** Redrawing fire counters and varying payload parameters does not create a new test distribution. The architecture is explicitly designed from the nine Phase 1 injections and their traces. That is acceptable for calibration, not for a clean validation claim. Tightening: Phase 1b must include an external holdout: new injection archetypes, new surfaces, and at least one category not represented in Phase 1, authored or seed-escrowed by someone other than the v2 implementer. §11.5 already admits the benchmark leak; §11.10 does not actually close it. 

[MAJOR] **Retreat-condition labeling is a degrees-of-freedom leak (§11.10 item 3; §11.1).** "Recoverable-class cells" in 1bKG1 plus ex ante retreat labels creates an incentive to classify hard cases as retreat and move them out of recall. Tightening: independent blinded adjudication of recoverable vs retreat before any v2 run; publish oracle recovery scripts; require a separate abort-quality gate on retreat cells.

[MAJOR] **The deviation log records self-deception; it does not prevent it (§11.10 item 5).** With full codebase control, the author can move boundary changes into "instrument-class," especially around matcher fixes, schemas, launcher probes, strict reply schemas, and void-run invariants. Tightening: freeze container hashes, dependency pins, matcher code, instrumentation schema, and gate scripts; require an independent replay audit of raw traces to metric labels.

[FATAL] **Two-tier vs judge as first-class arms creates post-selection inference (§11.9 #6; §11.10 item 2).** If whichever arm wins becomes the architecture, the reported v2 result is not a simple confirmatory test. It is model selection on the test. Tightening: designate one primary arm before Phase 1b; treat the other as exploratory, or require a second locked holdout after arm selection.

[MAJOR] **Probe-covered-surface coverage is only diagnostic (§11.10 item 2).** That is backwards. Since §11.9's central repair is active probing, probe validity is a primary mechanism gate, not a diagnostic. Tightening: require a hard gate: ≥X% of load-bearing injected surfaces have a valid, non-perturbing, post-injection probe whose evidence is independently sufficient or explicitly marked semantic.

[MAJOR] **Break-even plausibility remains subjective (§11.10 item 2; §11.4).** "Crossover ≤ 8 workers plausibility test" is not a gate unless the model, estimator, priors, exclusions, and acceptance rule are frozen. Tightening: pre-register the exact regression/model form, bootstrap procedure, and what counts as plausible.

[MINOR] **Cross-vendor red-team is advisory, not binding (§11.10 item 4).** It may improve design but does not constrain choices. Tightening: require every [FATAL]/[MAJOR] red-team finding to be either converted into a pre-registration clause or explicitly waived in the prereg.

## 4. Attack the Phase 1b gates (§11.10 item 2)

### 1bKG1 detection

[FATAL] **Recall on "recoverable-class cells" can pass while the architecture is bad (§11.10 item 2).** If hard cases are labeled RETREAT or excluded, recall can improve by denominator management. Worse, a system can detect recoverable invalidations but still fail to recover, which §11.10 does not make part of the detection gate. Add: "valid detection must lead to correct recovery action or justified abort," with separate counts for detect-only, detect-and-recover, and detect-and-abort.

[MAJOR] **The category clause is unstable (§11.10 item 2).** "≥50% in ≥4 categories" is fragile at small per-category n. A single cell can swing a category. Use Wilson lower-bound or exact-binomial lower-bound gates, or report category balance as descriptive and make the primary gate per-cell with stratified minimums.

[MAJOR] **Probe-covered-surface coverage as diagnostic is too weak (§11.10 item 2).** Make it a hard gate because §11.9's active-probe claim lives or dies there.

### 1bKG2 noise/self-harm

[FATAL] **Median FIR can hide storms (§11.10 item 2).** §11.7's worst symptom was a storm: 172 non-surface fires in one cell. A median cap can pass while a tail cell destroys a run. Add P90/P95 false-fire count, max false-fire cap, time-to-first-false-interrupt on clean cells, and "no clean-cell escalation-cap grind" as hard clauses. 

[MAJOR] **Clean-run success parity with S1 can pass if S1 is weak (§11.10 item 2).** If batch baseline success is low, "within N points" tolerates bad absolute success. Add an absolute clean success floor or a paired non-inferiority gate with minimum usable-output rate.

[MAJOR] **Noise on injected cells is missing (§11.10 item 2).** False positives do not matter only on clean runs; §11.8 says they starved true detection. Add "pre-detection false-interrupt budget on injected cells."

### 1bKG3 economics

[FATAL] **A fitted crossover can pass while Phase 1b economics fail (§11.10 item 2; §11.4).** A model can project value at fan-out ≤8 while observed Phase 1b tasks remain cost-negative. The gate should require either measured value in a controlled fan-out arm or an out-of-sample validation of the fitted crossover, not just plausibility. 

[MAJOR] **Amortization is still a loaded choice (§11.10 item 2).** "Amortization explicitly ruled either way" is not enough; the rule itself determines whether v2 looks viable. Freeze two views: per-run unamortized and amortized only over a pre-specified repeated-plan workload.

### 1bKG4 heartbeat comparison

[FATAL] **TTD ≥2x plus wasted-work parity can pass while the architecture is useless (§11.10 item 2).** A system can detect fast, abort fast, waste little, and fail the user. KG4 needs to be conditional on successful recovery or justified retreat. Otherwise ABORT is a shortcut to parity.

[MAJOR] **TTD is censoring-sensitive (§11.3; §11.10 item 2).** TTD for detected cells ignores misses unless penalized. Add a survival-analysis style gate or assign undetected cells a run-end censoring penalty.

### Missing gates

[FATAL] **Missing: active-probe validity/independence gate (§11.9 #1; §11.10 item 2).** Required clause: for every probe-generated interrupt, an audit must classify the probe as targeted to the mutated surface, non-perturbing, fresh, and independent of the original trigger. For RETRIEVAL_INTEGRITY and TOOL_CONTRACT, require a semantic-validity audit, not just a field read.

[FATAL] **Missing: recovery-quality gate (§11.8 five R's; §11.9 #5).** Detection is not the product. The architecture claims interrupts for replanning. Gate on correct recovery class, successful replan, salvage correctness, and no replan into empty state.

[MAJOR] **Missing: instrumentation-integrity replay gate (§11.7; §11.9 #7).** Given the known matcher defect, require independent replay from raw traces to labels. Without it, v2 can pass on measurement artifacts.

## 5. Attack the novelty claims (§10) as a hostile FSE reviewer

| §10 claim | Nearest neighbors the document misses or understates | Does the delta survive? |
| --- | --- | --- |
| [FATAL] **1. Plan-to-monitor compilation (§10.1).** | The closest prior work is not just generic RV monitor synthesis. RVPLAN explicitly synthesizes runtime monitors from planning models to detect plan-assumption failures at runtime, including translating planning models to temporal logics. Assumption-based runtime verification handles partial observability and uses assumptions/models to reason over unobservable behavior. LLM-assisted natural-language-to-RV-monitor synthesis also exists: Cohen/Peled synthesize runtime verification monitors from natural-language specs; LLMon synthesizes RV monitors from temporal or natural-language specifications; nl2spec/NL2TL translate natural language into temporal logic specifications. | Survives only narrowly: not "compiled monitors from plans," not "LLM generates monitors," not "assumption monitoring." The surviving delta is "LLM multi-agent plan-validity monitors over API/retrieval/tool surfaces, with empirical interrupt economics." Rewrite §10.1 accordingly. |
| [MAJOR] **2. Sentinel as interrupt filter (§10.2).** | Runtime enforcement and guardrail systems are close: AgentSpec defines a DSL with triggers, predicates, and enforcement for LLM agents; Agent-C enforces temporal/state constraints over tool calls; Pro2Guard/ProbGuard-style systems do proactive runtime risk monitoring; LlamaFirewall positions itself as a real-time guardrail layer for AI agents. | Weak. "Interrupt economics for plan validity rather than safety" survives; "filter tier" does not, especially because v1 falsified it. |
| [MAJOR] **3. Failure ontology as generative prior with conjugate calibration (§10.3).** | MAPE-K Knowledge components, failure taxonomies such as MAST, and learned/probabilistic monitoring already use structured state abstractions and runtime-updated knowledge. MAST supplies a multi-agent failure taxonomy from annotated traces; Pro2Guard/ProbGuard uses symbolic state abstractions and learned transition/risk models. | Partial. The ontology-as-LLM-compiler-prompt is a practical engineering contribution. The Beta posterior story is not inherently novel unless it is shown to improve decisions out-of-sample. |
| [MAJOR] **4. TripwireBench (§10.4).** | The "benchmark over agent tasks with injected failures/security cases" neighborhood includes AgentDojo's extensible environment for tasks, defenses, and attacks; τ-bench's dynamic tool-agent-user domains; GAIA's tool-use assistant tasks; SWE-bench Verified's human-filtered software tasks. | Survives if framed as a mutation/invalidation wrapper and metric suite over existing benchmarks, not a new general agent benchmark. The novelty is the injection protocol plus wasted-work/TTD/FIR/salvage metrics. |
| [FATAL] **5. Two boundedness laws (§10.5).** | "Detection is observation-bounded" is basically monitorability/partial observability/diagnosability. Runtime verification is defined around observed executions and monitor synthesis; ABRV explicitly studies monitoring under partial observability; discrete-event diagnosability formalizes finite-time fault detection from observations. | Not as "laws." They survive as empirical restatements in LLM-agent plan monitoring. If called laws, reviewers will demand formal definitions and proofs or at least literature grounding. |
| [MAJOR] **6. Precision-recall coupling through run lifetime (§10.6).** | Monitoring overhead, observer effects, and adaptive monitoring costs are standard in self-adaptive systems. Weyns emphasizes sensors/actuators and adaptation interference; Rainbow explicitly uses runtime probes/gauges and adaptation; ReProbe addresses adaptive monitoring probes and reconfiguration cost. | Survives as an LLM-agent-specific empirical mechanism: false interrupts consume token/tool-call budget and alter trajectories. It does not survive as a general theoretical novelty. |
| [MAJOR] **7. Detection-latency economics (§10.7).** | Event-based monitors versus periodic revalidation/polling is not new in runtime monitoring or MAPE-K systems. Rainbow-style systems already monitor runtime properties and adapt on constraint violations using probes/gauges; RV is "testing forever" on observed traces with concern for low runtime overhead. | Survives as a measured economic comparison in multi-agent LLM orchestration, but only where signals recur. The v2 generalization via probes is still unproven. |
| [MINOR] **8. Pre-registration apparatus (§10.8).** | Registered reports and preregistration are established in empirical software engineering and open science; registered reports in SE were introduced at MSR 2020 and are now established across SE venues/journals; open-science guidance for SE already argues for artifact/data transparency. | Survives as a strong artifact/process contribution, not a novelty claim about agent systems. Report it, but do not oversell it as a research contribution unless the prereg apparatus itself is evaluated or reusable. |

### Specific novelty collapse: compiled active probes

[FATAL] §11.9 #1's "compiled active probes" is very close to standard self-adaptive monitoring. MAPE-K systems monitor managed systems and environments through sensors/probes; Rainbow's architecture explicitly includes probes, gauges, model managers, constraint evaluators, and adaptation engines. Active observation is not a new conceptual move. The possible delta is that probe specs are generated per LLM plan from a natural-language plan and typed ontology, but even that is narrowed by LLM-to-monitor and NL-to-temporal-logic work. 

## 6. The rejection: strongest FSE 2027 reject review

**Summary.** The paper reports an unusually transparent negative pilot, but the proposed contribution is not yet mature enough for FSE. The central empirical story—surface starvation plus judge credulity—is derived from exploratory trace archaeology whose key raw tables are not in the paper, and multiple alternative explanations remain consistent with the reported evidence. The v2 system is then designed directly from the failed test traces and re-evaluated on a lightly perturbed version of the same benchmark family, with gates that still permit denominator management, post-selection between judge/no-judge architectures, and economics-by-abort. Finally, the novelty claims are overstated relative to runtime verification, assumption-based plan monitoring, MAPE-K self-adaptive systems with probes, runtime enforcement for LLM agents, and LLM-assisted monitor/spec synthesis.

### Three weightiest objections

[FATAL] **Objection 1 — Causal underidentification (§11.7–§11.8).** The paper's v2 design rests on an exploratory diagnosis that is not uniquely supported by the reported evidence. "Compiled, never fired" is treated as surface starvation, but could be normalization/matcher failure, trajectory distortion by false replans, base-agent horizon failure, or semantic predicate insufficiency. The full archaeology table is not included, and the paper does not provide raw-event-to-matcher replay evidence. Therefore the reader cannot know whether active probes are the right repair.

[FATAL] **Objection 2 — Invalid confirmatory status of Phase 1b (§11.5; §11.10).** The authors acknowledge that v2 was designed from Phase 1 traces, but the mitigation—new fire counters and varied payloads—is insufficient. Phase 1b remains trained on the benchmark's causal structure. The protocol also allows author-ratified thresholds, post-selection between two-tier and rebuilt-judge arms, and retreat-condition labeling that can alter the recall denominator. This is not a clean confirmatory study.

[FATAL] **Objection 3 — Novelty overclaim (§2; §3.5; §9; §10; §11.9).** The system is framed as generated MAPE-K and runtime monitoring, but the paper understates prior work on runtime monitor synthesis, assumption-based plan monitoring, partial observability/monitorability, MAPE-K probes/gauges, runtime enforcement for LLM agents, and LLM-generated monitors from natural language. The surviving contribution is a specific empirical application and negative-result methodology, not the broader architectural novelty claimed.

### Fixable by October 2

[MAJOR] Fix the related-work and novelty framing in §2, §9, and §10. Replace "laws" with "empirical observations in this setting" unless formalized. Add RVPLAN, ABRV, LLM-to-RV-monitor, nl2spec/NL2TL, Rainbow/probes/gauges, Agent-C, AgentSpec, Pro2Guard/ProbGuard, and LlamaFirewall.

[MAJOR] Tighten Phase 1b preregistration in §11.10: freeze exact thresholds now; define "v2 data"; publish a dev-run ledger; predefine recoverable/retreat labels; designate one primary architecture; make probe validity and recovery quality hard gates.

[MAJOR] Add a raw-trace replay appendix for §11.7: raw event → normalized event → predicate evaluation → escalation → judge → route. Without the missing archaeology table, the diagnosis will read as motivated.

[MINOR] Reframe the paper as "negative v1 + calibrated redesign + bounded pilot evidence," not as a mature architecture.

### Structural or unlikely to fix by October 2

[FATAL] True independence of v2 from Phase 1 traces is impossible now. You can mitigate with external holdouts, but you cannot claim v2 was not shaped by the test.

[FATAL] The conceptual novelty of compiled active probes will remain weak against MAPE-K/RV unless the paper's contribution is narrowed to LLM-agent plan-validity economics.

[MAJOR] Strong generalization to real multi-agent deployments is structurally weak until the full GAIA/τ-bench/SWE-bench/natural-failure study runs and includes out-of-sample injection families.

## 7. Independent forecast

[FATAL] **(a) Probability v2 achieves strict detection recall ≥60% under Phase 1b: 0.40.** Active probes should recover some L2 misses, but content-shaped RETRIEVAL_INTEGRITY and TOOL_CONTRACT signals still require semantic discrimination, and corroboration can suppress true field-shape detections.

[MAJOR] **(b) Probability v2 achieves clean-run success parity with batch: 0.48.** Corroboration and calibration should reduce the v1 self-injury, but probes, checkpointing, salvage emission, and abort logic add new perturbation and overhead paths on small tasks.

[FATAL] **(c) Probability v2 retains TTD ≥2x vs cost-matched heartbeat while also reaching wasted-work parity: 0.30.** TTD likely survives where probes fire, but wasted-work parity requires abort/recovery decisions to be both early and correct; v1 already showed speed does not automatically become savings.

[FATAL] **(d) Probability all of the above: 0.11.** The three requirements are coupled: the changes that improve clean-run parity and FIR—corroboration, conservative thresholds, tiered monitoring—are the same changes that can cut recall and delay detection.

**Under-$30 experiment/analysis most likely to change these numbers:** run a zero-LLM shadow replay over the Phase 1 traces and deterministic mutated worlds: compile the v2 probes for the existing nine injection types, execute only the probe scheduler and corroboration policy with interrupts disabled, and audit whether each would produce fresh, targeted, non-perturbing, independent evidence. If that replay shows TOOL_CONTRACT and RETRIEVAL_INTEGRITY probes produce actually decisive evidence, my recall forecast rises sharply; if it shows repeated same-surface or semantic-ambiguous confirmations, the v2 premise is already broken before the build.

## Three highest-severity items

[FATAL] §11.7–§11.8 do not uniquely identify surface starvation; telemetry mismatch, trajectory distortion, and semantic predicate failure remain live rival causes.

[FATAL] §11.10 is not yet a clean self-binding protocol because v2 is trained on Phase 1 traces and the gates still permit threshold, denominator, arm-selection, and abort-economics loopholes.

[FATAL] §10 overclaims novelty: compiled active probes and boundedness laws collapse into known MAPE-K/RV/observability machinery unless narrowed to LLM-agent plan-validity economics.

[1]: https://arxiv.org/abs/2503.18666 "AgentSpec: Customizable Runtime Enforcement for Safe and Reliable LLM Agents"
[2]: https://arxiv.org/pdf/2503.13657 "Why Do Multi-Agent LLM Systems Fail?"
[3]: https://arxiv.org/html/2406.13352v3 "AgentDojo: A Dynamic Environment to Evaluate Prompt ..."
[4]: https://christian.schallhart.net/publications/2009--jlap--a-brief-account-of-runtime-verification.pdf "main.dvi"
[5]: https://link.springer.com/article/10.1007/s10664-022-10277-5 "Registered reports in software engineering - Springer Nature"
