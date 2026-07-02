# A7b — A7-family close: MINI PRE-REGISTRATION (FINAL — awaiting author ratification)

**STATUS: FINAL (predictions frozen; seeds 16–19 confirmed; arm-(b) target-surface selection rule
pinned — 2026-07-03). NOT RATIFIED, NOT RUN — awaiting only the author's timestamp-commit.** Same
template as the A7 base pre-reg. Two targeted follow-ups that close the two open questions A7 left.
**A7b CLOSES the A7 family — no further probes after this.** Author ratifies and timestamp-commits
this pre-reg before any run.

**RATIFIED by the author on 2026-07-03T02:29:30+0530**, before any run. Ratified by the author via
explicit recorded instruction; commit executed by the assistant on the author's authorization;
hash backfilled in follow-up. Ratifying commit: **[POST-COMMIT BLANK — backfilled after the
commit]**.

## Motivation
A7 (2026-07-03) found: (1) its nonzero mechanical false-interrupts were **task-intrinsic**, not
noise-attributable, and are **confounded by CLI 2.1.198 vs the frozen 2.1.170** with no within-run
noiseless control (D37); (2) the transient-500 landed on `/auth/token`, a surface V2 does not
compile a probe for, so **the status fast path was never tested by the noise**. A7b runs the two
controls that resolve these, then the A7 family is closed.

## Design (frozen before any run)
- **Arm (a) — NOISELESS CONTROL.** V2 on **a1, b1, c1**, **noise OFF** (`noise_profile=None`), CLI
  2.1.198, at the **seeds matching the A7 V2 cells** (a1: 4,5,6; b1: 7,8,9; c1: 10,11,12 — the same
  9 V2 seed-points, run clean). **Question:** do A7's task-intrinsic interrupts (V2 a1's mass
  `/shipping/rates` + `/inventory/items` escalations; c1's `/docs/search` escalation) **reproduce
  without noise**? Reproduce ⇒ confirmed task/CLI-intrinsic (A7's nonzero FIR is NOT noise).
  Vanish ⇒ they were noise-caused after all.
  - *Cells:* 9 (a1/b1/c1 × 3 seeds). Flag-off is byte-identical to Phase 1, so this arm needs no
    new build — it is the existing V2 path with `noise_profile=None`.
- **Arm (b) — MONITORED-SURFACE TRANSIENT-500.** V2, **3–4 cells**, transient-500 placed on a
  surface **V2 compiles a probe for** (a load-bearing plan surface — e.g. `/inventory/items` or
  `/pricing/quote/{sku}` for a1, verified from the A7 armed-probe set), the 500 **heals on retry**.
  **Question:** does V2's **status fast path INTERRUPT** on a transient-500-that-heals when the 500
  lands **on a monitored surface** (the test A7's `/auth/token` landing could not run)?
  - *Target-surface selection rule (frozen, non-discretionary):* the target surface is pinned in
    A7b Phase 2 to **the most-frequently-armed load-bearing surface in the A7 armed-probe evidence**
    for the task — by this rule, never by discretionary choice; the selected surface and its
    supporting armed-probe counts are logged in the A7b Phase-2 note.
  - *Build (A7b Phase 2, offline, gated):* `transient_500` gains an optional **target-surface param**
    so the 500 lands on a named monitored surface instead of the first worker call. Default = current
    first-call behavior ⇒ **flag-off + existing A7 configs byte-identical**; validated by the banked
    replay before any A7b run.
  - *Cells:* 3–4 (**a1 × seeds 16–19, confirmed**; 500 on a1's
    monitored surface). Seeds disjoint from A7 (4–15) and all other namespaces; escrow-disjointness
    by the same inference basis as A7's M4 (observed escrow ≥ 2594; any collision → numbered deviation).

- **Metric:** the A7-FIR (interrupts / interruptible-events; §6.1-distinct), with per-interrupt
  **attribution from the trace evidence** (which surface fired) — the same read A7 used.
- **Spend cap (hard):** **$8.00** modeled `total_cost_usd`. Abort and report partial if reached; no
  verdict on a truncated matrix. (Est.: 9 + 4 = 13 V2 cells × ~$0.3 ≈ $4 — the cap is headroom.)

## Pre-registered prediction

Provenance: author's bets elicited in conversation 2026-07-03; prose drafted by an AI
assistant and ratified verbatim by the author at signing; frozen before any A7b run; no A7b
data existed at freeze time. Informed by the A7 results (which motivated both arms).

Arm (a), noiseless control: PREDICT the task-intrinsic interrupts REPRODUCE without noise on
at least one of a1/c1, i.e. V2's clean FIR is not 0 at these seeds on CLI 2.1.198. Mechanism:
A7's V2 firings were identical across noise classes (same probes, same surfaces), which is
evidence the noise was not the cause. If correct, the confirmatory clean FIR of 0.0 is specific
to seeds 1-3 and/or CLI 2.1.170 and does not generalize; the Threats paragraph will say so.

Arm (b), monitored-surface transient-500: PREDICT the status fast path FIRES (interrupt before
the healing retry is observed) in most or all cells. Mechanism: unchanged from A7's M3 - status
>= 400 interrupts without a confirming probe, 500 is not excluded, no heal-on-retry rule exists.
This is the original M3 bet, now placed on a surface the monitor actually watches.

## Verdict wording (frozen; fill the measured result post-run)
> A7b (post-hoc, exploratory, closing the A7 family). Noiseless control: the A7 task-intrinsic
> interrupts **[did / did not]** reproduce with noise off on CLI 2.1.198, so A7's nonzero
> false-interrupts **[are / are not]** attributable to task/CLI rather than the injected noise.
> Monitored-surface transient-500: V2's status fast path **[did / did not]** interrupt on a
> transient-500-that-heals placed on a compiled-probe surface, so the fast path **[is / is not]**
> fragile to a benign, self-healing transient. This closes the A7 family; the confirmatory FIR of
> 0.0 remains the noiseless-world figure and is unchanged.

## Reporting rule
Results attach as the **CLOSING SECTION of the A7 report**
(`A7_PHASE3_4_RESULTS_2026-07-03.md`), labeled post-hoc exploratory. **A7b closes the A7 family —
no further probes.** The confirmatory FIR (0.0) is not altered or restated.

## Custody
Scaffold drafted 2026-07-03 by the assistant at author direction. Open author-authored fields:
the prediction block, the arm-(b) seed sign-off, and the M1-style ratification (timestamp + commit)
above. The author ratifies + timestamp-commits before any A7b run; the assistant does not commit or
timestamp on the author's behalf. Spend cap $8; no metered run until ratified.
