<!--
BENCHMARK SPECIFICATION — Phase 1c fan-out task: DEMAND-NORMALIZED REGIONAL ALLOCATION (v3,
DRAFT for freeze; supersedes v2/v1). A controlled synthetic scaling test of the mechanism, built for
prereg_1c_fanout_v3.md's width-scaled estimand. NOT frozen, NOT qualified, NO treatment system
has touched it. Logged at freeze as benchmark-addition deviation (proposed D37) with a hash pin
over: this spec, the oracle, the eligible mutation field, the trigger rule, the recovery rule,
the demand distribution, and the information-boundary capability audit.
v3 CHANGELOG (third review — GPT, conditional approve; five edits):
 E1 capability audit broadened from the matcher to the INFORMATION BOUNDARY: baseline values stay
    sealed in per-surface side-channel state, never exposed to compiler/workers/orchestrator/any LLM,
    so no agent can compute baseline-T outside the matcher.
 E2 escape hatch reversed: if any aggregate path exists in the FROZEN 1b system, ABANDON the
    single-shard claim — no treatment code may be modified to preserve the estimand (no SUT surgery).
 E3 S3's schedule FROZEN (mandatory pre-Stage-2 sweep + cadence; snapshot and every reread costed).
 E4 post-pilot resize follows a PREWRITTEN cost/CV rule, blind to V2 detection / treatment-effect.
 E5 "signed report" removed → "immutable report with an opaque provenance identifier" (a real
    signature would itself reveal the corruption, violating §3).
v2 CHANGELOG (second adversarial review — GPT):
 F1/M2 S3 given a FAIR arm-time baseline + per-surface value-diff, cost-booked identically (the
       arm-time snapshot is a symmetric task feature; arms differ only in cadence/targeting).
 F3    single-shard invariant made airtight via a compiler/matcher NO-AGGREGATE-DIFF audit;
       global_total / reducer output is NOT a compilable tripwire target. Fork ratified =
       single-shard needle (forbid aggregate baseline-diff); §12 makes it confirmable.
 F2    injection timing gets a pre-evidence setup phase + an explicit regime justification.
 F4    renamed (no "fixed budget" invariant); demand-normalized shares; any budget B is exposed
       only post-share and cannot validate T.
 M1    construct-validity / threat-to-validity note added.
 M3/M4 retrieval-integrity corruption of an immutable report; provenance_id opaque.
 M5/m2 mutation distribution + fixed-width encoding + anomaly audit fully specified.
 M6    N=32 rationale rewritten as budget/conservatism; crossover recomputed for THIS task post-pilot.
 M7    Stage-2 work unit calibrated; Stage-1/Stage-2 waste reported separately.
 M8    three-way outcome split (correct completion / valid-with-salvage / abort rate).
 m1/m4/m5 baseline-order trace fields; runtime-oracle isolation; post-pilot treatment lock.
Author sign-off items marked [AUTHOR-CONFIRM].
-->

# Benchmark — Demand-Normalized Regional Allocation (Phase 1c fan-out task), v3

**Status:** draft for freeze · spec hash: `[SHA-256 at freeze]`
**Purpose:** the width-scalable task `a1` could not supply. One silently-corrupted shard changes a **shared denominator**, so every final output is *mathematically* invalid — "all N outputs wasted" is an arithmetic fact, not a harness policy. Detection is single-visit-hard by construction (§3), so the task tests observation-bounded detection at fan-out, not a softened proxy.

**Claim scope (frozen).** A *controlled synthetic scaling test of the mechanism and its cost model on this workload.* No Phase-1c result licenses a broad efficiency claim; the deployment claim stays deferred to the real-suite fan-out study (prereg_1c §9).

**Construct-validity note (frozen — M1).** This surface is *intentionally mechanism-isolating*: it tests whether baseline-probe monitoring scales when the only valid signal is a one-shard value change. It does **not** show that all fan-out faults reduce to baseline-diff retrieval integrity, nor that the mechanism helps on fault classes with observable structural signatures.

---

## 1. Scenario and structure

**Widths:** N ∈ {8, 16, 32} (N=64 dropped — see §13).

**Task — compute demand-normalized regional allocation shares from N verified demand ledgers**, in two parallel stages joined by a deterministic reducer:

- **Manifest (pre-run).** A manifest lists the N `region_id`s and their surface URLs — and **nothing else**: no demand values, totals, checksums, or expected ranges beyond generic schema (m3). It exists so a monitoring arm can enumerate all N surfaces to baseline.
- **Setup phase (F2).** Each worker performs a fixed, nontrivial pre-evidence task unit (schema fetch + plan-local computation) so meaningful work precedes the fault — the injection lands mid-execution, not before work begins.
- **Stage 1 — read (N parallel).** Worker i reads one fixed-size **immutable** evidence report from surface `S_i`, extracts demand `d_i` and `provenance_id`.
- **Reduce (deterministic, no LLM).** `T = Σ_{i=1..N} d_i`.
- **Stage 2 — allocate (N parallel).** Worker i emits a fixed-size allocation package: `region_id`, `verified_demand = d_i`, `provenance_id`, `global_total = T`, `share = d_i/T` as an **exact rational `numerator/denominator`** (no floats). Stage-2 work-unit size is frozen and identical across widths (M7): fixed field/token budget, same template at N=8/16/32, no verbosity inflation. If a budget `B` exists at all, it is exposed *only after* shares are computed and **cannot** validate `T` — the oracle checks demand-total correctness, not budget conservation (F4).

Fixed work per worker; total grows with N (the width-scaled estimand). Regions are independent except through the shared `T`.

---

## 2. Per-arm behavior (S3 made fair — F1/M2)

The **arm-time snapshot** — a clean baseline read over all N manifest surfaces, captured before the setup phase — is a **symmetric task feature available to any monitoring arm**, cost-booked per re-read identically across arms. Arms differ only in *cadence and targeting*, never in baseline access:

- **S1 (batch):** does not monitor; uses no baseline; the fault surfaces only at final validation. Waste = N invalid allocation packages → W_batch scales with N.
- **S3 (heartbeat, baseline-diff — fair comparator):** takes the same arm-time snapshot over all N surfaces; re-reads surfaces and value-diffs each against its stored baseline on a **frozen periodic cadence** `[AUTHOR-CONFIRM: heartbeat period, cost-matched to S3's 1b cadence]`, and runs a **mandatory full N-surface sweep immediately before Stage 2 dispatch** (not discretionary). The initial snapshot and **every** reread are fully costed against cost and injection timing **identically to V2** — no S3 read is free. (S3's 1c configuration is a baseline-diff heartbeat; if this differs from the 1b S3, it is declared as a deviation at freeze — §12.)
- **V2 (sentinel):** compiles per-surface baseline probes from the manifest, re-checks via the probe-primary/corroboration cadence, value-diffs each surface against its arm-time baseline, interrupts on a single-surface mismatch, and recovers (§8). Must arm baselines across all N surfaces to be sound.

The treatment difference is purely *mechanism* (compiled probe-primary targeting vs periodic heartbeat sweep), with baseline access held equal — so a V2 win on cost or detection timing is not an information advantage.

---

## 3. Detection-locus invariant (ratified: single-shard; airtight via capability audit — F3)

**The only sound detection path is a per-surface value-diff against the arm-time baseline.** Aggregate baseline-diff (computing baseline-`T = Σ baseline d_i` and comparing to runtime `T'`) is **forbidden for all arms** so that detection means *finding the mutated shard among N*, not noticing the sum moved:

1. **No observable expected total / cross-surface invariant.** `T` is knowable only by summing the N reads; no manifest total, budget invariant, aggregate checksum, or per-region quota is exposed. `d_j`'s only ground truth is `S_j` + its arm-time baseline.
2. **Post-injection world internally consistent.** `T' = Σ(read values)`, every `share` sums to 1 against `T'`; each package is internally valid. Backing out `d'_j` only confirms internal consistency — it does not reveal the corruption. No static/structural tripwire can catch it.
3. **Plausible mutation** (§4) — no range/sanity tripwire fires.
4. **Compiler is total-blind.** Grounding sources expose per-surface read contracts only — never an expected total, sum-consistency rule, the reducer output, or `global_total`. `global_total`/`T'` is **not a compilable tripwire target**.
5. **Information-boundary capability audit (frozen, verified before any treatment run — E1).** The constraint is on the *information boundary*, not merely the matcher operator, because a baseline aggregate could be computed anywhere the baseline values are visible. Two requirements: (a) **baseline values stay sealed in per-surface side-channel state** and are **never exposed** to the compiler, workers, orchestrator, or any other LLM — so no agent can compute baseline-`T = Σ baseline d_i` outside the matcher; (b) the **matcher has no cross-surface aggregate-reduction operator** — a tripwire may compare one surface's runtime read to that surface's own baseline, and may not reduce across surfaces or compare any baseline aggregate to a runtime total. The compiler receives neither the oracle, the validator, nor this benchmark spec, and `global_total`/`T'` is not a compilable tripwire target (§3.4). The audit artifact (`runs/matrix_1c/information_boundary_audit.json`) enumerates every place baseline values are readable and the matcher's full predicate set, and proves no aggregate path exists by either route.
6. **Abandon, do not modify (E2).** If **any** aggregate path exists in the **frozen 1b system** — whether through baseline exposure (5a) or a matcher operator (5b) — the single-shard claim is **abandoned** and the estimand is reported as "baseline-derived aggregate-or-shard diff." **No treatment code (compiler, matcher, probe layer, side-channel) may be weakened, re-sealed, or otherwise modified to preserve the single-shard estimand.** The benchmark adapts to the frozen system; the system is never altered to fit the benchmark. (Benchmark-driven SUT surgery is the same category of error as renegotiating a kill gate.)

**Consequence.** Soundness requires baselining all N surfaces (the arm cannot know `j`), the origin of probe-volume(N) and the deployment-cost canary. Detection is *possible* but hard and harder at larger N — the recall(N) curve Phase 1c measures. **Misses at high N are expected and reported, never engineered away (§9).**

---

## 4. Single-shard injection (M3/M4/M5/m2)

After the setup phase and the N distinct `prepare` events, **before any Stage-1 evidence read** (§5):

- Select shard **j** by a seeded width-balanced rule (each index equally likely across seeds) — `[AUTHOR-CONFIRM: rule]`.
- Mutate exactly one value `d_j → d'_j` on `S_j`.
- **Source semantics (M3/E5):** `S_i` is an **immutable report identified by an opaque provenance id**; for the run the source is supposed to be fixed. The mutation changes the value while `provenance_id` stays invariant — so baseline-reconcile is the *only* semantically correct recovery, not an arbitrary "treat change as bad." This is a **retrieval-integrity corruption**, explicitly **not** a live-update task. There is deliberately **no signature or verifiable digest** over the value: a real signature would itself fail on the corrupted value and hand detection a structural signature path, violating §3 — so verification semantics are unavailable at runtime by design.
- **Provenance (M4):** `provenance_id` is an **opaque stable identifier** — not a checksum, version, timestamp, digest, or retrievable validation handle; **no provenance/verification endpoint exists at runtime.**
- **Hold invariant on `S_j`:** HTTP status, schema, field names, response length/encoding, provenance id. No `changed`/`error`/`version`/warning field anywhere.
- **Mutation distribution (M5/m2):** `d'_j` is drawn from the **same conditional demand distribution** as the original; **fixed-width numeric encoding** (same digit length — `999`→`1001` length leaks are forbidden; pad to fixed width); excluded from extreme quantiles `[AUTHOR-CONFIRM: e.g. bottom/top 5%]`; with a **minimum wound margin** large enough that `T' ≠ T` fails the validator yet small enough to stay non-outlying `[AUTHOR-CONFIRM: margin]`. A **static anomaly audit** (frozen) certifies `d'_j` is not detectable by range, z-score, rank, digit-length, schema, provenance, or response-size checks.
- Leave all other N−1 surfaces **byte-identical** to clean.

Canonical oracle retains `d_j`, so batch computes `T' = T − d_j + d'_j`, and every final package carries `global_total = T' ≠ T`: all N packages invalid (`GLOBAL_TOTAL_MISMATCH`), an arithmetic fact.

---

## 5. Execution structure (start barrier + setup phase — F2)

1. Spawn exactly N workers (executor width N via D35).
2. **Setup phase:** each worker performs its fixed pre-evidence work unit.
3. Each worker calls a neutral `prepare(region_id)`; no evidence read yet.
4. After N **distinct** `prepare` events, **fire the injection** on `S_j`.
5. Release Stage-1 reads → reduce → `T'`.
6. Dispatch/resume N Stage-2 allocations.
7. Validate the complete set.

**Injection-timing justification (frozen — F2).** The start-barrier trigger is chosen because the estimand requires the mutated shard to be *unread* at fault exposure while all N shards are already committed and have done setup work. It tests the **post-plan, pre-read corruption** regime where baseline monitoring can pay; it is **not** claimed to sample all mid-run invalidation timings. The setup phase ensures meaningful work precedes the fault so W_batch waste is real.

**Concurrency note (refines prereg_1c §2).** Poisoning propagates through the shared reducer `T`, not through simultaneous in-flight workers — so all N outputs are invalid regardless of read-time overlap. Realized concurrency is a recorded covariate (§9), **not** load-bearing for "all N affected"; the barrier guarantees single-fault-bearing-read assignment, not a concurrency number.

---

## 6. Oracle (exact, programmatic; runtime-isolated — m4)

Grader only — **never a runtime signal.** It retains canonical `{d_i}` and true `T`. A package set passes iff for all i: `global_total == T` **and** `share_i == d_i/T` (exact rational) **and** `verified_demand == d_i` **and** provenance ids intact.
- Clean: passes. Injected-undetected: N packages with `global_total == T' ≠ T` → wound `GLOBAL_TOTAL_MISMATCH`. Injected-recovered: §8.
- **Runtime isolation (structural qualification):** no worker, orchestrator, or tool may call the oracle or receive `GLOBAL_TOTAL_MISMATCH` before the run ends.

---

## 7. Recovery path (M3)

The injection is a **corruption of an immutable report** (oracle retains original `d_j`), so recovery is **RECONCILE-to-baseline**: on detecting `S_j`'s post-injection read ≠ its arm-time baseline, restore the baseline `d_j`, recompute `T`, regenerate the N allocations → passes §6 (`global_total == T`). Because detection via baseline supplies the recovery value, a detection is typically **detect-and-recover**; a detection that interrupts but cannot regenerate within budget is **detect-and-justified-abort** (salvage = flag the integrity violation, emit no invalid allocation). Detect-only and silent failure are non-passing.

---

## 8. Recorded quantities (manipulation check, baseline order, cost canaries, outcomes)

Per cell, never trusting nominal width: workers started at injection; distinct shards assigned (+ any duplicate/missing); the fault-bearing read; max concurrent workers; N downstream outputs produced-or-prevented; invalid-package count. **Baseline ordering (m1):** per surface, the baseline read counter, and a proof that `baseline(S_j) < injection < detection_read(S_j)`; flag any missing or post-injection baseline. **Cost canaries (prereg_1c §5):** compiler input/output tokens and **C(N)**; armed-surface count and **probe-volume(N)**; sweep count; **Stage-1 and Stage-2 waste reported separately** (M7); per-arm total cost; realized fan-out; any context-overflow/timeout/rate-limit (an experimental outcome per prereg_1c §6.1, not an integrity failure). **Outcome split (M8) — report all three, never collapsed:** (1) cost per **correct completion** (allocation set == oracle); (2) cost per **valid outcome** counting justified-abort-with-salvage; (3) **abort rate.** A high abort rate may not support "pays at scale" unless the paper says *pays for valid detection/salvage*, not *for successful completion*.

---

## 9. Qualification before any treatment system touches the task

**Structural (every N ∈ {8,16,32}):** exactly N unique shards; fixed-size work/shard; exactly one mutated raw surface; N−1 byte-identical; detection-locus invariants §3.1–§3.6 verified (incl. the information-boundary audit §3.5 and no-runtime-validator m4); `T' ≠ T`; validator reports exactly **N** invalid packages; scripted recovery (restore `S_j` baseline, recompute `T`, regenerate) passes; the static anomaly audit of `d'_j` passes.

**Empirical S1 (every N):** clean S1 = **3/3** exact pass; injected S1 = **3/3** wounded by the intended `GLOBAL_TOTAL_MISMATCH`, first-pass invalid-output count = N; no timeout/formatting/unrelated-validator failure counted toward qualification.

**Revision rule.** If a revision is needed, version it, report *why* the prior failed, **rerun qualification from zero.** Never silently retain only the successful revision.

**Hard rule.** **V2 performance is NOT qualification.** Once V2 has seen the task, mutation difficulty is never adjusted to help detection. *A miss is a result* (§3 makes misses expected at high N).

---

## 10. Integrity controls (before treatment runs)

Log as benchmark-addition deviation **D37**; freeze+hash the spec, oracle, mutation field, trigger rule, recovery rule, demand distribution, and the information-boundary audit. Draw `j`/`d'_j` for confirmatory cells from **sealed** parameters; retain one **disjoint development mutation** for the pilot. Same fixture/shard/mutation across paired arms. Burn all qualification + pilot seeds. Keep compiler, matcher, probe cadence, corroboration, recovery **byte-identical** to the 1b build (SUT-neutral; prereg_1c §4 diff artifact). A new benchmark *surface*, declared and qualified — not "plan input only."

**Post-pilot treatment lock (m5):** after the feasibility pilot, only **sample size and N grid** may change — never task semantics, mutation difficulty, probe cadence, compiler prompt, or recovery policy.

**Blind resize rule (E4).** The post-pilot change to sample size or N grid follows a **prewritten cost/CV formula, frozen before the pilot runs and computed only from the pilot's per-seed cost/waste variance and the budget** — explicitly **blind to V2 detection, recall, and any treatment-effect result.** The pilot may size the confirmatory matrix; it may **not** influence the design through what it revealed about whether V2 won. (Same firewall as burning the pilot seeds, applied to the design decision.)

---

## 11. Red lines (do not)

N workers redundantly reading the same fault · any loud `404`/error/changed/version flag · a finalizer that discards N outputs by policy rather than by `T' ≠ T` arithmetic · any observable expected-total, aggregate checksum, cross-surface invariant, or matcher aggregate-reduction path (breaks §3) · **baseline values exposed to the compiler, workers, orchestrator, or any LLM** (breaks §3.5a) · **modifying any treatment code to make the information-boundary audit pass** (breaks §3.6) · a runtime-reachable oracle/validator (breaks m4) · treatment performance deciding whether an injection qualifies · pooled cross-task CV (2.10) used to freeze sample size (use the forced-width pilot CV) · a resize decision influenced by V2 detection results (breaks E4) · a fixed-overhead assumption without measuring C(N) and probe-volume(N) · variable-length numeric encoding that leaks the mutation by length · any signature/digest over the value that would itself reveal the corruption.

---

## 12. Author sign-off before freeze
- `[AUTHOR-CONFIRM]` **the F3 fork** — ratified here as *single-shard needle (forbid aggregate baseline-diff)*; flipping to *baseline-monitoring-by-any-route (allow aggregate for both arms)* is a §3 rewrite. Single-shard is the harder, on-thesis, less-attackable version and matches your prior choices; confirm or flip.
- `[AUTHOR-CONFIRM]` S3's 1c configuration as a **baseline-diff heartbeat**, its **frozen heartbeat cadence/period** (cost-matched to 1b S3), and whether this differs from the 1b S3 → declare as a deviation if so.
- **RATIFIED-PRE-PILOT (2026-06-25, not hash-pinned)** — the prewritten blind resize formula: `n_seeds(N) = max(5, ⌈(1.645·SD_seed[B_p(N)] / H)²⌉)` at worst-case p, **H = $0.015** (one-sided-95%-LCB half-width on the §6.2 estimand `B_p(N)`), **budget bound B = $450**; per-width N∈{8,32}, binding-width n. Computed blind to detection / treatment-effect, frozen before the pilot.
- `[AUTHOR-CONFIRM]` demand distribution + magnitudes; fixed-width encoding width; excluded quantiles; minimum wound margin for `d'_j` (wound the validator, stay non-outlying).
- `[AUTHOR-CONFIRM]` share representation = exact rational (recommended) vs fixed-precision decimal + frozen tolerance.
- `[AUTHOR-CONFIRM]` the seeded width-balanced shard-selection rule for `j`.
- `[AUTHOR-CONFIRM]` Stage-2 fixed work-unit size (token/field budget).
- `[AUTHOR-CONFIRM]` the disjoint development mutation reserved for the pilot.

---

## 13. N=32 cap (M6)

N=32 is the **largest width tested because it is the highest affordable width under the pilot budget** and avoids the high-variance N=64 tail — **not** a transfer of the old model's 25–86 crossover, which came from a different cost structure than this new surface. The expected crossover **for this task** is recomputed from the feasibility pilot (prereg_1c sizing). Any crossover above 32 is **unobservable by design** and reported as such; "no crossover demonstrated through N=32" must not be read as "no crossover exists." This is the conservative (against-the-architecture) direction.
