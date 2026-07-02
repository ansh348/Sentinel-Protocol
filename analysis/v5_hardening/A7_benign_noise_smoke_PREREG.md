# A7 --- Benign-noise smoke test: MINI PRE-REGISTRATION (NOT YET RUN)

**STATUS: NOT RUN. Awaiting explicit author go-ahead + spend authorization.**
Per the brief, this probe requires: (1) explicit author approval, (2) this one-page
pre-registration committed with a timestamp *before any run*. Nothing here has been
executed; no LLM calls were made; no trace was written. This file is the pre-commitment
artifact only.

`[AUTHOR-INPUT: approve/deny A7; if approved, ratify this pre-reg and commit it with a
real timestamp BEFORE the first run.]`

---

## Motivation
The mock world generates no benign anomalies (Edit 3 / noiseless-world asymmetry). The
frozen false-interrupt rate of 0.0 (redesign and S2) is therefore an upper bound measured
in the most favorable noise environment. A7 measures whether the monitor false-fires when
benign, recoverable, non-fault anomalies are present --- a post-hoc exploratory bound on
deployment behavior, NOT a confirmatory result.

## Design (frozen before any run)
- **Arms:** redesign (V2) and S2 (passive baseline), the two arms with FIR 0.0 in the
  confirmatory study.
- **Tasks:** the four clean task types (a1, b1, c1, d1), one seed each per anomaly class.
- **Anomaly classes (benign; none is a real fault, none should be interrupted):**
  1. **Transient 500-then-success:** the first call to one surface returns HTTP 500, a
     retry succeeds. No state is corrupted; the deliverable is unaffected.
  2. **Latency spike:** one surface responds after an elevated delay; the response is
     otherwise correct.
  3. **Additive schema field:** a response gains one extra, unused field; all required
     fields are present and correct (a backward-compatible addition).
- **Cells:** 2 arms x 4 tasks x 3 anomaly classes = 24 runs (one seed per cell).
- **Metric:** false-interrupt rate (FIR) per arm per anomaly class = interrupts /
  interruptible-events, all of which are benign here, so any interrupt is false.
- **Spend cap (hard):** `[AUTHOR-INPUT: confirm cap; brief suggests ~$5--15]`. Abort the
  run if the cap is reached; report partial results labeled as such.

## Pre-registered prediction
`[AUTHOR-INPUT: record the author's predicted FIR per class before running, e.g. "we expect
FIR ~0 on the additive-field class (schema probes are equality-on-required-fields, not
closed-world) and non-zero FIR on transient-500 and latency classes if the compiled probes
treat a single 500/timeout as a surface fault."]`

## Verdict wording (frozen; fill the measured numbers post-run)
> Under benign injected noise (post-hoc, exploratory, one seed per cell), the redesign's
> false-interrupt rate was [X] and S2's was [Y], by anomaly class [...]. This is an
> exploratory bound outside the pre-registered confirmatory design; it [does / does not]
> re-open the self-starvation mechanism of Section 6, and the confirmatory FIR of 0.0
> remains the noiseless-world figure.

## Reporting rule
Results attach to Edit 3 ONLY, labeled "post-hoc exploratory robustness probe under its own
mini pre-registration." The frozen confirmatory FIR (0.0) is not altered or restated.
