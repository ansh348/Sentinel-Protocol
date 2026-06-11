# External red-team review — Gemini 3.1 Pro (adjudication input of record)

Provenance: blind adversarial review of sentinel_protocol_v6.md (diagnosis §11.7–§11.8 +
v2 spec §11.9 + Phase 1b protocol §11.10), per §11.10 item 4. Received 2026-06-12 via the
author; ingested verbatim below. Attribution basis: trailing label on the author's paste;
the brief attributes the trajectory-distortion and horizon stories to GPT-5.5 Pro alone,
and neither appears here — consistent. Adjudication governed by
decisions/rater_adjudication_principle.md. Nothing in this file alters the Phase 1 verdict
(decisions/kill_gates_final.md).

---

### 1. Attack the Causal Diagnosis (§11.7–11.8)

**[MAJOR] Rival Story 1: Subagent Context/Summarization Erasure**
The diagnosis claims 12/18 misses were "surface starvation" (L2), meaning the injected surface was never re-observed (§11.7). A highly probable rival story is that the subagent *did* interact with the surface again, but the subagent's internal context management or summarization behavior stripped the raw evidence before the matcher could evaluate it. LLM workers frequently compress verbose tool outputs. If the matcher operates on the subagent's *reported* state rather than the *raw network/tool payload*, the surface was observed by the worker but rendered invisible to the monitor.
*Trace-level evidence needed:* A byte-for-byte comparison of the raw tool/HTTP outputs against the input strings fed to the tripwire matcher. If the raw tool output contained the violation but the matcher's payload did not, the L2 classification is false; it is an architectural context-plumbing failure, not starvation.

**[MAJOR] Rival Story 2: Predicate Brittleness (Semantic Blindness)**
The diagnosis assumes that if an L2 tripwire was "armed and correct," the lack of a fire means a lack of observation (§11.7). However, API responses frequently change shape during failures (e.g., returning a `200 OK` with a JSON body `{"error": "deprecated"}` instead of a clean `404` or `410`). If the worker hit this endpoint, the passive matcher's rigid predicate (`status_in: [404, 410]`, §4.3) would silently bypass it. This is not starvation; this is semantic blindness caused by the discrete DSL's inability to interpret the world.
*Trace-level evidence needed:* A grep of all worker execution logs in the L2 cells for the target endpoint URLs or function names. If a network call or tool invocation matching the surface occurred *after* the fire counter, but the DSL failed to trigger, the DSL is indicted, not the observation model.

### 2. Attack Each v2 Change and Their Interactions (§11.9)

**[FATAL] Change 1 (Compiled active probes) vs. Content-Shaped Constraints:** You claim probes will run with "no LLM inference on the probe path." This works for HTTP HEAD requests. It fundamentally breaks for RETRIEVAL_INTEGRITY or TOOL_CONTRACT (§5), which are content-shaped. Re-reading a document to see if its semantic facts still hold cannot be done with a deterministic script; it requires an LLM. If you use LLMs for probes, your cost model explodes. If you don't, probes are useless for the exact categories that failed in Phase 1 (0/3 and 1/6, §11.7).

**[FATAL] Change 2 (Evidence-class corroboration) vs. Field-Shaped Signals:** You require a second independent signal to corroborate field-shape evidence. `TOOL_CONTRACT` violations (e.g., skipped quality gates) are inherently field-shaped absences (e.g., `checks_run == 0`). A skipped step does not emit a second corroborating signal. By requiring corroboration for field-shape evidence to bypass the credulous judge, you guarantee a 100% false-negative rate for omission-based tool violations. You fixed the false-positive problem by blinding the monitor.

**[MAJOR] Change 3 (Calibration loop executed):** You are initializing the v2 posterior with Phase 1 data (§6, §11.9). But Phase 1 operated under a passive monitoring paradigm. Probes (Change 1) will radically alter the base rate of observations. Applying Phase 1's passive-observation posteriors to v2's active-observation distribution is a statistical error that will result in wildly miscalibrated escalation thresholds on the first v2 run.

**[MAJOR] Change 4 (Priced ABORT/RETREAT) vs. Orchestrator Blindness:** The abort policy requires projecting "recovery cost against remaining task value." An agent mid-flight has notoriously poor estimates of "remaining task value," often believing it is one step away from completion for 20 steps. The abort trigger will misfire continuously on complex SWE-bench tasks, prematurely killing runs that just needed a single remap.

**[MINOR] Change 5 (Recovery-typed hints):** Forcing reality into five discrete `recovery_class` buckets assumes orthogonal failure modes. In schema drift (Reinterpret) combined with an endpoint move (Remap), forcing a single hint limits the orchestrator's replan scope, potentially causing replan-churn.

**[MAJOR] Change 6 (Two-tier vs Rebuilt Judge):** Removing the judge entirely places the entire burden on the DSL matcher. If Rival Story 2 (Predicate Brittleness) is true, the two-tier architecture will silently miss catastrophic invalidations because it lacks the semantic fallback a judge provides.

**[MINOR] Change 7 (Matcher fix):** Fixing one hardcoded bug gives zero guarantees about the structural integrity of the DSL parser at scale.

**[FATAL] Change 8 (Tiered compilation by work-at-risk) vs. Fan-out Realities:** Your plan to selectively strip monitoring from "small plans" assumes risk is proportional to duration. A short plan hitting a high-value API has massive work-at-risk (e.g., deleting a database in 3 steps). Basing monitor coverage on `fan-out x horizon` instead of `impact` guarantees you will miss critical, fast-moving failures.

### 3. Attack the Phase 1b Protocol (§11.10)

**[FATAL] The Protocol is a laundering machine for benchmark leakage.**
You explicitly admit v2 was designed from Phase 1's traces on these exact nine injections (§11.5). Re-drawing fire-counters and varying payloads (§11.10) does absolutely nothing to fix the structural overfit. You have literally hardcoded architectural fixes (e.g., the `probe` field, evidence-class downgrades) to patch the exact vulnerabilities exposed by this specific suite of 9 injections.
Your anti-overfit claim rests on the "full study" having natural failures, but Phase 1b itself is tainted. If Phase 1b passes, it proves only that you successfully reverse-engineered your own test set.
*Tightening measure:* Phase 1b must be evaluated on an entirely distinct set of 9 injection *categories* (e.g., RESOURCE_BUDGET and DEPENDENCY_VERSION, which were excluded from Phase 1 per §5) that the v2 design has never seen.

### 4. Attack the Gates (§11.10, item 2)

**[MAJOR] Missing Gate: Probe-Induced Perturbation Rate.**
Active probes manipulate the world. If you are scheduling automated deterministic probes (Change 1), you run the massive risk of rate-limiting the worker, consuming budget, or mutating state (e.g., executing a non-idempotent check). You have no gate measuring how many clean S5 runs die *because the probe itself broke the environment*.

**[MAJOR] 1bKG2 (Absolute caps on FIR):** Setting absolute caps for false interrupts is dangerous because it ignores the natural retry/error rate of the baseline suite. If tau-bench environments naturally throw transient errors, S5's FIR might spike legitimately. You need a Delta-FIR gate (S5 FIR - S2 FIR <= Absolute_Threshold), not a raw Absolute FIR.

**[MAJOR] 1bKG4 (Wasted-work parity):** You mandate wasted-work parity, but probe overhead must be accounted for in the *waste* column, not just the *compile* column. If S5 uses fewer tool calls but burns an equivalent amount of tokens spamming HEAD requests, you haven't saved work; you just shifted the compute from LLM inference to network I/O. The clause must explicitly read: `(S5 post-invalidation worker tokens + S5 total probe network/compute cost) <= S3`.

### 5. Attack the Novelty Claims (§10)

**[FATAL] Claim 1 & 5 (Plan-to-monitor compilation & Boundedness laws):**
As an FSE reviewer, I see nothing novel in "Information-bounded compilation." It is a tautology: a system cannot monitor what it is not aware of. Furthermore, "Observation-bounded detection" is identical to the concept of *Partial Observability* in standard Control Theory and POMDPs (Partially Observable Markov Decision Processes), and deeply explored in Runtime Verification (e.g., LTL monitor synthesis under incomplete trace observability). You are repackaging fundamental limits of distributed systems as "discovered laws" of your architecture.
*Delta check:* Fails.

**[MAJOR] Claim 1 & 2 (Compiled Active Probes):**
Standard MAPE-K implementations (e.g., Garlan's *Rainbow* framework) have used active probes for two decades. The cloud-native community calls this *synthetic monitoring*. Your only delta is that an LLM synthesizes the probe script from a natural language plan rather than a human writing it. However, since you claim these probes are compiled mechanically from OpenAPI specs and schemas (§8.2), you aren't even using the LLM for the probes; you are just doing standard API scraping.
*Delta check:* Fails. This is Swagger-to-synthetic-monitor generation, not a breakthrough in multi-agent reasoning.

**[MINOR] Claim 7 (Detection-latency economics):**
Cost-matching a heartbeat vs. an event-driven monitor is a well-established evaluation in systems engineering (e.g., polling vs. webhooks). Your result (3x faster at parity cost) is a solid engineering outcome, but it is a parameter finding, not a conceptual novelty.
*Delta check:* Survives as a systems benchmark, fails as a theoretical contribution.

### 6. Write the Rejection

**Summary:** This paper addresses a genuine problem in multi-agent orchestration—wasted compute post-plan invalidation—but its proposed solution, Sentinel Protocol v2, is structurally flawed and methodologically compromised. While the trace archaeology of the v1 failure is thorough, the v2 architecture directly overfits the v1 test set. More critically, the introduction of "active probes" abandons the core premise of zero-inference runtime monitoring, as content-based assumptions cannot be deterministically probed without incurring the very LLM costs the architecture claims to avoid. Finally, the "discovered laws" of monitoring are mere restatements of partial observability in classical systems literature.

**Objection 1 (Methodological Overfit):** The v2 architecture was explicitly reverse-engineered against the 9 injection types that defeated v1. Hardcoding an evidence-class downgrade for field-shape evidence because it caused false positives in Phase 1 guarantees a failure to generalize to true field-shape anomalies in out-of-distribution tasks.
*Status: Structural.*

**Objection 2 (The Active Probe Paradox):** The paper claims monitoring must be cheap and deterministic, yet the categories that failed (RETRIEVAL_INTEGRITY, TOOL_CONTRACT) require semantic, content-shaped checks. A deterministic script cannot re-verify semantic contradictions. To achieve the claimed active observability for these categories, the monitor must re-invoke an LLM, destroying the cost-advantage model presented in the break-even equation.
*Status: Structural.*

**Objection 3 (Trivialization of Novelty Claims):** Claims 1 and 5 frame the limitations of passive monitoring as novel "boundedness laws." These are direct analogs to unobservability in discrete event systems and classical runtime verification. The paper ignores two decades of MAPE-K literature addressing probe-based monitoring in self-adaptive systems.
*Status: Fixable by October 2 (requires severe dilution of claims and rewriting Section 10/2).*

### 7. Independent Forecast

* **(a) Strict recall ≥ 60%: 15%.** You broke the ability to catch field-shape anomalies by requiring corroboration; you traded false positives for false negatives, and the content-based probes will fail to compile reliably.
* **(b) Clean-run success parity: 40%.** Active probes introduce massive perturbation vectors to the environment, and the priced abort mechanism is highly likely to miscalculate and prematurely kill runs.
* **(c) TTD ≥ 2x and Wasted-work parity: 25%.** The network I/O and orchestration overhead of scheduling probes will eat your wasted-work margins alive, even if TTD remains fast.
* **(d) All of the above: 5%.** The architecture is fighting itself; fixes for one metric directly sabotage the others.

**Highest-Leverage $30 Experiment:** Run a single matrix execution of S5 v1 (no code changes) where you manually pipe the *raw* network/tool returns directly to the DSL matcher, bypassing the subagent's memory/context entirely, to permanently prove or disprove whether L2 "starvation" was actually an LLM context-erasure artifact.

---

### Top 3 Highest-Severity Items

1. **[FATAL]** The v1-to-v2 iteration is a blatant overfit; patching the architecture specifically against the 9 injections that defeated v1 guarantees benchmark leakage unless Phase 1b tests entirely new injection categories.
2. **[FATAL]** "Active probes" cannot deterministically check content-shaped semantic assumptions without an LLM, meaning you either accept blindness on those categories or destroy your own cost-efficiency model.
3. **[FATAL]** Requiring corroboration for field-shape evidence functionally blinds the protocol to absence-based anomalies (like skipped quality gates), guaranteeing false negatives to artificially lower the false-interrupt rate.
