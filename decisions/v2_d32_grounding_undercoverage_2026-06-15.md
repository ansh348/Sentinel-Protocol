# D32 — Family-template grounding under-coverage fix (C0 record, before code)

**Date:** 2026-06-15. **Status:** build-in-progress (C0 written before any code). **Flag:**
behind `TRIPWIRE_V2`; flag-off byte-identical to Phase 1. **Matrix:** NOT run. **Held-out:** not
touched. Full ruling in `deviations.md` D32; this memo is the build record.

## The diagnosis this answers

The grounding-rate diagnosis (`analysis/v2_doc_grounding_rate.py`,
`runs/v2_doc_grounding_rate/summary.json`) isolated the c1+doc_contradiction compile (plan held
FIXED to the real recorded orchestrator plan, N=10 independent Sonnet compiles, world=None) and
found:

- The **compile is reliable**: 10/10 ground the value probe on `/docs/passages/pol-returns`
  under the concrete-naming plan. The D31 residual "compile passage-grounding non-determinism"
  does NOT reproduce at the compile step under a concrete-naming plan.
- The real locus is a **deterministic substrate under-coverage bug**: when the model emits the
  family template `/docs/passages/{passage_id}`, `_instantiate` does `sorted(glob)[0]` and arms
  ONE arbitrary (lexicographically-first) member of a family the integrity property spans. It is
  harmless in c1 only because the plan ALSO names `pol-returns` concretely. Under a plan that
  names retrieval generically (no concrete id), the template is the only passage probe and the
  lexicographic pick watches the wrong member → MISS.
- The diagnosis flagged the decisive **generic-plan** test and did not spend it (budget).

## The rule (deterministic, category-blind, injection-blind)

A compiled probe targeting a family-level template (`{param}` segment) grounds to, in order:
1. the **plan-named concrete ids** the soft set names directly inside the family glob; else
2. **all bounded family members** enumerable from `path_samples_for_rev`, within the cap; else
3. **UNCOVERED_CAUTION** (D29 valve).

Each armed member composes with the existing per-surface policy (D31 write-footprint / gate
eval / D30 baseline+drift). Budget overflow beyond `FAMILY_MEMBER_CAP` → UNCOVERED_CAUTION.
Invented-concrete-id grounding (D5/D8) is unchanged (single real representative); a concrete
hallucinated surface still fails loudly (N2). The LLM compile prompt is byte-unchanged.

## Why this is injection-blind

The rule resolves a template to plan-provided ids or the WHOLE bounded family. It never
references, prefers, or singles out the injected member. Coverage of the injected member follows
only because (concrete plan) the plan named it as the task's subject, or (generic plan) it is one
member of the fully-armed family — never because the fix knows which member is injected. Family
membership is drawn from the seen/synthetic surface enumeration, never from escrow.

## Build checkpoints

- **C0** (this): deviation + memo, committed before code.
- **C1**: implement in `_instantiate`/`ground_surface`/`compile_pipeline`; unit tests
  (plan-named → exactly those; none → full member set, rule names no injected id; unbounded →
  uncovered; planned-write member → D31; budget overflow → uncovered).
- **C2**: full seen sweep (5 categories + 3 clean) via real V2Conductor (no regression) +
  doc_contradiction under BOTH plans (concrete c1 + generic variant); report armed family set,
  baseline-vs-injection index, FIR, cost. Bounded dev-run (~$6).
- **CLOSE**: full suite both flag states; byte-identity 27/27 both; assert prompt byte-unchanged
  + D28/D29/D30/D31 preserved; $0 dollar impact + count submetric delta; commit the chain. STOP.
