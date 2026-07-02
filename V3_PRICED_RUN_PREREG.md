# V3 PRICED FULL RUN — FROZEN PRE-REGISTRATION

**Status:** FROZEN + USER-CONFIRMED 2026-07-01 before any V3 data exists. This
artifact commits the bar, lever, arms, verdict meanings, and spend cap for the
GPT-5.5 priced-run measurement BEFORE the run. No number below may be changed
after the first run cell executes; deviations are logged, not edited in.

**Confirmed adjustments at freeze:** (1) reasoning fixed at `effort=low` (not
none); (2) workers priced at **real token cost** (list-price reconstruction of
actual token usage) in the overhead ratio — no tier is treated as free.

**Scope discipline (unchanged from the paper):** read-only on experiment-code
core, on V2's frozen pre-registration, and on sealed held-out parameters (never
read or printed). GPT-5.5 enters ONLY as a writer candidate through the existing
`runner=` seam (pinned `gpt-5.5-2026-04-23`, OpenAI Responses API, direct HTTPS
outside Codex). The frozen V2 compile prompt (`prompts/v2_compile.md`) and
few-shot (`prompts/v2_compile_fewshot.json`) files are UNTOUCHED; the V3 coverage
directive (§b) is appended by the harness runner at request time, not written
into any experiment file.

Relationship to prior artifacts: `SCOPING_distill_screen.md` §10 (cost/grounding,
offline) and §11 (fire/transfer, **offline, byte-identical, reproducible**). THIS
run is **LIVE** (real workers, real timing, real money) and its numbers are
reported in a section labelled LIVE, never blended with §11's offline figures.

---

## (a) THE BAR — frozen

**Overhead ratio**, on the **clean-run median** cost basis (identical to the
paper's 55.5% figure, which this pre-reg reproduced from the banked runs:
V2 monitored clean median $0.3642, S1 batch clean median $0.2342 →
(0.3642 − 0.2342)/0.2342 = **55.5%**):

```
overhead = (monitored_median_cost − batch_median_cost) / batch_median_cost
PASS iff overhead ≤ 0.12
```

- `*_median_cost` = the **median over the clean cost cells** (tasks × seeds) of an
  arm's **total run cost**, LLM cost at **list prices**, all tiers summed
  (writer + orchestrator + workers + probe traffic).
- **Cost model, frozen:** Claude tiers priced by the existing
  `conductor/sessions.py::LIST_PRICES_USD_PER_MTOK` (Sonnet orchestrator, Haiku
  workers). GPT-5.5 writer priced at OpenAI list prices **$5.00 / $0.50 / $30.00
  per 1M** (input / cached-input / output), from the actual reported `usage`
  (so warm prompt-cache of the static prefix is counted honestly at $0.50/1M).
- **Denominator is measured LIVE in this run** (a fresh S1 batch arm under the
  same conditions), NOT imported from the paper.
- On clean runs there are no injections → no replans, so overhead ≈
  `writer_cost / batch_worker_cost`. With batch_worker ≈ $0.2342, the bar implies
  a **writer-cost target of ≤ $0.0281/clean-run**. This is the frozen arithmetic
  the coverage lever must move.

## (b) THE LEVER + ARMS — frozen

**Lever = checklist COVERAGE / LENGTH** (assumption count), NOT reasoning effort.
Reasoning was proven detection-free across none/low/medium in §11 (offline), so it
is a FIXED control here, not a varied lever.

- **Reasoning fixed at `reasoning.effort = low`** for every monitored arm
  (user-confirmed; §11 showed detection flat across none/low/medium, and `low`
  gives a small reasoning budget to prioritise which assumptions to keep under a
  tight cap while staying near-min writer cost). It is a FIXED control, identical
  across all coverage arms, so the only varied quantity is coverage.

- **Coverage mechanism (GENERAL, pre-specified, fault-list-BLIND).** A single
  directive appended to the writer's instructions by the harness runner, verbatim
  and identical across all tasks/faults:

  > COVERAGE BUDGET: emit AT MOST N assumptions total. If the plan leans on more
  > than N dependencies, keep the N most LOAD-BEARING — those whose failure would
  > most directly waste or invalidate a plan step's work — and omit the least
  > consequential. Judge ONLY how load-bearing a dependency is (how badly the plan
  > breaks if it is false), NEVER what kind or category of failure it represents.

  It names no fault, category, surface, or mechanism; it ranks by load-bearingness
  only. The writer stays fault-list-blind, same discipline as the whole paper.

- **Coverage settings tested (frozen N):**
  - **full** — N = ∞ (no cap; the §11 behaviour, ~31–35 assumptions).
  - **cap-12** — N = 12.
  - **cap-6** — N = 6.

## (c) THE ARMS TO RUN — frozen

Tasks: the 4 confirmatory archetypes **a1, b1, c1, d1** (benchmark_1c excluded —
non-confirmatory).

**CLEAN cost cells (the overhead ratio):**
| arm | writer | coverage | cells |
|---|---|---|---|
| **B** | none (batch S1, no monitor) | — | 4 tasks × 3 seeds = 12 |
| **M-full** | GPT-5.5 (effort=none) | full | 4 × 3 = 12 |
| **M-12** | GPT-5.5 (effort=none) | cap-12 | 4 × 3 = 12 |
| **M-6** | GPT-5.5 (effort=none) | cap-6 | 4 × 3 = 12 |

**INJECTED detection cells (LIVE fire preserved per coverage), 1 seed each:**
- Seen catchable pairs (9): a1{endpoint_404, schema_drift, token_expiry},
  b1{schema_drift, gate_skip_trap}, c1{doc_contradiction, token_expiry},
  d1{gate_skip_trap, endpoint_404}.
- Held-out (2): RESOURCE_BUDGET = quota_cliff @ a1 (qualified host);
  DEPENDENCY_VERSION = silent_minor_bump @ b1 (qualified host). Held-out params
  are the yaml **qualification defaults** (visible) — **no sealed value is read**.
- 11 cells × 3 coverage settings × 1 seed = **33 injected monitored runs**.

**Total = 48 clean + 33 injected = 81 runs.** Seeds drawn fresh for this run
(disjoint from Phase-1 {1,2,3}, qualification 901+, and escrow namespaces).

## (d) VERDICT MEANINGS — frozen before data

Evaluated against the §a bar and the §c LIVE detection.

- **ESCAPE** — at least one coverage setting clears **overhead ≤ 12%** AND keeps
  **LIVE detection preserved** at that setting: fire on the catchable faults holds
  (defined: the setting's live fire rate on the seen catchable pairs + RB equals
  the M-full setting's live fire rate — no fault lost by the cap).
- **COUPLING CONFIRMED (LIVE)** — detection **degrades** as coverage/cost drops
  (a catchable fault the fuller setting caught is missed at a cheaper setting),
  OR **every** setting stays **above 12%** overhead. A cheaper writer that still
  fails the cap, or whose detection erodes with coverage, is this verdict — a
  real, publishable result, reported at full prominence.
- **INCONCLUSIVE** — the coverage cap did **not** actually reduce coverage/cost
  (achieved assumption count and writer cost do not fall materially across full →
  cap-12 → cap-6) **while** detection is untouched. Guards against a weak attempt
  being read as either verdict. Trigger: median assumption count fails to drop by
  ≥ 25% from full to cap-6, or writer median cost fails to drop materially.

DEPENDENCY_VERSION is expected **0/all** for every arm (the §11 wall; no reachable
lens) and is **constant across coverage**, so it does not affect the coverage
slope; it is reported but excluded from the ESCAPE detection-preservation test.
RESOURCE_BUDGET will likely read **differently LIVE (timing-bound)** than offline
(coverage-bound 8/8 in §11); whatever computes is reported.

## (e) SPEND CAP — frozen, hard

- **Real out-of-pocket = OpenAI GPT-5.5 writer calls only.** (Claude
  orchestrator/workers run on the subscription OAuth path — plan usage, not
  marginal API dollars — per `sessions.py` deviation D1.)
- **HARD CAP: $12.00 OpenAI spend** for the whole run. Estimated need ≈ $5
  (see estimate below); the cap is headroom.
- **Run-count guardrail: ≤ 90 runs** (subscription-usage guard).
- Hitting either cap is **SYSTEM BEHAVIOR**: the run halts, the partial matrix and
  the cap-hit are logged and reported as-is — never hidden, never worked around by
  quietly shrinking scope mid-run.

---

## COST ESTIMATE (reported with the frozen pre-reg; run only on confirmation)

Per-run costs from the banked runs (this pre-reg's measurement):
- batch clean (S1): **$0.234**/run (Claude subscription; $0 OpenAI).
- monitored clean: worker+orch ≈ $0.20 (Claude sub) + GPT-5.5 writer ≈
  $0.03–0.06 (OpenAI; lower with cap + warm cache).
- monitored injected: worker+orch+replan ≈ $0.33 (Claude sub) + GPT-5.5
  writer/recompile ≈ $0.05–0.09 (OpenAI).

**Real OpenAI out-of-pocket:**
- clean monitored: 36 runs × 1 writer call ≈ 36 calls.
- injected monitored: 33 runs × ~1.4 calls (compile + occasional replan recompile)
  ≈ 46 calls.
- ≈ 82 GPT-5.5 calls × ~$0.05 ≈ **$4–5 OpenAI** (well under the $12 cap).

**Claude subscription usage (not marginal $, modeled for the ratio):** 81 runs ×
~$0.2–0.35 ≈ **$18–25 modeled** (plan usage).

**Modeled total (ratio context, not out-of-pocket): ≈ $25.**
**Wall time:** ~81 runs × ~2–3 min ≈ **3–4 h** (background matrix).

If a smaller footprint is preferred, the reducible knob is **clean seeds 3 → 2**
(48 → 32 clean runs) and/or dropping the DV injected cells (constant 0); this
lowers OpenAI spend to ≈ $3–4 and wall time to ~2.5 h, at some loss of median
stability. Proposed default is the 81-run matrix above.

---

## DEVIATIONS (logged, not edited into the frozen numbers above)

- **D-V3-1 (2026-07-01, execution-environment): background runs are killed on a
  short, variable leash** (observed windows ~12 min then <2 min), so the full
  81-run LIVE matrix (~4 h) cannot complete as one background job. Two changes,
  both execution-only (no change to the bar §a, lever §b, verdict meanings §d, or
  spend cap §e):
  1. **Execution mode → foreground-chunked, resumable.** Each invocation runs a
     time-bounded chunk (~520 s) then exits; a resume map (cell keys already in
     `v3_results.jsonl`) skips completed cells and carries the cumulative OpenAI
     spend across chunks, so the $12 cap and run count are enforced end-to-end.
  2. **Reduced matrix (fewer cells, same design):** clean overhead **1 seed**
     (was 3) × 4 tasks × {batch, full, cap12, cap6} = 16 clean cells; injected
     detection on **6 faults × 3 coverage = 18** cells — a1{endpoint_404,
     token_expiry, quota_cliff}, c1{doc_contradiction}, d1{gate_skip_trap},
     b1{silent_minor_bump}. Total **34 runs**. This keeps the coverage SLOPE
     (full→cap12→cap6) on all 4 tasks and the coupling test on the cap-sensitive
     value-lens fault (doc_contradiction) + an easy control (endpoint_404) + RB
     (quota_cliff, live-timing) + DV (silent_minor_bump, constant). Cost basis and
     medians are now over 1 seed × 4 tasks — reported as such, a screen-grade
     denominator, not the 3-seed confirmatory median. `schema_drift` is dropped
     from the injected set (offline 2/4, structure-shaped) to bound run count.

---

## FROZEN — DO NOT PROCEED WITHOUT USER CONFIRMATION

Per mission STEP 1: STOP here. Await explicit user confirmation that (1) this
pre-reg is frozen and (2) the estimate/cap are acceptable, before running any cell.
