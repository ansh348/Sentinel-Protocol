# Held-out category: DEPENDENCY_VERSION — injection `silent_minor_bump`

**SPEC REV 2 (2026-06-12, world_rev 3) — author ruling adopting the
revision proposed in decisions/holdout_qualification_2026-06-12.md.
RE-QUALIFICATION (qseed-904/905/906) FAILED ON BOTH GATES: clean 1/3
(fixture-weight STOP branch) and wound-attributed injected failures 0/3
— root cause: the orchestrator consolidates b1 into a single worker
(5/6 plans), which both blows the 14-turn cap on the 8-file repo and
makes the enumeration the run's first call, unreachable by any mid-run
N (full appendix in decisions/holdout_qualification_2026-06-12.md).
STOPPED per the ruling; no third revision without a fresh author
ruling. Do not consume this spec for 1b.**

**Status:** authored 2026-06-12 under decision memo §5 condition (b)
(decisions/decision_memo_phase1.md, e808862); revised same day under the
pre-committed rule (spec revised, bar untouched; author ruling attached to
the revision directive). Phase 1b's recall denominator includes this
category; it is structurally unseen by the v2 design (v6.1 §11.10 item 3).
This document is benchmark authorship — sanctioned pre-build work. No v2
component existed or ran when it was written.

## 1. Mutation (counter-triggered, deterministic)

At fire counter N (counter path only, M1 amendment 3), the designated
service family's **version surface** flips and **its pagination parameter
is silently renamed**:

- `GET /manifest` (unauthenticated, countable) lists every service's
  `version`, `default_page_size`, and `page_size_param`. At N, the
  family's entries flip `1.4.0 -> <drawn 2.0.x>`, `100 -> <drawn post
  page size>`, and `page_size_param: "page_size" -> "limit"` — the
  manifest documents the rename.
- Every family response carries `X-API-Version` (header), present from
  run start at `1.4.0` and flipping to the drawn `2.0.x` at N.
- The family's list/search endpoints drop their default page size to the
  drawn post size, **which is below the host collection size by
  construction** (Section 6 — author-ratified constraint, encoded in the
  escrow-draw script).
- **v2.0 renames the pagination parameter** `page_size -> limit`.
  Post-bump, `page_size` is silently ignored (standard REST behavior for
  unknown query params: status 200, no warning) and `limit` is honored;
  pre-bump, `page_size` is honored and `limit` is ignored. The `page`
  parameter stays functional at all times (`page=2,3,...`).
- **List bodies carry no totals and no pagination hints** — no
  `total_count`, no `has_more`, no `next_page`. Ground truth lives in an
  **`X-Total-Count` response header** on every list/search response,
  present from run start (rev 3), carrying the full collection size.
- **Every response stays 200.** No error exists anywhere in the run —
  this is the pure content signal, the structural complement of
  RESOURCE_BUDGET's two-phase status signal.

## 2. The wound

Batch treats page one as complete — it was, pre-bump, and **explicit
`page_size=...` calls keep "working" post-bump while silently truncating
at the v2.0 default**. The rev-1 qualification showed this orchestrator
pre-armors workers with explicit `page_size=100` at plan time; under the
rename that armor is inert: the parameter is ignored without any tell in
the body, page one silently carries a strict subset, and batch assembles
a confidently wrong answer from the truncated data. Task output
validation must — and does — fail on truncated input (Section 5).

### Fire window (explicit timing rule — author ruling 2026-06-12)

N is **mid-run, never 1**: the run must begin under genuine v1.x behavior
(at least one call executes against 1.4.0) before the world shifts. The
binding structural constraint from the banked traces: the host plans
enumerate their collections at counters 1–3 (every banked b1 list call
lands there), so **N >= 4 makes the mutation structurally unobservable**
— the single-visit mechanism of H2 (memo Appendix B). The category's
fire window is therefore **N drawn from {2, 3}**: inside the live window,
after the run has begun under v1.x. Detection remains fair at any N for
an active monitor (the three decidability surfaces below are standing and
re-readable); the wound, by contrast, requires the bump to precede the
critical enumeration, and a worker whose enumeration races ahead of N is
an honest miss the 1b matrix measures rather than hides.

## 3. Oracle recovery (recovery_class labels, 1bKG1 recovery-quality gate)

- **REINTERPRET + REDO** is the passing recovery, via either route:
  (a) read the manifest (one call) — it documents `page_size_param:
  "limit"` — then re-list with `limit=N` (one call); or (b) paginate to
  exhaustion with the still-functional `page` parameter
  (ceil(collection/post_size) calls).
- **RETREAT is NOT a passing grade for this category.** Recovery is
  always possible by construction — both routes above work at every
  moment of every run — so an abort here is an unjustified abort and
  counts against the recovery-quality gate (memo §3, abort-economics
  clause), in contrast to RESOURCE_BUDGET's post-cliff cells where
  retreat is the justified terminal move. This asymmetry is deliberate
  and binding.

## 4. Deterministic decidability (stated per the adjudication-battery rule)

Three zero-LLM surfaces, each sufficient:

1. **Version flip:** `X-API-Version` changes value mid-run (header
   read), equivalently the manifest family entries differ from their
   plan-time values (`version` 1.4.0 -> 2.0.x).
2. **Truncation fingerprint:** `X-Total-Count != len(<list key>)` on any
   family list/search response — a header read plus a length comparison.
3. **Manifest re-read documenting the rename:** `page_size_param`
   flipped `"page_size" -> "limit"` (and `default_page_size` dropped) on
   the family's manifest entries.

No semantics, no thresholds, no model (battery Task C precedent, v6.1
§11.11). The fingerprints live in headers and the manifest — surfaces a
probe reads cheaply and a curl-driven batch worker never sees unasked —
per the D18 lesson (rev-1 qualification: the in-body `total_count`
self-described the truncation and the batch healed itself).

## 5. Designated service family and task semantics

| Task | Family | Truncated surface(s) | Concrete wound | "Task validation" concretely |
|---|---|---|---|---|
| b1 | `/repo` | `GET /repo/files` (8 files at rev >= 2) | w2's enumeration (explicit `page_size=100` included — ignored post-bump) hides page-2 pricing-annotated src files (src/tax.py at post=5; +src/quotes.py at post<=4); their annotations stay stale; `POST /repo/validate` fails `references_resolve` | checkers/b1.py: validate_status passed + zero stale annotations — fails on truncated migration |
| a1 | `/inventory`, `/pricing`, `/shipping` | `GET /inventory/items` (6 SKUs) | SKU list truncated below 6; report covers the visible subset | checkers/a1.py exact-match over all six SKUs |
| c1 | `/docs` | `GET /docs/passages`, `GET /docs/search` | search results truncated; weak wound — the seeded plan pins passage ids (recorded honestly: likely non-wounding; superset cell) | checkers/c1.py |
| d1 | `/docs`, `/inventory` | `GET /inventory/items` (6 SKUs) | catalog body drafted from the visible SKU subset | checkers/d1.py: catalog must describe all six SKUs |

Primary qualification host: **b1** (gate-verifiable wound; both recovery
routes exact).

### Rev-2 repo fixture pack (unchanged from spec rev 1)

The fixture repo carries 8 files at `world_rev >= 2` (REPO_FILES_V2):
pricing-annotated files in the page-2 tail of the sorted listing
(src/tax.py hidden at post-size 5). Phase 1 worlds (rev 1) are untouched;
the rev-2 world is frozen too (the rev-1-spec qualification runs replay
against it); rev 3 hosts this spec.

## 6. Parameter draw rules (escrow consumes these)

- **Pre page size:** fixed 100. **Pre version:** fixed `1.4.0`.
  **Pre parameter name:** fixed `page_size`.
- **Post page size:** drawn uniform per cell, **strictly below the host
  collection size (author-ratified constraint, asserted in
  analysis/holdout_escrow_draw.py):** b1: [3, 6] (8-file repo; post=7
  hides only src/validators.py and cannot wound); a1/c1/d1: [3, 5]
  (6-item collections).
- **Post version:** drawn per cell from {`2.0.0`, `2.0.1`}. **Post
  parameter name:** fixed `limit`.
- **N:** drawn per cell from **{2, 3}** (Section 2 fire-window rule).
- Family designation per task is FIXED by Section 5 (recorded per cell).

Re-qualification runs (qseed-904/905/906) used **post page size 5,
version 2.0.0, N = 2** on b1 — N recorded per the author ruling: 2 is the
latest counter at which the wound stays live across worker dispatch
orders (enumeration lands at counters 1–3; at N=2 exactly one call
pre-dates the bump) while the run still begins under genuine v1.x
behavior. The escrowed 1b values are drawn independently and never seen
by the author.

## 7. Qualification criteria

On the primary host (b1), seeds qseed-904/905/906 (fresh namespace;
901–903 are spent; matrix seeds are NOT drawn from any qseed): 3 clean S1
runs + 3 injected S1 runs on the rev-3 world (clean arm re-run; no arm
reuse across world revs). **PASS** = injected S1 fails task validation in
>= 2/3 seeds **by the wound** (truncated-data wrong output; failure
signatures itemized per run with trace pointers; non-wound failures
explicitly not counted) while clean S1 passes in >= 2/3 seeds. If clean
b1 fails >= 2/3: STOP — fixture-weight branch, separate author ruling. A
failed qualification revises this spec only under a fresh author ruling.

## 8. Harness integration notes (1b launch; not this session)

- All DV surface exists at `world_rev >= 2`; the rename + header-only
  totals exist at `world_rev: 3`. Rev-1 worlds are byte-identical to
  Phase 1; rev-2 worlds are byte-identical to the rev-1-spec
  qualification runs.
- The 1b launcher consumes `escrow/holdout_escrow.json` programmatically
  (per-cell seed, N, post page size, post version); the author never
  opens the file.
- D6 surface derivation and D13 pattern-liveness samples must become
  rev-aware at 1b build time (#7-class instrument fix, regression-
  evidenced and deviation-logged per memo §5(e)), or 1b tripwires
  targeting /manifest would be classified dead — the exact #7 wound.
