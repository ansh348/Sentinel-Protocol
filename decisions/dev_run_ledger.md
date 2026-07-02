
---
## Phase-1c benchmark S1 QUALIFICATION  (DRAFT / NOT FROZEN, not confirmatory)
- date: 2026-06-25  ·  spec: decisions/benchmark_1c_sharded_allocation_v3.md (un-pinned)
- purpose: §9 S1 qualification (structural + empirical) for the sharded-allocation surface
- seeds BURNED (qualification, not reusable for confirmatory): [9101, 9102, 9103]
- N grid: [8, 16, 32]  ·  worker model: claude-haiku-4-5-20251001  ·  in-flight ceiling: 8
- LLM worker calls: 337  ·  TOTAL SPEND: $0.7561 (hard cap $25)
- result: clean 9/9 exact-pass · injected 9/9 wounded (GLOBAL_TOTAL_MISMATCH, N invalid) · qualified=True
- artifact: runs/matrix_1c/s1_qualification.json

---
## Phase-1c CONCURRENCY FEASIBILITY probe  (FEASIBILITY / NOT FROZEN, not confirmatory)
- date: 2026-06-25  ·  host: Windows-11 (local laptop, NOT a separate provisioned container) (16 vCPU, 16.4GB RAM, 4.6GB free at start)
- D21 cmd-shim: CLEAR -- TRIPWIRE_CLAUDE_BIN unset; resolves to real PE32+ claude.exe (no .cmd shim)
- worker: trivial single-turn Haiku call (concurrency stress, not detection)  ·  seeds BURNED: [7701, 7702]
- ramp: 8:CLEAN -> 16:FAILED
- VERDICT: largest CLEAN N = 8; N=16 FAILED -- host-memory (pre-launch gate)
- spend: $0.0167  ·  llm calls: 16  ·  artifact: runs/matrix_1c/concurrency_probe.json

---
## Phase-1c API-KEY auth switch + EQUIVALENCE GATE  (FEASIBILITY / NOT FROZEN, not confirmatory)
- date: 2026-06-25  ·  STEP-0 docs read from platform.claude.com (base api.anthropic.com, x-api-key, anthropic-version 2023-06-01, Haiku claude-haiku-4-5-20251001, Sonnet claude-sonnet-4-6)
- harness change D38 (D21-adjacent): ANTHROPIC_API_KEY direct Messages-API worker path (urllib POST /v1/messages)
- EQUIVALENCE GATE on shard R-0001: model_match=True, output_shape_match=True, gate_pass=True  (api $0.000511 / sub $0.00164)
- VM ramp (STEP 1/4, N=16/32/64): BLOCKED -- no cloud credential / provisioning CLI in env
- cost extrapolation (30s x 3 arms x 2 cond x N{8,16,32}): ~$37 (+N64 ~$43); spend this step $0.0022
- artifact: runs/matrix_1c/apikey_equivalence.json

---
## Phase-1c API-DIRECT CONCURRENCY RAMP (FEASIBILITY / NOT FROZEN, not confirmatory)
- date: 2026-06-25  ·  path: API-key direct Messages API (thread+HTTPS, NO subprocess) -- run LOCALLY (the sub-CLI 259MB/worker memory wall does not apply)
- ramp: 8:CLEAN -> 16:CLEAN -> 32:CLEAN -> 64:CLEAN
- largest CLEAN N = 64; binding constraint at high N = none within tested range
- seeds BURNED: [7701, 7702]  ·  spend $0.0459  ·  calls 240  ·  artifact runs/matrix_1c/apikey_concurrency_ramp.json

---
## Phase-1c D38 FULL-worker-path equivalence gate (FEASIBILITY / NOT FROZEN, not confirmatory)
- date: 2026-06-25  ·  method: localhost logging proxy (ANTHROPIC_BASE_URL) captured the CLI's actual /v1/messages requests
- STEP 0: cache_read EXCLUDED from ITPM; Tier-4 per-class (Sonnet 4k/2M/400k, Haiku 4k/4M/800k, Opus 4k/10M/800k) -- brief's 10k/10M/2M figures corrected
- STEP 2 (request equivalence): B1 thin-API FAILS on ALL call sites -- CLI injects 3-block system (billing+preamble+prompt), thinking/effort/output_config/context_management/metadata/stream/?beta=true/claude-code-20250219/cache breakpoints + an auxiliary Haiku title call; tool worker gets the full 29-tool catalog. B2 (CLI+API-key) PASSES by construction.
- STEP 3: not run (STEP 2 failed for B1; B2 identical by construction)
- STEP 4: B1 COMFORTABLE @Tier4; B2 TIGHT-but-manageable (agent loop+29 tools inflate ITPM; CLI prompt-caching gives free cache-read ITPM)
- STEP 5: confirmatory MUST run on B2 (CLI+API-key) for Phase-1b comparability -> subprocess -> VM needed for N>8; B1 thin-API only for non-confirmatory probes
- artifact: runs/matrix_1c/d38_full_equivalence.json (+ pathA_capture.jsonl, pathA_worker_capture.jsonl)

---
## Phase-1c RAILWAY B2 run -- ATTEMPTED, BLOCKED (FEASIBILITY / NOT FROZEN, not confirmatory)
- date: 2026-06-25  ·  NO live deploy: railway CLI UNAUTHENTICATED (needs `railway login`) + Docker daemon DOWN (Docker Desktop not started)
- CLI DRIFT FINDING: Phase-1b SUT = 2.1.170; last-task equivalence + current = 2.1.193 (both on npm). Equivalence to the real 1b SUT (2.1.170) NOT established -- pin 2.1.170 + re-capture before claiming 1c<->1b comparability.
- COST (Eray number, B2 real multi-turn worker @ $0.0193/worker from 1b banked + compile $0.1376): core(worker+compile) ~$227, full(+orchestrator) ~$292 for 30s x 3 arms x 2 cond x N{8,16,32} (10080 workers). ~6-8x the thin-API ~$37.
- Tier-4 peak-minute: COMFORTABLE on console limits (10k/10M/2M) at sane pacing; TIGHTER on doc-standard (4k/2M Sonnet).
- prepared (UNTESTED): deploy/railway/{Dockerfile,railway.toml,entrypoint.sh}; equiv recheck reuses _capture_proxy/_capture_pathA
- spend this step: $0 (no calls; cost computed from banked data). artifact: runs/matrix_1c/railway_b2_status.json

---
## Phase-1c CLI version diff 2.1.170 vs 2.1.193 (FEASIBILITY / NOT FROZEN, not confirmatory)
- date: 2026-06-25  ·  isolated npm-bundled native claude.exe per version; auth constant (ANTHROPIC_API_KEY); fixed inputs; proxy capture; VERSION the only variable
- VERDICT: NOT identical. Real tool-catalog diffs: COMPILE sends 0 tools(193) vs 3(170: DesignSync,Monitor,PushNotification) under --tools ''; WORKER 29(193) vs 31(170), diff {only170: AskUserQuestion,EnterPlanMode,ExitPlanMode; only193: SendMessage}.
- Neutral-only: billing cc_version tag, title-call prompt wording. Identical: model ids, max_tokens, thinking, effort, context_management, beta flags, the v2_compile.md prompt block (verbatim).
- IMPACT: differing tools are non-executable for these gated sites (plausibly low behavioral impact) but the request DIFFERS -> not assumable neutral. 1c MUST PIN 2.1.170 for 1b-comparability (-> Dockerfile default already 2.1.170).
- installed state: native PATH CLI unchanged = 2.1.193; 2.1.170 kept at isolated C:/temp/claude170 (not PATH/repo). spend ~$0.16. artifact: runs/matrix_1c/cli_version_diff.json

---
## Phase-1c 1b VERSION ANCHOR -- HARD GATE FAILED, STOPPED before Railway deploy (FEASIBILITY / NOT FROZEN)
- date: 2026-06-25  ·  Q: did Phase-1b actually run on 2.1.170 (the settled pin)?
- EVIDENCE: harness runtime stamp payload.cli_version in ALL 172/172 matrix_1b cells == 2.1.177 (run_one.py:940; queue.py cli_version_guard locks 1 version/run). 2.1.170 appears NOWHERE in run traces (only prereg.md's DECLARED pin). 1b saved no request bodies, so the explicit stamp is the evidence.
- VERDICT: Phase-1b ran on 2.1.177, NOT 2.1.170. The CLI auto-updated past the declared 2.1.170 pin before the matrix executed. STOP -- did not deploy/spend on Railway.
- CORRECT PIN = 2.1.177 (Dockerfile updated 2.1.170->2.1.177). 3-way capture: worker catalog 2.1.177==2.1.170 (31 tools) != 2.1.193 (29); compile ambient tools 170={DesignSync,Monitor,PushNotification}/177={Monitor,PushNotification}/193={} (all differ).
- supersedes last task's 'pin 2.1.170' verdict (anchored to a version 1b never ran). PROVENANCE: SUT-of-record = 2.1.177 per runtime stamp, not prereg's 2.1.170.
- Railway spend $0 (no deploy); Anthropic spend ~$0.16 (2.1.177 capture); cost cap $15 never reached. artifact: runs/matrix_1c/cli_1b_anchor.json

---
## Phase-1c Railway B2 probe -- EQUIVALENCE HARD GATE caught OS divergence; STOPPED pre-deploy (FEASIBILITY / NOT FROZEN)
- date: 2026-06-25  ·  validated LOCALLY before any Railway spend: image builds, in-container `claude --version`==2.1.177 (real 1b SUT), persistence-survives-redeploy logic PASS, B2 auth (ANTHROPIC_API_KEY) works, real multi-turn worker probe N=4 CLEAN (per-worker $0.0201 ~= $0.0193 banked; prefix cache-hit 8/8).
- EQUIVALENCE re-confirm: compile tools MATCH (Monitor,PushNotification) but WORKER catalog Linux-container=28 vs Windows-2.1.177-ref=31, missing {Glob, Grep, PowerShell} (PowerShell Windows-only; Glob/Grep Windows-only in the CLI).
- ROOT CAUSE: Phase-1b ran on WINDOWS; Railway containers are LINUX. The CLI tool catalog is OS-DEPENDENT, so version-pin (2.1.177) is necessary-not-sufficient -- no Linux container can be request-identical to the Windows 1b SUT.
- IMPLICATION: Railway-Linux cannot host a comparability-preserving 1c SUT. The catalog delta is non-executable for the curl-gated worker (plausibly low behavioral impact) and OS-robust metrics (concurrency/memory/cost) are still valid on Linux -- so the CHEAP feasibility probe could proceed with an OS caveat, but strict 1b-comparability needs a Windows host.
- NOT deployed to Railway (no compute billed). Local spend ~$0.5 API (smokes). Image tw-b2 + volume tw-b2-data kept locally for the chosen path.

---
## Phase-1c Railway B2 PROBE -- RAN on Railway (FEASIBILITY / NOT FROZEN, not confirmatory)
- date: 2026-06-25  ·  isolated project tw-b2-probe / service tw-b2 (GGMR never touched)  ·  in-container claude 2.1.177 (real 1b SUT)  ·  B2 = real CLI + ANTHROPIC_API_KEY
- HARD GATES: persistence PROOF PASS (redeploy -> /data marker SURVIVED); equivalence: compile tools MATCH, worker 28 vs 31 = ACCEPTED OS delta {Glob,Grep,PowerShell} (Linux vs Windows-1b; non-executable for curl-gated worker; metrics OS-robust). User ratified Option 1.
- RUNG TABLE (real multi-turn worker): N=16 CLEAN 16/16 | N=32 CLEAN 32/32 | N=64 DEGRADED 64/64 (13/128 worker errors). largest CLEAN N=32.
- RAM vs API: NEITHER binds through N=32 (161GB free, 0x 429 even at N=64). N=64 limiter = per-worker subprocess errors (timeout/transport), not RAM/rate-limit.
- per-worker cost ~$0.011-0.027 (cache-effective; brackets $0.0193 banked); prefix CACHE-HIT at scale (every worker, cache_read>0).
- CONFIRMATORY-PLATFORM FLAG (no action): 1b=Windows, probe=Linux; OS delta non-cosmetic for the confirmatory run. Open options (a) Windows host, (b) Linux-as-distinct-SUT, (c) re-baseline 1b on Linux. OPEN for author.
- spend: Anthropic ~$2.83 probe + $0.16 Railway-equiv (+ ~$0.5 local smokes); Railway compute minimal (one-shot, restart=NEVER); $15 cap never approached. durable copy: runs/matrix_1c/railway_probe/summary.json (raw /data kept on the Railway volume as backup).

---
## Phase-1c CV PILOT — STEP-0 gate ratified + formula FROZEN pre-pilot; STEP-3 BLOCKED (V2 not built for benchmark) (PILOT / NOT FROZEN / NOT CONFIRMATORY)
- date: 2026-06-25  ·  STEP 0: estimand B_p(N) specified (prereg §6.2). Resize formula was unsigned [AUTHOR-CONFIRM] -> author RATIFIED -> recorded in prereg §5 + benchmark §12 as RATIFIED-PRE-PILOT (blind, frozen before pilot, NOT hash-pinned): n_seeds(N)=max(5, ceil((1.645·SD_seed[B_p(N)]/H)^2)) worst-case p, H=$0.015, budget B=$450 (surface n-wanted vs affordable, no truncation).
- STEP-3 PREMISE FAILS: B_p = K_S1 − K_V2 needs BOTH arms on the benchmark_1c task. S1-on-benchmark is built/qualified; the FULL V2 ARM HAS NEVER BEEN WIRED TO benchmark_1c. The V2 stack (run_v2_loop, compile_probes, arms, corroboration) runs only on tasks a1/b1/c1/d1 via tasks/*.yaml + world/server.py; grep confirms NO benchmark_1c integration in conductor/sentinel_v2/world.
- Building V2-on-benchmark = the §9 V2-qualification of the benchmark (task YAML + N-shard world server + single-shard injection + compile producing per-surface baseline-diff probes + arms/corroboration wiring) — a major integration, NOT a pilot input. a1-proxy is infeasible: a1's emergent ~3-step plan cannot be forced to N=8/32 width (the width-scaling gap the benchmark exists to fill).
- STOPPED before any Railway deploy/spend ($0 this task). Cannot measure forced-width SD_seed[B_p(N)] until V2-on-benchmark exists. Open for author: (a) authorize the V2-on-benchmark build, then run the pilot; (b) halt the CV pilot until V2-on-benchmark is built.

---
## Phase-1c R1 DETERMINATION — plan-named-id grounding BYPASSES FAMILY_MEMBER_CAP=24 (DETERMINATION / NOT FROZEN / NOT CONFIRMATORY)
- date: 2026-06-25  ·  code-read + local grounding test (no LLM, SUT ground_surface unmodified §3.6), $0.
- CODE PATH: FAMILY_MEMBER_CAP=24 (compile_probes.py:162) is applied in EXACTLY ONE branch of ground_surface — all_bounded (line 218: bounded[:FAMILY_MEMBER_CAP]). The plan_named branch (line 217: members=named) and the concrete branch (line 222: members=(s,)) carry NO cap. plan_named is derived (lines 291-293) from the soft set's concrete, groundable surfaces (injection-blind).
- LOCAL TEST (32 region samples): template + NO plan_named -> mode=all_bounded, 24 armed, 8 overflow (cap bites). template + 32 plan_named -> mode=plan_named, 32 armed, 0 overflow (BYPASS). 16 plan_named -> 16 armed.
- VERDICT: NAMED IDS BYPASS THE CAP. Full N=32 coverage is achievable via a named-id D36 plan with NO SUT surgery. The bare {region_id} template idiom still ceilings at 24 (separately reportable). Realizing full coverage additionally requires the world to serve all N samples AND the compile to faithfully name all N ids (compile-fidelity, a separate verification, not done here).
- R1 in v2_on_benchmark_build_scope: resolved to the "bypass" world.

---
## Phase-1c V2-on-benchmark scope RE-SCOPED — added no-LLM-compiler ablation arm V2nc (SCOPING / DRAFT / NOT FROZEN, planning only)
- date: 2026-06-29  ·  PLANNING ONLY, no code/build/spend ($0).  Responds to external reviewer's strongest objection (is the LLM compile necessary vs deterministic re-observation).
- V2nc = V2 substrate, LLM compile_assumptions REPLACED by a deterministic selection rule: arm a per-surface VALUE baseline-diff probe on EVERY shard endpoint the plan touches (static enumeration from openapi_paths_for_rev / path_samples, /regions/* prefix); uniform field_read+BASELINE_DRIFT lens. Same arm-time baseline / cadence / corroboration / barrier / replan.
- §3.6: V2nc is a NEW ARM (parallel branch at compile-and-arm), V2's compile branch byte-identical; not SUT surgery.
- R1 fold-in (resolved): plan-named ids bypass the cap; V2 coverage compile-fidelity-dependent (full if named, 24 if bare template); V2nc coverage = all N by enumeration, cap-independent -> reportable coverage contrast.
- Further ablations: probes-without-compiler = V2nc (cheap, in scope); compiler-without-probes = separate build (flagged, not committed).
- Cost/effort delta: V2nc marginal ~$20 (workers+orch, NO compile) + ~0.5d; revised combined ~$75-85 (over $50 cap). Updated scope doc §2A/§4/§5-R1/§6/§7.

---
## Phase-1c COMPILE-FIDELITY CHECK — real Sonnet compile names ALL 32 named ids; V2 full-coverage REAL (DETERMINATION / NOT FROZEN / NOT CONFIRMATORY)
- date: 2026-06-29  ·  one real Sonnet compile (compile_probes.compile_assumptions, unmodified §3.6) on a named-id N=32 D36-style plan; SUT grounding on synthetic 32 samples. spend $0.3969.
- RESULT: compile emitted 133 assumptions; 131 region surfaces — 32 DISTINCT CONCRETE ids (region_0001..region_0032) + 1 template /regions/{region_id}/evidence. SUT grounding: plan_named=32, modes {concrete:128, plan_named:3} -> DISTINCT surfaces ARMED = 32/32. 66 region assumptions carry a value pointer (field baseline-diff lens).
- VERDICT: FULL — V2's full-coverage path at N=32 is REAL (the LLM names all 32; it does NOT collapse to <=24). The cap only bites a bare template, which a named-id D36 plan avoids.
- RIDERS: (a) COST — the named-id N=32 compile cost $0.397, ~2.9x the 1b median $0.1376 (133 assumptions; naming 32 surfaces balloons compile output) -> full coverage at high N is more expensive, which SHARPENS the V2-vs-V2nc cost contrast (V2nc compile = $0). (b) LENS — 66 value-pointer assumptions over 32 surfaces (broad), but per-surface value-lens coverage on the MUTATED shard is confirmed at §9 right-reason qualification, not here.
- Implication: V2/V2nc coverage contrast = EQUAL when compile is faithful (it is); the live contrast is COST (compile $0.40 vs $0), not coverage. R1 residual resolved.

---
## Phase-1c V2-on-benchmark — APPROVED budget (separate capped line items, program budget; the $50 was a per-task pilot guardrail)
- date: 2026-06-29  ·  approved 2026-06-29. Track as SEPARATE capped line items, not one blurred number:
  - LINE ITEM 1 — V2-qualification: cap ~$25 (own cap).
  - LINE ITEM 2 — V2nc ablation arm: cap ~$20.
  - LINE ITEM 3 — CV pilot (S1+V2+V2nc): cap ~$42.
- Spent against these so far: $0 (build not authorized yet). Compile-fidelity check ($0.3969) is a pre-build DETERMINATION, charged to neither.

---
## Phase-1c V2-on-benchmark — PHASE 2 BUILD (world+task+injection+reducer) LOCAL, all checks PASS (BUILD / NOT FROZEN / NOT CONFIRMATORY)
- date: 2026-06-29  ·  LOCAL only, $0 (no Railway, no detection run, no model call). All additions world/task/checker-side; treatment code byte-identical.
- 5 components: (1) world/services/regions.py + conditional registration -> 32 distinct shards, fixed 4-digit, /regions ABSENT on a1-style worlds (existing OpenAPI byte-identical); (2) world/state.py region fixtures (n_regions, default None) deterministic, N-1 byte-identical clean vs injected; (3) world/injections.py single_shard_value_mutation (NEW type) - exactly one surface mutated, N-1 byte-identical, §4 anomaly audit passes, T'!=T; (4) tasks/benchmark_1c.yaml named-id D36 plan names all 32 ids; (5) checkers/benchmark_1c.py reducer+§6 validator - clean PASS, injected N invalid (all GLOBAL_TOTAL_MISMATCH), RECONCILE passes. ALL PASS.
- STRUCTURAL QUALIFICATION N in {8,16,32}: ALL 12 checks pass each (N unique, fixed work, one mutated, N-1 identical, manifest no aggregate §3.1, post-injection consistent §3.2, opaque provenance §4, T'!=T, validator N invalid, all GTM, reconcile §7, anomaly audit §4). ALL N QUALIFIED.
- SUT-NEUTRALITY (hard gate) PASS: sentinel_v2/ + conductor run loops + sessions + sentinel = ZERO changed files (byte-identical). world/{server,state,injections}.py = ADDITIVE-only benchmark hunks (matcher/middleware/existing injections untouched); regions registered conditionally on n_regions (same discipline as rev-2 meta router). D35 executor knob NOT touched (deferred to phase 3); D36 = task-YAML input (no code). artifact runs/matrix_1c/sut_neutrality_diff.json.

---
## Phase-1c V2-on-benchmark PHASE 3 — D35 knob (SUT-neutral PASS) + §3.5 information-boundary audit (single-shard HOLDS) (BUILD / NOT FROZEN / NOT CONFIRMATORY)
- date: 2026-06-29  ·  LOCAL only, $0 (no model call, no Railway, no detection run).
- PART A D35: run_one.py:953 max_workers=4 -> max_workers=int(self.task.get('executor_width',4)); default 4 = 1b byte-identical; benchmark executor_width=32. SUT-NEUTRALITY DIFF PASS: git shows run_one.py changed ONLY the executor-width line (+comment), no other code line; sentinel_v2/=0, sentinel/=0, sessions.py=0, run_v2_loop.py=0 changed. D35 changes ONLY the concurrency parameter. artifact runs/matrix_1c/sut_neutrality_diff.json.
- PART B §3.5 audit (static, frozen system): baselines sealed in conductor self.v2_baselines (run_v2_loop.py:86). EXHAUSTIVE runtime readers = run_v2_detection (MATCHER, per-surface diff, no Σ) + evaluate_write_footprint (matcher-side, per-surface). Compiler/workers/orchestrator/prompts NEVER receive baseline values (verified: compile gets plan+context+side-channel fresh reads; worker.md/orchestrator.md/v2_compile.md have no baselines). Matcher has NO cross-surface aggregate operator. VERDICT: NO aggregate baseline-T computable outside the matcher -> §3.5a+§3.5b satisfied -> SINGLE-SHARD CLAIM HOLDS. No SUT modified. artifact runs/matrix_1c/information_boundary_audit.json.

---
## Phase-1c V2-on-benchmark PHASE 4 — restructured plan to D36 WIDTH-SCALED form + re-qualified (BUILD / NOT FROZEN / NOT CONFIRMATORY)
- date: 2026-06-29  ·  LOCAL, task/plan-side only. spend $0.1953 (ONE real Sonnet compile for the fidelity re-check); treatment code byte-identical.
- STEP 1: tasks/benchmark_1c.yaml restructured from 4 named-id steps -> 32 ONE-SHARD worker steps (fixed work/worker, total grows with N), all 32 ids named, fan_out=executor_width=n_regions=32, shared-denominator reduce + §6 validator kept.
- STEP 2: structural qualification RE-RUN on the width-scaled form at N in {8,16,32} -> ALL 12 checks pass each; wound lands (single mutated shard -> validator exactly N invalid, all GLOBAL_TOTAL_MISMATCH). Re-verified on the new form, not inherited.
- STEP 3 compile-fidelity RE-CHECK (real Sonnet on the 32 one-shard named plan): 131 assumptions, 32 distinct concrete ids, ZERO templates, grounding modes {concrete:128} -> DISTINCT surfaces ARMED = 32/32 = FULL (structure-robust). 32 value-pointer assumptions (exactly ONE per surface -> every surface gets a value baseline-diff lens; cleaner than the 4-step form's 66 spread). COST $0.195 — ~HALF the 4-step form's $0.397 and only ~1.4x the 1b median $0.1376 (the width-scaled form compiles CHEAPER, not more; softens the high-N compile-cost concern). Coverage did NOT degrade vs the 4-step form.
- STEP 4 SUT-neutrality re-confirm: sentinel_v2/=0, sentinel/=0, sessions.py=0, run_v2_loop.py=0 changed; only conductor change = the phase-3 D35 knob (0 non-D35 lines); restructure touched ONLY tasks/benchmark_1c.yaml. Byte-neutral.

---
## Phase-1c V2-on-benchmark — GROUNDING-MISMATCH CHARACTERIZATION (CHARACTERIZATION / NOT FROZEN, no build/spend)
- date: 2026-06-29  ·  static code-read only, $0. V2 grounds via path_samples_for_rev/openapi_paths_for_rev (world_rev-keyed, fixed app no n_regions, instantiation hardcoded to {sku}/{passage_id}/{path}). Benchmark /regions not in the sample set -> GroundingError. Phase-4 fidelity 32/32 was vs SYNTHETIC samples = INVALID for real grounding (currently FAILS).
- Q1 (no-touch route?): NO. Grounding sample source is world_rev-keyed (pattern_liveness.py:45, surface_appendix.py:39); per-task mechanism is SELECTION (services_touched filter) not ADDITION. No way to present /regions to grounding without modifying path_samples_for_rev/openapi_paths_for_rev.
- Q2 (visibility vs behavior): VISIBILITY-ONLY (additive). Fix = build sample-app with n_regions + add {region_id} instantiation branch; n_regions=None default -> existing tasks BYTE-IDENTICAL (router conditional, branch dormant, classify/ground/cap untouched). Only adds /regions samples when n_regions set. NOT behavior change.
- Q3 (finding?): BOTH. The fix is clean additive (NOT §3.6 surgery). BUT the need for it exposes a real architectural property -> CANDIDATE FINDING: plan-compiled monitoring's grounding assumes a fixed/small/enumerable per-world-rev surface topology (hardcoded {sku}6/{passage}6/{path}8, cap 24); width-scaled (variable-N, N=32>cap) surface families fall outside it and require parameterizing the sample-derivation. The width-scaled benchmark exposed it. artifact runs/matrix_1c/grounding_mismatch_characterization.json.

---
## Phase-1c V2-on-benchmark — GROUNDING FIX BUILT + REAL-PATH FIDELITY RE-MEASURE (BUILD/CHARACTERIZATION / NOT FROZEN / NOT CONFIRMATORY)
- date: 2026-06-29  ·  LOCAL. spend $0.75019 = TWO real Sonnet compiles ($0.358834 + $0.391356). Authorized clean-additive grounding fix (characterization option a), then re-measure compile fidelity on the REAL grounding path. Burned seeds. Railway not needed (local compile). No confirmatory artifact touched.
- STEP 1 — ADDITIVE GROUNDING FIX BUILT: threaded `n_regions` (default None) through path_samples_for_rev (pattern_liveness.py, +lru_cache 8->16) / openapi_paths_for_rev (surface_appendix.py) / compile_pipeline (compile_probes.py) / compile_and_arm (run_v2_loop.py), and added a dormant `{region_id}` instantiation branch alongside {sku}/{passage_id}/{path}. So the deterministic grounding's sample-derivation can SEE the benchmark_1c /regions surfaces.
- STEP 1 HARD GATE — SUT-NEUTRALITY: PASS (byte-neutral). classify_url_pattern (world.server, imported), ground_surface (compile_probes.py:192-230), _instantiate (:165-170), FAMILY_MEMBER_CAP=24 (:162) ALL byte-identical. Default n_regions=None -> regions router off + region_order empty + {region_id} branch dormant -> existing-task samples byte-identical (empirical: n_regions=None -> 0 /regions surfaces, existing byte-identical; n_regions=32 -> only the 33 /regions added = 1 list + 32 evidence). VISIBILITY-ONLY; NOT §3.6 surgery (no existing-surface logic weakened/re-sealed). Record: runs/matrix_1c/sut_neutrality_diff.json grounding_fix block.
- STEP 2 — REAL-PATH FIDELITY RE-MEASURE (supersedes the RETRACTED synthetic 32/32 logged above): ONE real Sonnet compile -> compile_pipeline(world_rev=4, n_regions=32, world=None). 32/32 /regions GROUND (no GroundingError, 0 hallucinated), 32/32 ARM, 32/32 carry a per-surface VALUE baseline-diff probe (value_changed/field_read/proof_baseline). Cap does NOT bite. Mutated shard R-0003 (/regions/R-0003/evidence) IS covered by a value lens. Histogram of the 32 armed surfaces: (schema_shape,schema_fingerprint,proof_baseline)x128 + (value_changed,field_read,proof_baseline)x96 -> every surface gets BOTH a structure probe AND >=1 value probe. The single-shard demand swap is OBSERVABLE on the real grounding path. Artifact: runs/matrix_1c/fidelity_realpath.json; script analysis/benchmark_1c_fidelity_realpath.py.
- WHY CAP DOESN'T BITE AT N=32 (fragility note, finding STANDS): the plan names all 32 ids concretely -> grounding takes the UNCAPPED plan_named branch (ground_surface:215-217), not the capped all_bounded branch (:218). A bare-template (generic-naming) plan would cap at 24/32, overflow -> UNCOVERED_CAUTION. Coverage at N>24 depends on the plan naming the ids — exactly the D32 plan-named-grounding mechanism (cross-ref the R1 24-cap finding). The additive fix makes surfaces visible; it does NOT raise the cap.
- MEASUREMENT-BUG (NOT a qualification finding): the FIRST re-measure reported a FALSE 0/32 value-lens coverage — the harness check searched the comparison enum for "BASELINE_DRIFT", a string that does NOT exist in probe_spec.py (the two Comparison members are HARD_INVARIANT and PROOF_BASELINE; the baseline-drift comparison is PROOF_BASELINE). Compile #1's grounded (32/32) and armed (32/32) numbers were VALID; only its value-lens SUB-count was mis-measured. Corrected the check (FaultShape.VALUE_CHANGED + LensOp.FIELD_READ + Comparison.PROOF_BASELINE) + added a self-evidencing shape histogram, re-ran ONE compile. The re-run was a measurement-check fix, NOT a treatment-code change. Soft-assumption count differed across the two compiles (162 vs 228) — ordinary LLM sampling non-determinism; both grounded 32/32.
- STEP 3 — FINDING LOGGED: the fixed-topology architectural finding (Q3) + the resolved real-path coverage recorded in runs/matrix_1c/grounding_mismatch_characterization.json (RESOLVED_real_path_coverage block) and runs/matrix_1c/fidelity_realpath.json.
- GATE STATE: coverage number is GO for the next phase (V2 + V2nc right-reason qualification). V2nc NOT built and NO detection run this phase, per brief.

---
## Phase-1c V2-on-benchmark — V2nc BUILD + V2/V2nc §9 RIGHT-REASON QUALIFICATION (QUALIFICATION / NOT FROZEN / NOT CONFIRMATORY)
- date: 2026-06-29  ·  LOCAL graded run, burned seeds. spend $16.34 measured (+ ~$0.39 sunk on a checker-path crash) ≈ $16.7, under the $25 HARD CAP (estimate printed before each detection batch). Proves DETECTION right-reason, not coverage (coverage settled: 32/32 grounded+armed+value-lens).
- STEP 0 — V2nc ARM BUILT + SUT-neutrality PASS: new sentinel_v2/deterministic_select.py (enumerates one VALUE soft assumption per plan-touched /regions surface, pointer=normalized_verified_demand, $0/no model); additive ArmSpec V2nc (kind v2, role 'ablation', deterministic_select=True) + dispatch passthrough (arms.py); one else-branch in V2Conductor.compile_and_arm (run_v2_loop.py) — the ONLY V2-vs-V2nc difference is the soft-set SOURCE, everything downstream byte-identical. V2's compiler/matcher/probe/side-channel BYTE-IDENTICAL (compile_probes.py, prompts, world/server matcher, probes/probe_spec/attachment/corroboration untouched; sha256 recorded in runs/matrix_1c/v2nc_sut_neutrality.json). Plus two ADDITIVE behavior-neutral observability fields (escalation.fault_shape/evidence_class + tripwire_set.probes[] shape) so the trace artifact alone proves which lens fired. V2nc deterministic coverage (no LLM): N∈{8,16,32} → N/N value baseline-diff probes, mutated shard covered, cap not consulted (concrete surfaces). Suite 417/417 flag off+on; banked byte-identity 27/27 both flag states.
- STEP 1 — INTEGRATION (first conductor end-to-end on this task; 4 bugs found+fixed, ALL world/task-side, none treatment): (1) checker path checkers/→tasks/checkers/benchmark_1c.py (_load_checker resolves REPO_ROOT/tasks/<rel>); (2) /admin/ground_truth returns n/seed when n_regions set (admin-path, additive, conditional); (3) goal/aggregate reframed to a COLLECTION task (orchestrator collects per-region records; the prior exact-rational-math instruction returned final_report=null); (4) checker does the DETERMINISTIC reduce from collected demands + §6-validate vs canonical clean (clean→all-N valid; one mutated shard→all-N GLOBAL_TOTAL_MISMATCH). Re-confirmed SUT-neutral after fixes: suite 417/417 both flags, byte-identity 27/27.
- STEP 2 — §9 GRADED MATRIX (18 graded cells, 0 failures): V2 QUALIFIES at measured N∈{8,16} (2 seeds), V2nc QUALIFIES at N∈{8,16,32} (2 seeds N≤16, 1 seed N=32). EVERY injected cell trace-confirmed: the value baseline-diff probe (value_changed/field_read/proof_baseline) ARMED + FIRED (grade=interrupt) on the MUTATED shard, injection@counter2 > arm-baseline@counter1 (clean baseline), numerical all-N wound (GLOBAL_TOTAL_MISMATCH). 9/9 clean cells QUIET+valid. Mutated shards vary by seed (R-0004/R-0014/R-0016/R-0003) — injection-blind selection covers different shards. n_inject=2 fires at the first worker curl (token POST is counter-advancing, /auth/token not excluded; arm-time baseline is side-channel/counter-neutral → clean).
- THE ONE ANOMALY (three-way classified) — V2 N=32 = (i) INTEGRATION BUG, NOT a right-reason failure: WinError 206 (Windows command-line length limit) — sessions.py:256 passes the rendered system prompt as --system-prompt <arg>; at N=32 the ORCHESTRATOR-generated plan (32 verbose worker steps) + 33-surface appendix exceeds Windows' ~32KB arg limit. Crash at subprocess launch → $0 spent. Non-reproducing on Linux (ARG_MAX ~2MB); V2nc N=32 immune (no LLM compile). NOT patched (shared LLM-invocation layer, §3.6-adjacent, out of scope) — DEFERRED to the prepared Railway MODE=qual run. This is the ONE cell where the local-vs-Railway venue bites, validating the platform-parity mandate. (The earlier $0.39 N=32 fidelity compile succeeded because it used the TERSE yaml plan, not the verbose orchestrator plan.)
- DEVIATION FLAG (prominent): graded §9 ran LOCAL CLI 2.1.193 / Windows, NOT Railway-Linux/2.1.177 — authorized (Option 3): §9 detection right-reason is OS/version-invariant (curl-gated worker; OS tool-delta non-executable; version only affects 1b-comparability which qualification doesn't touch). Platform parity REQUIRED for the CV pilot + confirmatory; the deferred V2 N=32 cell belongs to that run. Railway MODE=qual entrypoint branch PREPARED (deploy/railway/entrypoint.sh), NOT deployed.
- REALIZED FAN-OUT observation: clean cells fan-out=N; injected cells can re-provision above N on the replan re-dispatch (V2nc N=16→22, N=32→61) — orchestrator regenerates the plan on replan; detection unaffected.
- Artifacts: scripts analysis/{benchmark_1c_v2_qual.py (resume-safe harness), benchmark_1c_v2_qual_report.py, v2nc_build_check.py}; tests tests/{test_v2nc_deterministic_select.py, test_arms.py updated}; records runs/matrix_1c/v2_qualification/{cells.jsonl, verdict.json, QUALIFICATION_SUMMARY.md, v2nc_sut_neutrality.json}; traces runs/matrix_1c/v2_qual_runs/. NOT frozen, NOT confirmatory, NOT the CV pilot.

---
## Phase-1c V2-on-benchmark — V2 N=32 DEFERRED CELL CLOSED ON RAILWAY-LINUX/2.1.177 (QUALIFICATION / NOT FROZEN / NOT CONFIRMATORY)
- date: 2026-06-29  ·  Railway-Linux graded run (first real V2-on-Railway-Linux, de-risks the CV pilot path). spend $4.5427 (clean $1.914 + injected $2.629), under the $10 HARD CAP (entrypoint prints estimate + aborts if over; projected $2.98). burned seed 9132.
- CONTEXT: the local §9 left ONE gap — V2 N=32 crashed locally with WinError 206 (Windows command-line length limit on --system-prompt; the verbose orchestrator plan + 33-surface appendix overflow). Classified (i) integration bug, deferred to the prepared Railway MODE=qual run. This run closes it.
- DEPLOY: railway up to the existing tw-b2-probe service (Dockerfile pin 2.1.177, /data volume, restart=NEVER, RAILWAY_RUN_UID=0, ANTHROPIC_API_KEY service var). In-container gate: claude 2.1.177 PASS; /data persistence PASS (VOLUME SURVIVED REDEPLOY). Two deploy WRINKLES found+fixed (pilot-relevant, the point of running now): (1) railway.toml must be at the build-context ROOT — Railway ignored deploy/railway/railway.toml and fell back to Railpack (build FAILED) → added root railway.toml forcing the Dockerfile builder; (2) Dockerfile hardcoded `fastapi uvicorn psutil`, missing httpx + PyYAML → ModuleNotFoundError at run ($0 spent) → fixed to `pip install -r requirements.txt`; entrypoint cost-guard hardened to abort if the estimate produces no number (fail-safe).
- RESULT — V2 N=32 on Linux: (a) LAUNCHED CLEAN, no WinError 206 (the Windows-only crash confirmed Windows-only). (b) clean → success=True (all 32 packages valid, T=166407), 0 interrupts, fanout=32. (c) injected → RIGHT-REASON trace-confirmed: injection_fired@counter2 (R-0003 4415→4812), arm_baseline@counter1 (<injection), escalation value_changed/interrupt on /regions/R-0003/evidence @counter96, armed value lens value_changed/field_read/proof_baseline on the mutated shard, success=False "32/32 invalid (T'=166804 vs T=166407) GLOBAL_TOTAL_MISMATCH", fanout=32, 1 interrupt/1 replan.
- VERDICT NOW COMPLETE: V2 QUALIFIES at N∈{8,16,32}; V2nc QUALIFIES at N∈{8,16,32}. The §9 right-reason qualification table is closed across all three widths for BOTH arms. The WinError deferral is SUPERSEDED (treatment code never patched — the fix was the venue, exactly as predicted).
- CUSTODY: durable records on /data (cells.jsonl + traces under /data/v2_qual_runs/V2/n32/); the 2 V2 N=32 cell records + full trace evidence reconstructed into the repo (runs/matrix_1c/v2_qualification/{cells.jsonl platform-tagged railway-linux/claude-2.1.177, cells_railway_n32.jsonl, QUALIFICATION_SUMMARY.md, verdict.json}); 2 superseded WinError records dropped (backed up cells.local-only.bak.jsonl). Service torn down after the one-shot. Deploy artifacts: root railway.toml (NEW), deploy/railway/{Dockerfile -r requirements.txt, entrypoint.sh MODE=qual hardened}.

---
## Phase-1c — NET-COST CV PILOT (S1+V2+V2nc) on benchmark_1c, FROZEN blind resize applied SIGN-BLIND (PILOT / NOT FROZEN / NOT CONFIRMATORY)
- date: 2026-06-29  ·  Railway-Linux / claude 2.1.177 (platform parity REQUIRED — feeds the confirmatory design). burned fresh seeds (N=8: 7101-7105; N=32: 7201-7203; unused in qual 9132/9133 or s1_qual 9101-9103). MEASUREMENT run — treatment code BYTE-IDENTICAL (no arm/compiler/matcher/probe change).
- DESIGN (logged as the PILOT design; scope-doc §6 was a rough estimate not a frozen commitment): arms S1+V2+V2nc (scope §7.6); primary N=8 x5 seeds + spot-check N=32 x3 seeds; both conditions. n_inject=2.
- DEPLOY: MODE=pilot to tw-b2-probe (proven path: root railway.toml + Dockerfile `-r requirements.txt`). claude 2.1.177 hard-gated PASS; /data persistence PASS. Estimate $43.36 < $50 cap PRINTED before spend; budget guard armed (trim N=32 first, preserve N=8) — never tripped.
- SPEND: Anthropic $38.09 (N=8 $11.47 + N=32 $26.62), under the $50 HARD CAP. Railway one-shot (no idle billing).
- QUALITY FLOOR Q(N) MET (V2 & V2nc): clean-success 5/5 & 3/3 ALL arms; injected-wound 100%; V2/V2nc detected 100% + recovered (detect-and-replan) 100%; S1 0 detection (baseline); realized fanout=N every cell; KG0 holds (clean S1 pass / injected S1 wounded both widths). So the CV is of the QUALITY-QUALIFIED net cost.
- CV (product) — estimand B_p(N)=(1-p)D0+p D1, primary S1-V2: N=8 (5 seeds) D0=-$0.144 D1=-$0.676 worst-case p=0.50 SD=$0.1029 CV=0.251; N=32 (3 seeds) D0=-$0.954 D1=-$2.541 worst-case p=0.50 SD=$0.2672 CV=0.153. Secondary S1-V2nc: N=8 SD=$0.0614, N=32 SD=$0.2497.
- RESIZE (frozen formula n=max(5,ceil((1.645*SD/H)^2)), H=$0.015, SIGN-BLIND from SD only): per-width n(S1-V2) {N=8:128, N=32:859}. **BINDING-WIDTH n=859** (from N=32). S1-V2nc {N=8:46, N=32:750}. POINT ESTIMATE (NON-DETERMINATIVE, not used for n): mean B_p<0 at every N,p (N=8 p=.5 -$0.41; N=32 p=.5 -$1.75) -> V2 looks COSTLIER than S1 (E4: sign excluded from n). Economic note: V2 injected $3.40 vs V2nc $1.11 at N=32 — compiler recompile-on-replan ~$2.3/cell; V2nc near cost-neutral clean.
- **FREEZE-DECISION INPUT (STOP for author, no silent truncation):** implied confirmatory at n=859 = grid{1,3,8,16,32,64} x {S1,V2,V2nc} x {clean,injected} = 36 cells/seed x 859 = 30,924 cells ~= $29,729 vs B=$450 -> ~66x OVER. n-wanted=859 vs n-affordable(<=B)~=13. H=$0.015 is far tighter than the measured per-seed cost SD (~$0.10 N=8 / ~$0.27 N=32) -> formula demands hundreds of seeds. The confirmatory as specified (H, full grid, 3 arms) is unaffordable by ~10-66x; author must decide (relax H / shrink grid / wider CI / re-scope). CAVEAT: N=32 n=859 rests on 3 seeds (noisy); N=8 n=128 (5 seeds) more reliable but still ~$4.4K (~10x over $450).
- CUSTODY: runs/matrix_1c/cv_pilot/{cells.jsonl (reconstructed from run logs), cv_result.json, CV_PILOT_SUMMARY.md}; full traces durable on /data volume /data/cv_pilot/. Scripts analysis/{benchmark_1c_cv_pilot.py, benchmark_1c_cv_compute.py}; deploy/railway/entrypoint.sh MODE=pilot. Service TORN DOWN (deployments removed, MODE reset). NOTHING FROZEN/hash-pinned — the freeze is the separate next step.

---
## Phase-1c — CV-RESIZE AUDIT (is n=859 real or artifact?) (AUDIT / NOT FROZEN / NOT CONFIRMATORY, $0)
- date: 2026-06-29  ·  code-read + re-compute on banked cv_pilot/cells.jsonl ONLY; no run/deploy/spend; no confirmatory artifact touched. Script analysis/cv_resize_audit.py; report runs/matrix_1c/cv_pilot/CV_RESIZE_AUDIT.md.
- Q1 formula reproduces EXACTLY (no bug): n=max(5,ceil((1.645*SD/0.015)^2)). N=8: 1.645*0.10292/0.015=11.287 ->^2=127.39 ->ceil 128 ✓. N=32: SD 0.26723 -> 859 ✓. Units clean: SD and H both in $ (B_p is a $ diff) -> Z*SD/H dimensionless; no cents/$ mismatch; Z=1.645 one-sided 95%.
- Q2 SD is per-seed PAIRED (D0[s]=K0_S1[s]-K0_V2[s], D1 likewise, same seed; B_p assembled per seed before st.stdev ddof=1). Independent recompute: N=8 SD=$0.1029 (5 seeds), N=32 SD=$0.2672 (3 seeds) — match cv_result.json. Not pooled/unpaired.
- Q3 N=32 LEAVE-ONE-OUT: drop 7201->n=116, drop 7202->n=1438, drop 7203->n=1120 (full 859). LOO range [116,1438], swing 1322 -> **n=859 IS a 3-seed artifact** (seed 7201 V2-inj $3.98 outlier dominates). N=8 LOO [97,170] swing 73 -> n=128 is the stable/trustworthy anchor.
- Q4 HONEST FLOOR (N=8 5-seed SD, H=$0.015): n=128 -> implied confirmatory ~$4,430 (~10x over $450); n-affordable~13; H that fits B from N=8 SD ~ $0.047 (~3x looser). 
- CONCLUSION: not a code bug. n=859 is small-sample noise -> use n=128. But even n=128 is ~10x over budget -> H=$0.015 too tight for ~10-27c per-seed cost noise. Freeze decision = relax H / shrink grid-arms / wider CI / re-scope; the $30K figure should be reported as the (artifact-inflated) ceiling and the ~$4.4K (n=128) as the honest floor. Nothing frozen.

---
## Phase-1b — DEPENDENCY_VERSION §7 CLAIM VERIFICATION (ARCHAEOLOGY / VERIFICATION / NOT FROZEN / NOT CONFIRMATORY, $0)
- date: 2026-06-29  ·  read-only over 20 banked DV cells (runs/matrix_1b/runs/b1-{S1,S2,S3,V2}-silent_minor_bump-s{2088,2505,3191,3741,7101}); no run/deploy/spend; no treatment code or confirmatory artifact touched. Script analysis/dv_claim_verify.py; report runs/matrix_1b/dv_claim_verification.md.
- VERDICT: the §7 (fse_draft4.md:272) CENTRAL mechanism claim is **REFUTED** — the paper OVERCLAIMS. Q1: V2 DID arm /repo/files + record an arm-time baseline (✓) BUT it is NOT clean — DV fires at n_inject=1 (the /auth/token POST at counter 1), which PRECEDES V2's arm-time side-channel capture, so the baseline already shows the truncated page (files=3/5/6 = page_size_to) not the clean 8. So the miss IS information-bounded for V2, the OPPOSITE of "captured clean baseline, not information-bounded." Q2 CONFIRMED: 0 version tokens in any observed payload. Q3 REFUTED/misframed: bare /repo/files reads byte-identical to baseline on ALL 5 (not "most") because the baseline is dirty; "lone s2505 5→3" is wrong (s2505 page_size_to=5; its 5→3 is ordinary pagination of a page-size-5 listing, not a truncation; no seed surfaces a truncation vs its baseline). Q4 REFUTED: /repo/files WAS re-read post-worker 2-6x every seed (diffed vs dirty baseline -> no change); "never re-diffed /repo/files" false. Q5 CONFIRMED 0/5 all arms; PARTIAL on S2 — S2's lone escalation (s2088, fir=1.0) is a false interrupt on /repo/validate reference anomaly, not the truncation.
- FRAMING: "harness-wide 0/5 miss" survives (all 20 detected=False; passive arms + naive S2 have no error/status signal for a silent status-200 shorter listing — Q2). But "detection/benchmark limit, NOT v2-specific" does NOT survive as stated: V2's miss is information-bounded by injection-timing (arm-time baseline can't precede a counter-1 injection) — a real v2-relevant cause entangled with the n_inject=1 benchmark choice. Clean /repo/files = 8 files; truncation 8->3/5/6 real; a clean baseline WOULD have a diff to test (lens permitting). Corrected §7 sentence proposed in the report. NOT a detection fix (§3.6) — a paper-framing-accuracy finding for author decision.
