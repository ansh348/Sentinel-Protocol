# A7 — Benign-noise smoke test: PRE-REGISTRATION ADDENDUM (RATIFIED 2026-07-02)

**Status: RATIFIED 2026-07-02 (M1 signed, M3 prediction frozen). NOT RUN — no metered run,
trace, or FIR data exists; Phase 3 is gated on the author's explicit go.**
Drafted 2026-07-02 by the assistant at author direction, to freeze the parameters the base
pre-registration (`A7_benign_noise_smoke_PREREG.md`) left as `[AUTHOR-INPUT]`, then ratified by
the author. This file **extends** the base pre-reg; it does **not** modify it (the base file is
untouched). All author-authored fields are now frozen: M1 (ratification) and M3 (prediction,
recorded before any run) below. The addendum is timestamp-committed (see M1) before the first
A7 run.

**RATIFIED by the author on 2026-07-02**, before any run. Ratification timestamp (frozen in
this file): **2026-07-02**. Ratifying commit hash: **[POST-COMMIT BLANK — backfilled after the
commit; per convention the commit message carries the ratification and the file carries the
timestamp]**.

Provenance of every decision below: author message 2026-07-02 (M1–M6 + discrepancy + metric
note). Nothing here is invented; blanks are left blank.

---

## M1 — Approval & ratification (author decision: APPROVED + RATIFIED)

- **A7 is APPROVED and RATIFIED** by the author (2026-07-02).
- **Ratification:** the author ratified this addendum on 2026-07-02 (timestamp above); the
  timestamp-commit is carried by the ratifying git commit (message + hash backfilled above).
  The assistant did not sign or commit on the author's behalf — M1 is the author's signature.
- Precondition to run (from the base pre-reg / brief) — an approved, ratified,
  timestamp-committed pre-reg before the first run — is **met** on that commit. Phase 3 remains
  gated on the author's explicit go.

## M2 — Spend cap (FROZEN)

- **HARD CAP = $15.00** for the whole A7 run.
- **Meter:** the run's cumulative `total_cost_usd` at list prices (the repo's standard cost
  basis, identical to KG3's `total_cost_usd`). A7's arms (V2, S2, S1) run on the **Claude
  subscription** path (Sonnet orchestrator, Haiku workers; deviation D1) — there is **no
  GPT-5.5 writer** in A7 (that is V3 only). So `$15` is **MODELED subscription cost at list
  prices, not marginal OpenAI out-of-pocket.**
- **CONFIRMED (author, 2026-07-02):** the cap basis is **modeled `total_cost_usd` at list
  price**, labeled **MODELED** so it is **never conflated with the V3 study's metered-spend
  (real OpenAI out-of-pocket) accounting** — the two cost bases stay distinct in every A7 output.
- **On reaching the cap:** ABORT the run immediately; **report the partial matrix labeled as
  partial**; do **not** compute the verdict on a truncated matrix; do **not** quietly shrink
  scope to fit. (Mirrors the V3 §e / D-V3-1 cap-hit discipline.)
- **Rough size check (context, not a bar):** 36 runs (see M6) × ≈ $0.25–0.36/run ≈ **$9–11
  modeled**; noise-induced retries/replans (transient-500, any interrupt) can raise this, so
  $15 is headroom, not slack — the abort path is real.

## M3 — Pre-registered prediction

Provenance: the author's bet was elicited 2026-07-02 via explicit
choice (transient-500: "yes, the hair-trigger fires"); prose drafted
by an AI assistant from that bet and the Phase-0 mechanism notes;
ratified verbatim by the author at M1 signing. Placed post-Phase-2
offline build, pre-run: no metered runs, no live traces, and no FIR
data existed at freeze time.

V2 (redesign):
- Transient 500-then-success: PREDICT NONZERO FIR. Mechanism: the
  status fast path (D28/D30) interrupts on status >= 400 without a
  confirming probe; 500 is not in the {400,405,422} exclusion set;
  no heal-on-retry rule exists. Expected: most or all transient-500
  cells false-fire before the successful retry is observed.
- Latency spike: PREDICT FIR ~0, conditional on the D36 mechanism.
  No compiled check targets elapsed time, so near-predetermined
  silence; the class is read primarily as an S2 test with V2 as the
  designed-silence contrast (per D36).
- Additive schema field: PREDICT FIR 0, moderate confidence. Schema
  probes compare required fields for equality and are not
  closed-world, so an extra field should match nothing.

S2 (naive interrupt; corrected noiseless clean baseline: 4
false-fired cells, per D35):
- PREDICT noisy-clean FIR at or above its noiseless baseline; worst
  on transient-500 (raw anomaly escalated directly), moderate on
  additive-field, lowest on latency.

Asymmetry acknowledged: if the V2 transient-500 prediction is
correct, the confirmatory FIR of 0.0 does not survive benign
weather, and the Threats replacement paragraph will say so. That
outcome is anticipated, not feared.

## M4 — Seed block (APPROVED: seeds 4–15)

**Author instruction:** enumerate all seed namespaces in use; propose the lowest disjoint
block; do not finalize without author sign-off. **APPROVED by the author 2026-07-02: seeds 4–15.**

### Seed namespaces in use across the repo

| Namespace | Seeds in use | Evidence |
|---|---|---|
| Phase-1 confirmatory (clean cells / planning manifest) | **1, 2, 3** | `analysis/matrix_manifest.json` (all rows); `prereg.md`/D17; A6 (4 tasks × 3 seeds) |
| Confirmatory **injected** cells (escrow-drawn) | low-thousands — **observed 2594, 5682, 6570, 6820, 7968** | `deviations.md` D34 (a1-S3-quota_cliff seeds); sealed escrow (D23) |
| Qualification | **901+** — observed 910, 911 | `V3_PRICED_RUN_PREREG.md` §c; `deviations.md` D23 (s910/s911) |
| V3 priced study | **50011, 50012, 50013** | `V3_PRICED_RUN_PREREG.md` §12.4 |

The V3 pre-reg §c already names the canonical constraint verbatim: *"disjoint from Phase-1
{1,2,3}, qualification 901+, and escrow namespaces."*

### APPROVED block — **seeds 4–15** (12 seeds)

A7 needs **12 distinct seeds**, one per **(task × anomaly-class)** cell, each seed reused
across the V2 / S2 / S1 arms so all three arms see the identical noise schedule per cell
(12 seeds × 3 arms = 36 runs; see M6). The block is the lowest contiguous run above {1,2,3}:

| | transient-500 | latency | additive-field |
|---|---|---|---|
| **a1** | 4 | 5 | 6 |
| **b1** | 7 | 8 | 9 |
| **c1** | 10 | 11 | 12 |
| **d1** | 13 | 14 | 15 |

Disjoint from Phase-1 {1,2,3} ✓, below qualification 901+ ✓, far below escrow (all observed
draws ≥ 2594) and V3 (50011+) ✓.

**Escrow-disjointness basis — recorded explicitly as INFERENCE (author ruling, 2026-07-02).**
The escrow namespace is **sealed**; I **cannot machine-verify** that no escrow draw lands in
4–900. The disjointness of 4–15 from escrow therefore rests on **inference only**: every
*observed* escrow seed is **≥ 2594** and escrow is a large-draw namespace, so 4–15 is very
likely escrow-free — **an inference, not a proof.** **Ruling:** the block is approved on this
basis, and **any later-discovered collision between an A7 seed (4–15) and a real escrow draw
becomes a numbered deviation** — logged and reported, never silently re-rolled.

*(Adjacency note, non-blocking: 4–15 sits next to Phase-1 {1,2,3}; the author accepted this
over the more-separated 100–111 alternative.)*

## M5 — Verdict bars (FROZEN: none)

- **A7 stays bar-free exploratory.** **No PASS/FAIL bars. No pre-decided numeric consequences.**
- The verdict is the base pre-reg's **frozen fill-in wording only**, reproduced here for custody
  (fill the measured numbers post-run; change no other word):
  > Under benign injected noise (post-hoc, exploratory, one seed per cell), the redesign's
  > false-interrupt rate was [X] and S2's was [Y], by anomaly class [...]. This is an
  > exploratory bound outside the pre-registered confirmatory design; it [does / does not]
  > re-open the self-starvation mechanism of Section 6, and the confirmatory FIR of 0.0
  > remains the noiseless-world figure.
- **Reporting rule (unchanged):** results attach to **Edit 3 ONLY**, labeled post-hoc
  exploratory; the confirmatory FIR (0.0) is **not** altered or restated.
- **Consequence for the execution task's Phase 4:** report the **measured bound + the verdict
  wording**, with **no PASS/FAIL table** — there are no bars to pass or fail.

## M6 — S1 qualification anchor (FROZEN add) + inverted qualification rule (RATIFIED, per-cell)

- **S1 is ADDED as the qualification anchor:** 4 tasks × 3 anomaly classes = **12 runs**, on
  the **same seed block** as M4. Total A7 run count becomes **24 (V2+S2) + 12 (S1) = 36 runs.**
  S1 is the qualification anchor only; it is **not** part of the V2/S2 FIR matrix.

- **Inverted qualification rule — RATIFIED by the author (2026-07-02)** (mirror of fault
  qualification, inverted; D17 "all-QUALIFIED precondition" is the sibling it inverts):

  > **A7 NOISE-QUALIFICATION RULE.** A benign-noise profile *qualifies* for a given cell only
  > if the plain batch baseline **S1 (no monitor) still PASSES its programmatic checker on the
  > clean task under that noise profile**, at the cell's frozen seed. If S1's checker **FAILS**
  > under the noise profile on that cell, the profile is **not benign there — it is a fault,
  > not noise** — and the cell is **DISQUALIFIED**: its V2 and S2 FIR cells are **excluded from
  > the A7 matrix and logged** (cell, profile, seed, checker failure) at full prominence.
  > Qualification is judged on the **S1 anchor only** (category-blind, monitor-independent) and
  > decided **before** the V2/S2 FIR cells for that profile are scored. A disqualified profile
  > is **reported, never silently tuned or re-rolled.**

- **Granularity — RATIFIED PER-CELL (author, 2026-07-02):** an S1 clean failure under a noise
  profile disqualifies **that (task × class) cell only**; the excluded cell is logged; **the
  class survives on the tasks where S1 passes.** A failure never disqualifies a whole class
  across tasks.

## Discrepancy (FROZEN framing): three classes bind; paper prose is consistent

- The **frozen three anomaly classes bind**: transient-500-then-success, latency spike,
  additive schema field. **Do NOT add rate-limit jitter or flaky reads.**
- The paper prose (`paper/fse_focused_v5.tex:922`) lists **four** *illustrative* absent-noise
  examples ("no transient 500s, no rate-limit jitter, no flaky reads, no latency spikes"). The
  A7 design tests **three** (two of that list — transient-500, latency — plus additive-field).
  **Text and design are consistent:** the paper's list is an illustration of *absent* noise,
  not an A7 coverage contract; A7 samples a subset and adds additive-field. A7 makes **no**
  claim to exhaust the illustrative list. (Recorded so the reviewer never reads "4 vs 3" as a
  gap.)

## Metric note (FROZEN): two distinct FIR denominators, never blended

- **A7-FIR** denominator = **interruptible-events** (base A7 pre-reg): `interrupts /
  interruptible-events`, all benign → any interrupt is false.
- **Confirmatory FIR** denominator (`prereg.md` §6.1) = **total interrupts** (interrupts not
  attributable to injection on injected runs; any interrupt on clean runs), divided by total
  interrupts.
- These are **different denominators.** In every A7 output they must be **labeled distinctly**
  (e.g. "A7-FIR (interrupts / interruptible-events)" vs "confirmatory FIR (§6.1)"). Neither is
  ever restated as, blended with, or substituted for the other.

---

## CORRECTION (prominent — needs a numbered deviation at ratification)

**The base A7 pre-reg mis-states one arm's clean FIR.** Its Design line reads: *"Arms:
redesign (V2) and S2 (passive baseline), the two arms with FIR 0.0 in the confirmatory study."*

- **Accurate for V2:** V2's total clean false-interrupts = **0** (`docs/v3_archaeology.md:135`;
  gate `1bKG2` clean median/P95/max FIR = 0).
- **NOT accurate for S2:** S2 is the **naive-interrupt** arm (not "passive"), and it
  **false-fired on 4 clean cells** — **a1 seeds 1/2/3 and d1 seed 1; FIR 1.0** on those cells
  (`docs/v3_archaeology.md:134-135`; corroborated by `paper/fse_focused_v5.tex:633`). S2's
  confirmatory clean FIR is therefore **not 0.0.**
- The **same inaccurate "naive baseline's [clean false-alarm rate of 0]" framing** also appears
  in the paper's Threats setup — the very `[AUTHOR-INPUT: A7]` paragraph (`fse_focused_v5.tex`
  ~lines 923–925) — and in the execution task's own framing. (The paper is internally
  inconsistent: line 633 says S2 raised four clean false alarms; line 634 calls it a "zero
  floor.")

**Why it matters for A7:** for **V2**, A7 tests the intended question — "does a genuinely
FIR-0.0 arm false-fire under benign noise?" For **S2**, the noiseless-clean FIR is **already
nonzero (4 cells)**, so A7's S2 result is a comparison of **noisy-clean FIR vs an already-
nonzero noiseless-clean FIR**, a within-study reference — *not* "does a 0.0 arm break." A7
should still include S2 (per author decision), but described correctly.

**Status / actions (author-directed 2026-07-02 — I did NOT edit the frozen pre-reg or the tex):**
1. **Numbered deviation DRAFTED** for your ratification as **D-A7-1** (proposed number; you
   assign the final one) at `decisions/D-A7-1_deviation_DRAFT_2026-07-02.md`. It corrects the A7
   arm rationale: only V2 is clean-FIR-0.0; S2 is the naive-interrupt arm with clean FIR 1.0 on
   4 cells (a1 s1/s2/s3, d1-s1). **Not yet in `deviations.md`** — the frozen log stays untouched
   until you ratify and place it.
2. **Paper Threats sentence FLAGGED, NOT edited** (you will fix the tex). Exact target:
   `paper/fse_focused_v5.tex` ~line 924 — the clause **"the redesign's clean false-alarm rate of
   0 _and the naive baseline's_"** — "and the naive baseline's" wrongly implies S2's clean
   false-alarm rate is also 0. (Sibling internal inconsistency at lines 633/634.)
3. Keep S2 in A7, described as the naive-interrupt arm with an already-nonzero noiseless
   baseline.

---

## Custody footer

Drafted 2026-07-02; M2/M4/M6 finalized per author decisions 2026-07-02. **No code changed, no
run executed, no spend incurred.** The frozen base pre-reg (`A7_benign_noise_smoke_PREREG.md`)
is **untouched**. **Remaining items that gate the run:** (1) **M3 prediction text** — the author
is writing it directly in this file; (2) the **M1 ratification block** — the author inserts the
real timestamp + commit hash and commits. M2 (cap basis), M4 (seeds 4–15), and M6 (per-cell
qualification rule) are resolved above. On the author's commit, proceed to **Phase 1 (inventory
& plan, no spend)**.
