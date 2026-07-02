# A7 — Phase 3 (run) + Phase 4 (verdict) results

**Post-hoc exploratory robustness probe under its own mini pre-registration
(`A7_benign_noise_smoke_ADDENDUM_2026-07-02.md`, ratified in checkpoint `7a3807fe`). Attaches
to Edit 3 ONLY. The confirmatory FIR of 0.0 is the noiseless-world figure and is NOT altered.**

## Run summary
- **Matrix COMPLETE**: 36/36 jobs. **Total modeled cost $8.7475** — the $15 cap was **not** bound.
- **Run date 2026-07-03**, ratification 2026-07-02 (before-the-run ordering holds). **CLI 2.1.198.**
- Frozen run-order honored (S1 qual → transient → additive → latency); per-cell M6 gate applied.
- Execution note: the initial background run was **killed by the D-V3-1 short leash** after 14
  cells; resumed cleanly from the ledger in **foreground chunks** (author's original instruction).
  No data lost (append-only ledger); one orphaned worker self-exited.

## S1 qualification (per-cell M6 gate)
a1, b1, c1 **PASS** under all three noise classes → qualified. **d1 FAILS under all three →
disqualified** (6 FIR cells excluded). **Confound (flagged, not a rule change):** d1's S1 fails
~2/3 of the time even *noiseless* (A6: S1 clean {b1:1, d1:2}), so d1's disqualification reflects
d1's task-flakiness, **not** evidence the noise is non-benign. The frozen M6 rule is mechanical
(S1 fails → disqualify) and is applied as written.

## A7-FIR TABLE (computed once; `analysis/v5_hardening/a7_fir.py`)
"Interrupt" = `run_end.replans` (disruptive orchestrator interrupts); on a clean run every
interrupt is false. `esc`=worker escalations, `intEv`=orchestrator interrupt-events,
`land`=transient-500 landing call. A7-FIR denominator = interruptible-events (one qualified cell
= one event); **distinct from prereg §6.1 FIR (denominator = total interrupts).**

```
  arm class           task seed FIR esc intEv pause dis grind  ok    land
  -----------------------------------------------------------------------
  V2  transient_500   a1   4      0   0     0     0   0 False   N   token
  V2  transient_500   b1   7      0   0     0     0   0 False   Y   token
  V2  transient_500   c1   10     1   0     1     1   0 False   N   token
  V2  additive_field  a1   6      1   0     2     2   0 False   Y
  V2  additive_field  b1   9      0   0     0     0   0 False   Y
  V2  additive_field  c1   12     0   0     0     0   0 False   Y
  V2  latency_spike   a1   5      1   0     1     1   0 False   Y
  V2  latency_spike   b1   8      0   0     0     0   0 False   Y
  V2  latency_spike   c1   11     0   0     1     1   0 False   Y
  S2  transient_500   a1   4      0   0     0     0   0 False   N   token
  S2  transient_500   b1   7      0   0     0     0   0 False   Y surface
  S2  transient_500   c1   10     0   1     1     0   1 False   N   token
  S2  additive_field  a1   6      0   0     0     0   0 False   Y
  S2  additive_field  b1   9      0   0     0     0   0 False   Y
  S2  additive_field  c1   12     0   0     0     0   0 False   Y
  S2  latency_spike   a1   5      0   0     0     0   0 False   Y
  S2  latency_spike   b1   8      0   0     0     0   0 False   Y
  S2  latency_spike   c1   11     1   3     3     1   2 False   Y

  distribution  V2: n=9 median=0 P95=1 max=1 total_replans=3 grind_deaths=0
  distribution  S2: n=9 median=0 P95=1 max=1 total_replans=1 grind_deaths=0
  clean success under A7 noise:  V2 7/9 (77.8%)   S2 7/9 (77.8%)
  noise-free reference: V2 clean 8/12 (66.7%, A6)
```

## Noise-ATTRIBUTION (the decisive read — evidence in `a7_fir_evidence.py`)
The nonzero raw interrupts are **task-intrinsic, not noise-caused**:
- **V2 c1** interrupts on `/docs/search` under **both** transient and latency (identical) → c1 task
  behavior, not the noise class.
- **V2 a1** fires the **same mass `/shipping/rates/*` + `/inventory/items/*` coverage/relation
  escalations** under **both** additive and latency (identical) → a1 task behavior, not the noise.
- **The transient-500 landed on `/auth/token` in every cell** — a surface V2's compiled probes do
  NOT monitor — so **V2's status fast path never engaged the 500** (the M3 "load-bearing"
  prediction was untestable as designed).
- **S2 c1 transient**: the worker DID escalate on the 500 (noise-attributable) → orchestrator
  **DISMISSED** it ("transient upstream… retry"), **0 disruption**. S2 c1 latency's escalations
  were `content`/`body` schema confusion (task-intrinsic), mostly dismissed.
- **0 grind-deaths; no self-starvation** (§6): no cell shows a false alarm consuming the budget a
  later look needed. The one V2 fail-with-replan (c1 transient) replanned on the `/docs/search`
  probe, not the noise.

**Net: ~0 false interrupts are attributable to the benign noise.** The mechanical FIR is nonzero
but task-intrinsic, and is **confounded by CLI 2.1.198 ≠ the frozen 2.1.170 baseline** with no
within-run noise-free 2.1.198 control to separate noise effect from version effect.

## M3 PREDICTION vs MEASURED (per class)
| class | arm | M3 prediction | measured | verdict |
|---|---|---|---|---|
| transient-500 | V2 | NONZERO, "most/all fire" (status fast path on 500) | fast path **never engaged** — 500 landed on unmonitored `/auth/token`; 1 replan was a `/docs/search` probe | **not borne out** (untestable as designed) |
| transient-500 | S2 | worst class (raw anomaly escalated) | 1 escalation on the 500 → **dismissed**, 0 disruption | partly: S2 *did* react, but dismissal caught it |
| additive-field | V2 | FIR 0 | 1 replan, but task-intrinsic (shipping/inventory coverage) | measured>0 mechanically, **0 noise-attributable** |
| additive-field | S2 | moderate | **0** | lower than predicted |
| latency-spike | V2 | ~0 (no probe targets time) | 1 replan, task-intrinsic; no elapsed_ms probe fired | ~0 noise-attributable (consistent) |
| latency-spike | S2 | lowest class | **highest** S2 class (3 esc, 1 replan) — but `content`/`body` task confusion, not latency | **not borne out** (task-intrinsic) |

## FROZEN VERDICT WORDING (filled; frozen skeleton unchanged)
> Under benign injected noise (post-hoc, exploratory, one seed per cell), the redesign's
> false-interrupt rate was **3 disruptive interrupts across 9 cells (median 0, max 1), of which 0
> are attributable to the noise** and S2's was **1 across 9 cells (median 0, max 1), the single
> noise-triggered escalation dismissed without disruption**, by anomaly class **[transient-500:
> V2 fast path never engaged — the 500 landed on the unmonitored /auth/token surface; S2 escalated
> and was dismissed; additive/latency: no noise-attributable interrupts]**. This is an exploratory
> bound outside the pre-registered confirmatory design; it **does not** re-open the
> self-starvation mechanism of Section 6 (0 grind-deaths, no starved look), and the confirmatory
> FIR of 0.0 remains the noiseless-world figure.

## Draft Threats replacement paragraph (DO NOT APPLY — for author review)
Replaces the `[AUTHOR-INPUT: A7]` placeholder at `fse_focused_v5.tex` ~line 935:

> A post-hoc benign-noise probe (A7, pre-registered separately, one seed per cell) injected three
> recoverable non-fault anomalies — a transient 500-then-success, an elevated-latency value, and a
> backward-compatible extra field — into the redesign and the naive baseline on clean tasks. Across
> the qualified cells the redesign incurred three disruptive interrupts and the naive baseline one,
> **none attributable to the injected noise**: every observed interrupt was a task-intrinsic monitor
> or worker behavior (coverage and relation probes, a document-schema confusion), and the single
> noise-triggered escalation — the naive baseline reacting to the transient 500 — was correctly
> dismissed. No run suffered a grind-death, so the probe **does not** re-open the Section~6
> self-starvation mechanism. Two limitations bound this reading: the transient 500 landed on the
> authentication call, a surface the redesign does not compile a probe for, so its status fast path
> was never exercised by the noise; and the probe ran on a newer CLI than the frozen confirmatory
> pin, with no within-run noiseless control, so it cannot separate a noise effect from a
> version effect. The confirmatory false-alarm rate of 0 therefore remains the noiseless-world
> figure and an upper bound; the deployment bound under real noise is **not tightly established** by
> this exploratory probe, and a monitored-surface noise placement plus a same-CLI noiseless control
> are the obvious next steps.

## Departure notes (carry into the record; NOT numbered deviations unless you rule so)
1. **CLI 2.1.198 vs frozen 2.1.170** (auto-updater drift, D21 class): A7 ran on the current CLI;
   confounds the A7↔confirmatory comparison. Recommend logging as a numbered deviation.
2. **Combined-checkpoint ratification** (`7a3807fe`) — carried forward from the Phase-2 note.
3. **Background-leash + foreground-resume** (D-V3-1 confirmed): the run was executed in foreground
   chunks after the background job was leash-killed at cell 14; resume ledger recovered cleanly.
4. **Transient-500 landing limitation**: the "first worker call" 500 lands on `/auth/token`, off
   V2's compiled surfaces — the transient class did not test the fast path. Design limitation of
   the noise mechanism, not a monitor result.
5. **d1 disqualification confound** and **single seed per cell** (exploratory, per the frozen design).
```
