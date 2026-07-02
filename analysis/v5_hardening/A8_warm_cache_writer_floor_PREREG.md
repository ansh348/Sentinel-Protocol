# A8 --- Warm-cache writer floor: MINI PRE-REGISTRATION (NOT YET RUN)

**STATUS: NOT RUN. Awaiting explicit author go-ahead + spend authorization.**
Per the brief, this probe requires explicit author approval and this pre-registration
committed with a timestamp *before any run*. Nothing here has been executed. This file is
the pre-commitment artifact only.

`[AUTHOR-INPUT: approve/deny A8; if approved, ratify this pre-reg and commit it with a real
timestamp BEFORE the first run.]`

---

## Motivation and why it might be inconvenient
Edit 2's coupling claim ("coverage of the plan's assumptions has a floor cost proportional
to the plan") and §9's GPT-5.5 result rest on writer calls whose input is not
cache-amortized. If a warm prompt cache makes full-coverage check-writing cheap enough to
clear the 12% cap, the coupling claim must be scoped to *uncached* writers and Edit 2's
wording changes materially. This probe exists precisely because the answer might undercut
the paper; it must be run honestly or not cited.

## Design (frozen before any run)
- **Step 1 (static, no spend):** measure the fraction of the check-writer prompt that is a
  fixed, cacheable prefix (system + DSL spec + frozen few-shot) versus per-run plan content.
  Report cacheable-prefix tokens / total prompt tokens.
- **Step 2 (metered spend):** run the FULL-coverage GPT-5.5 check-writer with a warm cache
  on the four clean tasks (a1, b1, c1, d1). Use the same live batch denominator as §9,
  **\$0.2219** per run `[AUTHOR-INPUT: confirm this is the current live batch denominator]`.
- **Metric:** clean overhead = (warm-cache full-coverage writer run cost - batch baseline)
  / batch baseline, reported against \$0.2219.
- **Spend cap (hard):** `[AUTHOR-INPUT: confirm cap; brief suggests ~$2--5]`.

## Pre-registered prediction
`[AUTHOR-INPUT: record the author's prediction before running --- e.g. "cached full coverage
lands in the 15--25% range, still above 12%, because output tokens (the generated checklist)
are not cacheable and dominate the writer's cost."]`

## Verdict wording and the gate (frozen)
> With a warm prompt cache, full-coverage GPT-5.5 check-writing incurred a clean overhead of
> [Z]% against the live batch denominator (post-hoc, exploratory).
- **If Z >= 12%:** the coupling claim stands as written; note the cached measurement as a
  robustness point in §9.
- **If Z < 12% (the inconvenient outcome):** STOP. Do NOT quietly absorb it. Flag prominently
  in AUTHOR_TODO; the coupling claim must be scoped to *uncached* writers and Edit 2(b)/(d)
  rewording is required (the floor would then be a caching artifact, not a plan-proportional
  cost). This is the Edit 2d gate.

## Reporting rule
Attaches to Edit 2 and §9 only, labeled post-hoc exploratory. Does not alter any frozen
confirmatory number. If run, its outcome gates Edit 2's wording (see Edit 2d).
