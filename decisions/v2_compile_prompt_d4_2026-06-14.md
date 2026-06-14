# v2 Compile Prompt (D4) — Build Session Report (2026-06-14)

**Scope:** the ONE LLM step of the v2 path — the compile prompt that performs SOFT
dependency extraction feeding the deterministic substrate (B1–B7). The judgment layers
(corroboration wiring, cadence semantics, the audit harness, the rebuilt-judge arm)
remain HARD STOPS for sessions with the author present.

**Commits:** master, `0769236` (C0) → `bc742a8`; this report + ledger close the session.
Prior state: `f1c0634` (substrate close, B1–B7).

---

## What was built

### C0 — custody (commit 0769236)
Design-of-record §9 in `probe_compiler_design_v0.4.md` (soft extraction over the
substrate's hard constraints; generous; category-blind; few-shot from seen; the
operationalization note). Deviation **D27** logged BEFORE any tuning: the frozen
few-shot example-selection rule + shape→seen-surface binding table (sibling to D25).

### C1 — frozen few-shot set (dc74f7f)
`prompts/v2_compile_fewshot.json`: six worked examples (one per change-shape) derived
from the D27 table — seen-category surfaces only, spanning auth/inventory/pricing/docs/
repo + a cross-surface relation; teaches the shape-reasoning and the pointer rule.

### C2 — the compile prompt + LLM wrapper (2189241)
`prompts/v2_compile.md`: **category-blind** (no failure-category list; reasons only in
the six change-shapes), generous, four internal steps, soft output. `compile_probes.py`:
`SoftAssumption`/`SoftAssumptionSet` (`extra='forbid'` ⇒ a smuggled lens/firing field is
a validation error), `render_compile_prompt`, `compile_assumptions` (one bounded claude
call, one retry, a `compile` trace event per attempt).

### C3 — wire into the substrate (ae47d28)
`compile_pipeline`: appendix grounding rejects hallucinated surfaces LOUDLY (reuse the
N2 classifier); the provenance gate demotes chain-incomplete assumptions (missing
recovery hint, §3.3) to telemetry; attachment+lens+typing compile survivors — bare
surface → STRUCTURE probe, pointer → VALUE probe, gate surface → the §4 shadow via the
non-perturbation trapdoor (uncovered→caution when no world).

### C4 — recording + byte-identical replay (5f0902a)
`record_compile` writes the soft assumptions (the model output) + probe summary into the
run trace; `replay_compile` reconstructs the probes deterministically with NO model call.
Replay is byte-identical for non-gate AND gate probes.

### C5 — cost discipline (1d5ac1d)
`CompileEconomics`/`account_compile`: one bounded compile per run + one per replan
(keep-not-flush, D2), each ≤ MAX_ATTEMPTS; compile cost booked as overhead against the
12% clean cap (replan recompile booked on the run it occurs on, A5).

### Two robustness fixes the live measurement drove (0c4f318, bc742a8)
The measurement surfaced a genuine D5/D8-class **schema-transmission gap**, fixed
generally (not per-category):
1. **Dialect tolerance** — the model copies the appendix's `"METHOD /path/{template}"`
   form; `ground_surface` strips the HTTP method and instantiates a route template to a
   concrete representative.
2. **Invented-id grounding** — the model names the right route but invents a
   plausible-wrong id (`/pricing/quote/SKU-001`; the a1 appendix lists no SKUs);
   `ground_surface` matches such a concrete surface against the rev's real route
   templates and grounds it to a real representative (the model names the route; the
   substrate grounds the id). A truly hallucinated surface still fails loudly. The prompt
   was softened to keep the `{parameter}` placeholder when no real id is given.

---

## Test counts

| step | test file | new tests |
|---|---|---|
| C1 | test_v2_fewshot.py | 6 |
| C2 | test_v2_compile.py | 6 |
| C3 (+2 dialect/invented-id) | test_v2_compile_pipeline.py | 10 |
| C4 | test_v2_compile_replay.py | 3 |
| C5 | test_v2_compile_economics.py | 7 |
| **total new** | | **32** |

**Full suite 258/258 passing, flag OFF and flag ON (`TRIPWIRE_V2=1`).** Banked-world
byte-identity **27/27 both flag states** (no world code changed this session; outputs
`runs/archaeology_v2/replay_check_v2_d4_close*.json`; banked `replay_check.json` restored
byte-identical).

## Seen-category extraction-recall numbers

Measured live (sonnet COMPILE_MODEL), SEEN injections only, appendix derived seen-only
(rev 1, no held-out surface), category-blind prompt; recall = of the nine seen
(task, injection) cells, did the prompt emit an assumption grounding to the injected
surface (the injection defines the load-bearing surface — compiler-independent).

| pass | recall (mean / 3 samples) | note |
|---|---|---|
| pre-fix (dialect-strip only) | **78%** (7/9, stable) | a1 `/pricing/quote` dropped: model invented `/pricing/quote/SKU-001`, which failed concrete grounding |
| **post-fix** (invented-id grounding) | **100%** (9/9, all 3 samples, every cell 100%) | the model generously extracts every injected surface; the substrate grounds the route |

The model is generously complete (17–24 assumptions/task); the recall gap was entirely a
grounding-dialect artifact, now closed. (Generous output also makes a compile slow/costly
— 80–153 s, 24 assumptions — a real instance of the §0/C5 ≤12% overhead tension.)

## Spend
**~$4.65 LLM** total (the first v2 component to spend LLM; under the $10 cap): one $0.004
haiku launcher probe, one $0.13 a1 diagnostic, and four measurement passes ($0.58 + $0.59
+ $1.58 + $1.76) — the extra passes were the iterations that surfaced and then verified
the two grounding fixes. Detail: `analysis/dev_run_ledger.md`.

## Rule Zero (design-blindness) compliance
- **Category-blind prompt:** `prompts/v2_compile.md` contains NO failure-category label;
  it reasons only in the six general change-shapes. `test_v2_compile` asserts the five
  seen category labels are absent from the rendered prompt.
- **Few-shot seen-only:** `test_v2_fewshot` asserts no held-out token
  (quota_cliff/silent_minor_bump/RESOURCE_BUDGET/DEPENDENCY_VERSION/`/manifest`/rev-2
  pagination) and no category label appears anywhere in the set; one example per shape.
- **Frozen selection rule (D27):** the few-shot set was chosen by a fixed criterion +
  binding table committed (C0) BEFORE the prompt was written/tuned or any compile call
  was made — not hand-curated against outputs.
- **Tuned/validated on seen only:** the prompt was tuned and the recall measured on the
  five seen categories with a seen-only (rev-1) appendix; it was NOT evaluated against the
  held-out two or any real benchmark cell. Generalization to the held-out categories is
  measured ONLY at matrix launch.

## HARD STOPS — verified NOT built
- **Probe-primary corroboration wiring** — only the inert `Corroboration` seam in the
  typing engine; nothing computes corroboration.
- **Event-gated cadence semantics** — `scheduler.py` still NoOp-only; `cadence_hint` is
  carried as data, consumed by nothing.
- **Firing + inventory audit harness** — not built (D25 quarantine governs it).
- **Rebuilt-judge arm** — `arms.py` untouched (`resolve_arm` still raises).

---

## Judgment decisions still waiting (for sessions with the author)
1. **Probe-primary corroboration** — policy/wiring behind the §2.1 "OR corroborated" seam.
2. **Event-gated cadence semantics** — when to sweep; the work-at-risk weighting + the
   guaranteed pre-completion sweep that §3.1/B4 delegate runtime re-observation to.
3. **Firing + inventory audit harness** — the §7 audits, obeying the D25 held-out-
   denominator quarantine.
4. **Arm registration** — provisional ids V2/V2J and the two-tier/rebuilt-judge arms
   remain unregistered until the author wires them.
5. **Compile-prompt open items (flagged):** (a) whether the prompt should also emit the
   change-shape explicitly (it would let the substrate pick STATUS/ORDER/RELATION
   directly rather than via the gate/value/structure default — §9.1, deferred as it edges
   toward a lens choice); (b) richer ORDER/RELATION extraction (the soft prompt currently
   exercises the gate/value/structure subset); (c) the generous-output compile latency/
   cost vs the 12% cap (C5 measures it; a budget policy is a tuning choice).
6. **Phase-1c probe-failure policy (D26, OWED)** — still owed before any 1c data.
