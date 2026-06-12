# Held-out category escrow record — Phase 1b value superset

**Drawn:** 2026-06-12, after both held-out categories qualified
(RESOURCE_BUDGET 2026-06-12 on a1; DEPENDENCY_VERSION spec rev 3
2026-06-12 on b1 — decisions/holdout_qualification_2026-06-12.md), per
decision memo §5 condition (b) (e808862) and author rulings #1 and #2.

**File:** `escrow/holdout_escrow.json` — **gitignored** (verified via
`git check-ignore` before writing; the repo is public and the drawn
values must never be committed or printed).

**SHA-256 (the only public trace of the contents):**

```
df1dcd8bd1cad04f815576cc1d6876807e95bbf25ffc959ada40ff0fa2bb3c88
```

**Superset shape:** 4 tasks (a1/b1/c1/d1) x 5 seeds x 2 categories =
40 cells. A SUPERSET by design: the 1b matrix consumes the qualified
(task, category) pairs drawn from within; unqualified combinations
(e.g. c1's structurally weak DV wound) remain in the superset without
revealing which cells the matrix uses.

**Per-cell contents (schema, not values):** category, injection type,
run seed (1000–9999, distinct from matrix seeds {1,2,3} and qseeds
{901..909}), fire counter N, Q0 (RESOURCE_BUDGET), post version + post
page size (DEPENDENCY_VERSION), service family designation.

**Draw basis (non-secret, printed at draw time):** clean medians
a1 24, c1 12, d1 21 (Phase 1 finals), b1 14 (rev-4 re-qualification);
RB Q0 range [8, 14]; RB N in [40%, 60%] of clean median; DV N = 1
(ruling #2 R2); DV post-page ranges b1 [3, 6], a1/c1/d1 [3, 5] — all
strictly below host collection size (ruling #2 R5 constraint, asserted
in analysis/holdout_escrow_draw.py). Values drawn with the `secrets`
module: cryptographically random, no seed exists from which the author
could re-derive them. The draw script refuses to run twice.

**Custody rule:** the file is transmitted to the non-implementer escrow
holder (advisor or co-founder, per memo §5(b)); the Phase 1b harness
consumes it programmatically at 1b launch; **the author does not open
it.** Integrity at launch is verified against the SHA-256 above.
