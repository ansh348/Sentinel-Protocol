# Phase 1b matrix draw spec — original five categories (AUTHOR-5)

**Status:** committed in the ratification commit, BEFORE the draw executes
(prereg_1b.md AUTHOR-5 ruling amendment, 2026-06-12). Benchmark authorship;
no v2 component exists or ran when this was written. The draw script is
analysis/matrix_escrow_draw.py (run-once, `secrets` module); output is
`escrow/matrix_escrow.json` — gitignored (verified via `git check-ignore`
before writing), sealed, SHA-256 public, transmitted to the escrow holder
under the standing custody rules; the 1b loader consumes it
programmatically and never prints or logs drawn values.

## 1. What is drawn

- **Run seeds, per cell, unique:** uniform in [10000, 99999] — disjoint by
  construction from Phase 1 matrix seeds {1,2,3}, qualification seeds
  901–912, and the holdout-escrow namespace 1000–9999.
  - 27 original-injected cells: 9 qualified pairs × 3 seed slots
    (prereg_1b AUTHOR-2/AUTHOR-5 rulings).
  - 12 clean cells: 4 tasks × 3 seed slots. Clean-cell seeds are part of
    the same sealed draw for uniformity of custody (AUTHOR-2 requires
    3 clean seeds per task and no other record provides them); nothing
    about a clean cell is secret per se, but sealing everything keeps one
    loader, one custody rule, one hash.
  - A cell's drawn values are shared across all five arms (injections
    identical across systems at the same counter — the Phase 1
    comparability convention; prereg_1b §3).
- **Fire counters, per injected cell:** `n_inject` uniform integer in
  [floor(0.40·m), floor(0.60·m)] of the task's clean-median tool-call
  count m — the RB convention (RESOURCE_BUDGET.md §6) generalizing
  Phase 1's fixed 50% point. Medians (the holdout escrow record's draw
  basis, unchanged): a1 = 24, c1 = 12, d1 = 21 (Phase 1 finals,
  decisions/manipulation_table_s1_seed1.md); b1 = 14 (rev-4
  re-qualification clean median, decisions/holdout_escrow_record.md).
  Resulting ranges: a1 [9, 14]; b1 [5, 8]; c1 [4, 7]; d1 [8, 12].

## 2. Payload-parameter variation: the wound-preserving set is EMPTY

§11.10 item 3's "payload parameters varied" was examined per injection
against the world implementation (world/injections.py) and the
qualification record. Every payload parameter of the original five
categories is either task-identity, redesign-locked, or checker-linked;
varying any of them would alter the qualified wound and trigger the
AUTHOR-6 re-qualification clause. Per injection:

| injection | parameter | why it cannot vary |
|---|---|---|
| endpoint_404 (a1) | `path: /pricing/quote/*` | The removed route IS the wound's identity (tasks/a1.yaml assumption a1); removing any other route is a different assumption violation — a new, unqualified pair. The authored recovery surface (/pricing/quotes) is keyed to exactly this removal. |
| endpoint_404 (d1) | `path: /docs/package` | Same identity argument (tasks/d1.yaml assumption a2); §3a pair 9's RETREAT-condition label is derived from exactly this route having no alternative. |
| schema_drift (a1, pricing) | rename target `price`, silent dollars→cents | D18-locked: the rename target must not self-describe the unit change — night-0 proved `price_cents` lets the batch absorb the drift without replanning; the redesign IS the qualified wound. |
| schema_drift (b1, repo_config) | `DRIFTED_SETTINGS_YAML` authored constant | The drifted key target is what the validate gate's reference check breaks on (D18 companion note); a different drift is a different, unqualified wound. |
| token_expiry (a1, c1) | none (parameterless) | D19-locked mechanism: revoke-all + issuance suspension is the qualified design (night-0 proved the refresh path defeats anything weaker). There is no parameter to vary. |
| doc_contradiction (c1) | `passage_id: pol-returns` | Checker-linked: the frozen c1 premise probes (D16, tolerance frozen a priori) target the returns premise; contradicting another passage decouples the wound from the oracle. |
| gate_skip_trap (b1, d1) | `path: /repo/validate`, `/docs/validate` | The trapped gate is the task's REQUIRED gate (the only gate each task has); no other target exists. |

**How the anti-overfit intent is discharged anyway:** every seed-derived
world value (token streams, fixture instantiation, per-run world state)
re-derives from the freshly drawn, sealed run seeds, so the concrete
payloads v2 observes differ from anything in Phase 1's traces; and the
fire counters are drawn per cell from the ranges above rather than sitting
at the known 50% point. The blindness obligation of §11.10 item 3 ("v2
designers do not see the drawn values before freeze") is carried by the
seal, the public hash, and the holder's custody — identical to the holdout
escrow.

## 3. Draw mechanics and custody (binding)

1. Values drawn with the `secrets` module: cryptographically random, no
   seed exists from which the author could re-derive them.
2. The script refuses to run twice (output-exists guard, the
   holdout_escrow_draw.py pattern).
3. Console output is ONLY: the file path, the shape, the non-secret draw
   basis (the ranges above), and the SHA-256. No drawn value is ever
   printed, logged, or committed.
4. The file is transmitted to the escrow holder (Zeynep Sağlık,
   non-implementer) under the standing custody rules
   (decisions/holdout_escrow_record.md): hold; return only on written
   request; hash public so neither side can swap the file.
5. The 1b launcher verifies the SHA-256 at launch, consumes the file
   programmatically, and never prints or logs drawn values (prereg_1b §3
   build requirement, extended from the holdout loader to this file).
6. Custody record: decisions/matrix_escrow_record.md (committed after the
   draw, beside the holdout record).
