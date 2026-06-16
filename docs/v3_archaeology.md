# v3 Archaeology — Cost Autopsy of the 1b Confirmatory FAIL

**Date:** 2026-06-16. **Status:** exploratory, post-verdict, READ-ONLY. **Scope:** attribute
the KG3 overhead, decompose the KG4 waste + TTD, and explain the KG2 clean-success gap, to give
v3 a concrete cost target. **No verdict change.**

This analysis re-runs no cell, mutates no ledger/trace/gate report, and does not recompute the
verdict (which remains **FAIL**, frozen in `runs/matrix_1b/gate_report_final.json`). All numbers
come from the ledger (`runs/matrix_1b/results.jsonl`, 172 rows), the per-cell event traces
(`runs/matrix_1b/runs/<cell>/trace.jsonl`), and the gate report. Recomputation harness:
`analysis/v3_autopsy_scratch.py` (standalone, not imported by the suite). Every aggregate below
reconciles **exactly** with `gate_report_final.json` (cross-check table at the end).

## Method note — where the cost lives

The ledger row carries only `total_cost_usd` (it cannot itemise). The per-cell trace **can**:
every event carries `usage.cost_usd`, and `sum(usage.cost_usd) == run_end.cost_usd ==
ledger total_cost_usd` (verified on every cell — the join key). Bucketing each event's cost by
`event_type` across all 172 traces shows that **only five event types ever carry cost**:
`plan`, `compile`, `worker_end`, `aggregate`, `replan` — all real Sonnet (`claude-sonnet-4-6`)
calls. The entire detection substrate — `corroboration` (probe firing), `tripwire_set` (arming),
`interrupt`, `suppressed_refire`, the D29 cadence/pre-completion sweeps, the D30 arm-time sweep —
**carries no `usage` and costs $0** (deterministic substrate reads, no LLM). S1 traces contain
**no `compile` and no `corroboration`/`tripwire_set`** at all. This single fact drives the whole
autopsy: **V2's only net-new dollar component over the baselines is the `compile` LLM call**
(`sentinel_v2/compile_probes.py:108`), plus its repetition as `replan` recompiles on injected
runs (`conductor/run_v2_loop.py:506`).

---

## G3 — KG3 clean-cell overhead attribution (FAIL: 55.49% vs 12% cap)

KG3 is computed over the **12 clean cells per arm**; every V2 clean cell has `replans == 0`
(verified) so there is **no recompile cost** in the clean number.

| Bucket (median over 12 clean) | V2 | S1 | net |
|---|---|---|---|
| plan (orchestrator) | $0.0526 | $0.0651 | ~wash |
| **compile (sentinel, V2-only)** | **$0.1376** | **$0.0000** | **+$0.1376** |
| worker_end | $0.1110 | $0.1257 | ~wash |
| aggregate | $0.0397 | $0.0566 | ~wash |
| replan | $0.0000 | $0.0000 | 0 |
| **total** | **$0.36424** | **$0.234246** | **+$0.1300 (55.49%)** |

The V2−S1 clean delta is **$0.130**, and the V2 `compile` bucket alone is **$0.1376** — i.e.
the overhead **is** the compile call (plan/worker/aggregate are statistical washes between arms;
the arm-time sweep and cadence are $0). `compile` is present in **12/12** V2 clean cells.

- **FIXED vs VARIABLE.** On clean, the overhead is **~100% FIXED**: one bounded compile LLM call
  per run (`compile_probes.py:108`, MAX_ATTEMPTS=2), plus the arm-time sweep at $0
  (`run_v2_loop.py:181`). The VARIABLE components (cadence/pre-completion sweep — $0; per-replan
  recompiles — only on injected cells) contribute **$0** to KG3.
- **Probes ARMED vs exercised (the D32 family-arming breadth).** Armed = `tripwire_set.count`;
  exercised ≈ arm-time `probed` + pre-completion `swept`. The arm step over-provisions, most
  visibly on the families:

  | V2 set | armed | unique targets | arm-sweep probed | pre-compl. swept | interrupts |
  |---|---|---|---|---|---|
  | clean (med) | 18.5 | 13.5 | 13.5 | 2 | 0 |
  | injected (med) | 22 | 19 | 19 | 2 | 1 |

  Per injected category (armed vs arm-probed): **API_SURFACE 35→19**, SCHEMA_DRIFT 28→22,
  TOOL_CONTRACT 19→19, PERMISSION_AUTH 18→12.5, RETRIEVAL_INTEGRITY 15→9. D32 arms the full
  bounded family (cap 24) but only worker-touched / load-bearing surfaces are ever exercised —
  **armed ≫ exercised, most on API_SURFACE.** This is **$0 in the deterministic mock** (substrate)
  but is the real token/latency lever once the substrate is a live model.
- **Injected-cell cost blowup (context — not gated by KG3, but the same driver).** Median total
  on injected: **V2 $0.5711 vs S1 $0.3408 vs S3 $0.1898**. The V2 excess is again the LLM
  bookends: compile bucket **$0.2267** (median **2** compile events = initial + one
  **recompile-per-replan**) plus replan bucket $0.0456. So the compile call is paid **once** on a
  clean run (→KG3) and **~2×** on an injected run.

**Dominant driver: the once-per-run `compile` LLM call** (paid again on each replan).

---

## G4 — KG4 waste + TTD decomposition (PENDING; waste 1.0943 > 1.0, TTD unevaluable)

KG4 is computed over **all non-clean cells (injected + holdout = 31/arm)** — the brief's "S3
inert 0/31". (Injected-only the V2 median is 6282; the gate's 7008 includes the 3 detected
`quota_cliff` holdout cells, which also account for `n_detections` 21→24.)

- **Headline.** V2 non-clean wasted-tokens median **7008** vs S3 **6404** → **ratio 1.0943**
  (matches gate). Only a **9.4% excess**.
- **Monitoring overhead = $0 / 0 tokens.** The probe substrate carries no `usage`, so **none** of
  V2's waste is monitoring tokens — it is **100% discarded worker/orchestration tokens**, the same
  *kind* of waste S3 incurs. The excess is purely the cost of V2 *acting* on a detection
  (discarding in-flight work and replanning) where S3 does nothing.
- **The excess is small and concentrated.** Median `discarded_workers` is **0** (23/31 cells
  discard nothing); only **8/31** cells discard ≥1 worker. Waste median **with** discard = 7291.5
  vs **without** = 6495 — the discard adds ~800 tokens on a minority of cells.
- **Waste does NOT scale with detection latency or replans.** Pearson over the 31 cells:
  `corr(ttd, waste) = 0.007`, `corr(replans, waste) = -0.06`, `corr(discarded_workers, waste) =
  0.05` (detected-only subset: same, ~0). Waste is essentially flat in TTD and replan count.
- **TTD distribution.** 24 V2 detections; **14 carry a tool-call TTD** (median **9.5**, = gate),
  the other **10 detect via the status fast-path with null TTD**. TTD values:
  `[1, 4, 4, 5, 6, 8, 9, 10, 11, 13, 14, 14, 18, 18]`. **S3 detects 0/31**, so its TTD median is
  null and the TTD ratio is undefined → **KG4 is PENDING on the TTD gate**; the waste gate fails
  on the 1.0943 parity.
- **KG3↔KG4 tradeoff (from the run's own data).** Because waste is **uncorrelated with TTD**
  (corr ≈ 0), sweeping more frequently to cut detection latency would **not** reduce waste — it
  would only add compile/probe overhead and **worsen KG3**. The KG3↔KG4 tradeoff is therefore
  **adverse, not favourable**: there is no waste to "buy back" with earlier detection. The waste
  lever is orthogonal to sweep frequency — reduce the *per-discard* loss (pause only the affected
  worker / salvage partial outputs instead of discarding the wave), since the discard is what
  pushes the 8 heavy cells over parity.

---

## G2 — KG2 clean-success gap + FIR-0 robustness (PASS)

- **The gap is one cell, on different cells, with zero interrupts.** V2 clean success **8/12
  (66.7%)** vs S1 **9/12 (75%)**; KG2 PASSES the floor (≥60% and ≥ S1−10pp). All four V2 clean
  failures have **`n_interrupts == 0`** → the gap is **not** monitoring/false-positive
  interference. Reading each failing cell's `run_end`:

  | V2 clean fail | reason | run_end detail |
  |---|---|---|
  | c1 slot1 | (none) | `package_id None is not a non-empty string` |
  | c1 slot2 | (none) | `brief.warehouses: does not reflect the three operational warehouses premise` |
  | d1 slot1 | (none) | `title None …; citations is not a non-empty list of passage ids` |
  | d1 slot3 | (none) | `title None …; citations is not a non-empty list of passage ids` |

  All are **output-schema/quality validation failures** with `reason == None` — no
  `escalation_loop`, no budget cap, and mid-range cost ($0.36–0.48, nowhere near the ~$0.84 tail).
  So: **not budget/overhead exhaustion, not monitoring interference** — **unrelated
  task-completion variance** on the strict report-assembly tasks (c1/d1). S1 fails on a *different*
  set (b1-s2, d1-s1, d1-s2); both arms only share d1-s1. The sets differ and the net difference is
  one cell → not a systematic V2 regression, well within N=12 noise.
- **FIR-0 robustness — the win is real, not an easy set.** The clean set **includes the b1 cells**
  — the legitimate `settings.yaml`-migration **write** that previously false-positived as
  `value_changed` and motivated D31. Post-D31, V2 runs all three b1 clean cells at **0
  interrupts** — the FP-prone write surface was exercised and the D31 write-footprint policy held.
  And the clean set is not trivially quiet: the naive-escalation arm **S2 false-fired on 4 clean
  cells** (a1 s1/s2/s3, d1-s1; FIR 1.0), while V2's **total clean false-interrupts = 0**. Clean
  cells can trip a careless monitor; V2's policy did not. **FIR-0 is robust under real FP
  pressure.**

---

## Synthesis — the unifying driver and v3 levers

**One dollar driver, two surfaces.** The verdict-flipping economic failure (KG3) is **monocausal:
the `compile` LLM call** — $0.1376/run, ~the entire 55.49% clean overhead, present in 12/12 clean
cells, with the detection substrate at $0. The same call is the bulk of the injected-cell blowup
(paid ~2× as recompile-per-replan: $0.2267 of V2's $0.5711). **KG4 is a separate, secondary, and
non-compile mechanism** — a 9.4% token-waste excess from *acting* on detections (discarding ≥1
worker on 8/31 cells), uncorrelated with sweep latency or replan count, and **not** fixable by
sweeping more (that only worsens KG3). **The KG2 clean-success gap is orthogonal noise** —
output-validation variance on c1/d1, not cost and not monitoring; the FIR-0 win is robust.

So the picture is **one dominant lever plus two minor ones**, not a single knob:

1. **Cheaper / conditional / cached compile (PRIMARY — fixes KG3).** The probes are nearly free;
   the expense is the LLM that *arms* them. Skip or shrink the compile when the plan/assumptions
   are unchanged, cache compiled tripwires across runs/replans, or template the stable share. A
   compile that costs ≤$0.028 instead of $0.1376 clears the 12% cap outright.
2. **Avoid recompile-on-replan (SECONDARY — injected cost).** Incrementally re-arm on interrupt
   instead of a full recompile each time; this is the same compile lever applied to the ~2×
   injected multiplier.
3. **Probe pruning / baseline amortization (TERTIARY — live-model latency/tokens).** Armed ≫
   exercised (API_SURFACE 35→19); arm only plan-named / likely-touched surfaces. $0 in the mock,
   but the real cost once the substrate runs a model.

> **Mock-floor caveat (real-deployment qualification — added 2026-06-16).** Every "$0 substrate" /
> "near-free probes" / "essentially free" / "weakest lever" statement in this synthesis holds
> **only under the benchmark's free-re-observation assumption** — this is a deterministic mock
> world where probe re-fetches and re-reads cost nothing measured. In a live deployment probes hit
> real endpoints and files at real cost and latency, so (i) the 55.49% overhead is a **lower
> bound**, (ii) probe volume and sweep frequency — free here — re-emerge as real overhead (the
> family-arming over-provisioning, API_SURFACE armed 35 vs 19 exercised, is the canary), and
> (iii) "sweep frequency is the weakest lever" is a mock-world statement, not a deployment one.
> The compile-is-the-only-cost conclusion is a **benchmark-floor** result: a cached/cheaper compile
> does not make the architecture free in deployment. The FSE draft carries this caveat in §10.

**Sweep-frequency tuning is the weakest lever** *(in this mock world — see the mock-floor caveat
above)* — waste is replan/discard-bound and TTD-flat, so faster sweeping buys no waste reduction
and costs KG3. The waste lever, if pursued, is finer-grained interrupt (pause-affected-worker /
salvage), not cadence.

**Central tradeoff:** detection *coverage* vs the *LLM bookends* (compile to arm, replan to act).
The monitoring substrate is essentially free **only under the mock's free-re-observation
assumption** (mock-floor caveat above); v3 should keep the substrate cheap *and design for its
real deployment cost*, and make the LLM bookends cheap and conditional, rather than trading
coverage for cadence.

---

## Cross-check vs `gate_report_final.json` (all exact)

| quantity | recomputed | gate report |
|---|---|---|
| KG3 overhead | 0.554944 | 0.554944 |
| KG4 waste ratio | 1.094316 | 1.094316 |
| V2 / S3 waste median | 7008 / 6404 | 7008 / 6404 |
| V2 TTD median | 9.5 | 9.5 |
| n_detections | 24 | 24 |
| clean success V2 / S1 | 8/12 / 9/12 | 0.6667 / 0.75 |
| verdict (not recomputed) | — | FAIL |

**Provenance / fences honoured:** read-only on the ledger, traces, and gate reports; no SUT /
detection / conductor / `sentinel_v2` / world change; no cell re-run; no ledger modification; the
verdict was neither touched nor recomputed. Only `analysis/v3_autopsy_scratch.py` (read-only,
not suite-imported) and this doc were written. Held-out reads used only public outcome metrics
(the held-out is spent).
