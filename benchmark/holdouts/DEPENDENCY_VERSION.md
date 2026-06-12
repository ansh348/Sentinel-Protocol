# Held-out category: DEPENDENCY_VERSION — injection `silent_minor_bump`

**QUALIFICATION VERDICT (2026-06-12): NOT QUALIFIED as specified — the
wound landed in 0/3 qualification seeds (plan-time pre-pagination and
in-body total_count self-description; full diagnosis and proposed revision
in decisions/holdout_qualification_2026-06-12.md). Per the pre-committed
rule, this spec gets revised, not the bar. Revision pending author ruling;
do not consume this spec for 1b until re-qualified.**

**Status:** authored 2026-06-12 under decision memo §5 condition (b)
(decisions/decision_memo_phase1.md, e808862). Phase 1b's recall denominator
includes this category; it is structurally unseen by the v2 design (v6.1
§11.10 item 3). This document is benchmark authorship — sanctioned pre-build
work. No v2 component existed or ran when it was written.

## 1. Mutation (counter-triggered, deterministic)

At fire counter N (counter path only, M1 amendment 3), the designated
service family's **version surface** flips:

- `GET /manifest` (unauthenticated, countable) lists every service's
  `version` and `default_page_size`. At N, the family's entries flip
  `1.4.0 -> <drawn 2.0.x>` and `100 -> <drawn post page size>`.
- Every family response carries `X-API-Version` (header), present from run
  start at `1.4.0` and flipping to the drawn `2.0.x` at N.
- Simultaneously, the family's **list/search endpoints drop their default
  page size** (canonical form: 100 -> 10; drawn per-task values below).
  Explicit pagination (`?page_size=`, `?page=`) is honored at all times,
  before and after the flip, capped at 100.
- **Every response stays 200.** Payloads stay well-formed and carry
  `total_count` (the full collection size) and the list key
  (`items`/`files`/`passages`/`results`/`destinations`) truncated to the
  effective default page size. **No error exists anywhere in the run** —
  this is the pure content signal, the structural complement of
  RESOURCE_BUDGET's two-phase status signal.

## 2. The wound

Batch treats page one as complete — **it was, pre-injection** (and at
plan-time: the world's 1.x semantics return whole collections under the
100 default; assumption surface b1/a4: "GET /repo/files enumerates the
complete file set, so no annotation site is missed"). Post-flip, page one
silently carries a strict subset, and batch assembles a confidently wrong
answer from the truncated data. Task output validation must — and does —
fail on truncated input (see §5 per-task wounds).

### Fire window (explicit timing rule)

All four plans enumerate their collections FIRST; a mid-run flip post-dates
the only enumeration touch and structurally cannot wound — exactly H2's
single-visit mechanism (memo Appendix B) and §11.10's "injection timing as
an explicit variable". The category therefore defines its fire window as
**N drawn from {1, 2, 3}**: the silent bump lands between plan-time and the
first enumeration touch (the realistic shape of a dependency version bump,
which happens between sessions, not inside one). Detection remains fair at
any N for an active monitor: the manifest and the `total_count !=
len(items)` fingerprint are standing, re-readable surfaces independent of
fire timing. Qualification runs used N = 1 (deterministic wound; no
worker-dispatch-order race).

## 3. Oracle recovery (recovery_class labels, 1bKG1 recovery-quality gate)

- **REINTERPRET** (read the version surface; request explicit
  `page_size=100` or paginate to exhaustion) **+ REDO of the affected
  calls** is the passing recovery.
- **RETREAT is NOT a passing grade for this category.** Recovery is always
  possible by construction: explicit pagination is honored at every moment
  of every run, so a system that detects the truncation can always recover
  the complete collection at the cost of re-paged calls. This asymmetry is
  deliberate and binding: an abort here is an unjustified abort and counts
  against the recovery-quality gate (memo §3, abort-economics clause —
  aborts cannot launder parity), in contrast to RESOURCE_BUDGET's
  post-cliff cells where retreat is the justified terminal move.

## 4. Deterministic decidability (stated per the adjudication-battery rule)

Two zero-LLM fingerprints, each sufficient:

1. `total_count != len(<list key>)` on any family list/search response —
   a field read plus a length comparison.
2. Manifest/version re-read: `GET /manifest` family entries differ from
   their plan-time values (`version` 1.4.0 -> 2.0.x,
   `default_page_size` 100 -> drawn value); equivalently `X-API-Version`
   changes value mid-run.

No semantics, no thresholds, no model (battery Task C precedent, v6.1
§11.11).

## 5. Designated service family and task semantics

| Task | Family | Truncated surface(s) | Concrete wound | "Task validation" concretely |
|---|---|---|---|---|
| b1 | `/repo` | `GET /repo/files` (8 files at rev 2) | w2's file enumeration hides page-2 pricing-annotated src files (src/tax.py at post=5; +src/quotes.py at post<=4); their annotations stay stale; `POST /repo/validate` fails `references_resolve` | checkers/b1.py: validate_status passed + zero stale annotations — fails on truncated migration |
| a1 | `/inventory`, `/pricing`, `/shipping` | `GET /inventory/items` (6 SKUs) | SKU list truncated below 6; report covers the visible subset | checkers/a1.py exact-match over all six SKUs — fails on missing SKUs |
| c1 | `/docs` | `GET /docs/passages`, `GET /docs/search` | search results truncated; weak wound — the seeded plan pins passage ids, so direct reads bypass enumeration (recorded honestly: likely non-wounding; superset cell) | checkers/c1.py |
| d1 | `/docs`, `/inventory` | `GET /inventory/items` (6 SKUs) | catalog body drafted from the visible SKU subset | checkers/d1.py: catalog must describe all six SKUs |

Primary qualification host: **b1** (the truncation hides work the gate then
catches: the cleanest validation-failure wound, and the REINTERPRET+REDO
oracle is exact).

### Rev-2 repo fixture pack (DV-enabling, this category's authored fixture)

The fixture repo grows 4 -> 8 files at `world_rev: 2` (REPO_FILES_V2):
existing four plus `src/exports.py` (inventory.endpoint annotation),
`src/quotes.py` (pricing.source_field), `src/tax.py` (pricing.source_field),
`src/validators.py` (report.format). Sorted listing order puts
`src/report.py`, `src/tax.py`, `src/validators.py` on page 2 at post-size 5.
Clean b1 workload stays within worker turn caps (3 annotated files to
migrate instead of 1). Phase 1 worlds (`world_rev` absent -> 1) are
untouched; banked-trace replay byte-identity is preserved.

## 6. Parameter draw rules (escrow consumes these) — deviation note

**Deviation from the brief's nominal numbers, flagged for author review:**
the canonical 100 -> 10 drop never truncates this world's collections
(max 8 items), so implementing 100 -> 10 literally produces a structurally
non-wounding category. The spec keeps the canonical mutation FORM and draws
the post size below collection size, consistent with the brief's own
per-cell "version string + page-size pair" escrow draw:

- **Pre page size:** fixed 100 (the 1.x default; matches whole-collection
  behavior exactly).
- **Post page size:** drawn uniform per cell — b1: [3, 6] (8-file repo;
  post=7 hides only src/validators.py and cannot wound); a1/c1/d1: [3, 5]
  (6-item collections).
- **Version strings:** pre fixed `1.4.0` (authored world constant, uniform
  across clean and injected worlds); post drawn per cell from
  {`2.0.0`, `2.0.1`}.
- **N:** drawn per cell from {1, 2, 3} (§2 fire-window rule).
- Family designation per task is FIXED by §5 (recorded per cell in escrow).

Qualification runs (qseed-901/902/903) used **post page size 5,
version 2.0.0, N = 1** on b1; the escrowed 1b values are drawn
independently and never seen by the author.

## 7. Qualification criteria (this session's Task 3, mirroring the original nine)

On the primary host (b1), seeds qseed-901/902/903 (distinct namespace;
matrix seeds are NOT drawn from these): 3 clean S1 runs + 3 injected S1
runs. **PASS** = injected S1 fails task validation (or emits wrong output)
in >= 2/3 seeds while clean S1 passes in >= 2/3 seeds. A failed
qualification revises this spec, never the bar.

## 8. Harness integration notes (1b launch; not this session)

- All DV surface (manifest route, X-API-Version, total_count, pagination
  defaults, REPO_FILES_V2) exists only at `world_rev: 2`; rev-1 worlds are
  byte-identical to Phase 1.
- The 1b launcher consumes `escrow/holdout_escrow.json` programmatically
  (per-cell seed, N, post page size, post version); the author never opens
  the file.
- D6 surface derivation and D13 pattern-liveness samples must become
  rev-aware at 1b build time (#7-class instrument fix, regression-evidenced
  and deviation-logged per memo §5(e)), or 1b tripwires targeting /manifest
  would be classified dead — the exact #7 wound.
