# Matrix escrow record — Phase 1b original-category values (AUTHOR-5)

**Drawn:** 2026-06-12, immediately after the prereg_1b freeze (commit
6c8cc47, which carries the FROZEN pre-registration, the draw spec
benchmark/matrix_draw_spec.md, and the draw script — all committed BEFORE
the draw executed, per the AUTHOR-5 ruling amendment).

**File:** `escrow/matrix_escrow.json` — **gitignored** (verified via
`git check-ignore` before writing; the repo is public and the drawn values
must never be committed or printed).

**SHA-256 (the only public trace of the contents):**

```
2a9aed0a386df2f0fe5fa2122b2d85114f699eea8d6b2085df786cbeb6204e0e
```

**Shape:** 27 original-injected cells (9 qualified pairs × 3 seed slots) +
12 clean cells (4 tasks × 3 seed slots) = 39 cells; a cell's drawn values
are shared across all five arms.

**Per-cell contents (schema, not values):** task, injection (injected
cells), seed slot, run seed (10000–99999, unique, disjoint from Phase 1
matrix seeds {1,2,3}, qualification seeds 901–912, and the holdout-escrow
namespace 1000–9999), n_inject (injected cells only).

**Draw basis (non-secret, printed at draw time):** clean medians a1 24,
b1 14, c1 12, d1 21 (Phase 1 finals; b1 from the rev-4 re-qualification —
the holdout escrow record's basis, unchanged); n_inject ranges a1 [9, 14],
b1 [5, 8], c1 [4, 7], d1 [8, 12] (= [floor(0.40·m), floor(0.60·m)]);
payload-parameter variation NONE (benchmark/matrix_draw_spec.md §2: the
wound-preserving variation set is empty; injection params stay exactly as
qualified). Values drawn with the `secrets` module: cryptographically
random, no seed exists from which the author could re-derive them. The
draw script refuses to run twice.

**Custody rule:** identical to the holdout escrow
(decisions/holdout_escrow_record.md): the file is transmitted to the
non-implementer escrow holder (Zeynep Sağlık, co-founder); the Phase 1b
harness consumes it programmatically at 1b launch after verifying the
SHA-256 above; **the author does not open it**; the holder produces her
copy only on the author's written request; the loader never prints or logs
drawn values.

## Transmission record (2026-06-13)

The escrow file was transmitted by the author to the escrow holder via
WhatsApp on 2026-06-13 at 01:33 local (author-attested "done" with
screenshot reviewed in-session), as a single file (matrix_escrow.json,
~4 kB), followed at 01:34 by the custody SHA-256 in the same thread
(matches this record:
2a9aed0a386df2f0fe5fa2122b2d85114f699eea8d6b2085df786cbeb6204e0e),
enabling the holder to verify her copy against this public record
independently. Identity note, recorded for completeness (the holdout
record's custody-note pattern): the WhatsApp chat carries the contact
alias "Von Neumann"; the holder of record per the custody rule is Zeynep
Sağlık, and the alias-to-holder identity stands on the author's
attestation. **Receipt acknowledgment from the holder: not yet visible at
screenshot time — to be appended on receipt (the holdout record's
delivery-plus-confirmation pattern).** Standing custody rules unchanged:
hold; return only on the author's written request; hash publicly
committed so neither side can swap the file; the author does not open the
local copy, which the harness consumes programmatically at launch.

**Blindness statement:** the drawn values were never printed, logged, or
displayed during the draw (console output: shape, non-secret basis,
SHA-256 only — session record); they remain unseen by the author.
