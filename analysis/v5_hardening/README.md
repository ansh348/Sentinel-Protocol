# v5 Hardening --- Prompt A outputs (read-only, banked data)

All analyses run over already-banked traces / fitted models. No LLM runs. No banked trace,
verdict, or pre-registration artifact was modified. Each `aX_*.py` computes and writes its
`AX_*.md` (paste-ready) and `aX_*.json` (raw). Numbers here are emitted by the scripts, so
prose matches computation by construction. **Every insertion into the paper is post-hoc and
must be labeled post-hoc.**

## One-line results (feed Prompt B)

- **A1 (Edit 1b) --- bar robustness.** v1 pilot overhead ~246%, v2 confirmatory 55.49%,
  second-family floor +17.1% (cap-6). All three fail the 12% cap. FAIL is invariant to the
  cap: v2 fails any cap <55.5%, the floor fails any cap <17%. → paste sentence in `A1_*.md`.
- **A2 (Edit 1c) --- break-even location.** The pre-committed model does **not** admit a
  positive clean-overhead break-even at the measured fan-out (n0=3): per-replan cost
  \$0.221 > per-run waste gap \$0.068, so even a free monitor is cost-negative until fan-out
  ~10. Nearest meaningful locator (drops replan, generous): a 12% cap breaks even at fault
  rate **p\*≈41%**; at p=5--25% tolerable overhead is 1.5--7.3%. → `A2_*.md` (label post-hoc).
- **A3 (Edit 7) --- waste-parity autopsy.** Frozen 7,008 (V2) vs 6,404 (S3) unchanged. The
  entire mean gap (+807) is bucket (c) **re-dispatch rework** (+1,055 mean; 8/31 cells; S3
  discards nothing). It is NOT sunk cost --- V2 books less pre-fault sunk than S3 (2,278 vs
  2,806). Excluding re-dispatch rework, V2 median falls to **6,117 < 6,404**. → `A3_*.md`.
- **A4 (Edit 8) --- statistics.** Wilson95 LB: 10/15→41.7%, 24/31→60.2%, 12/31→23.7%,
  3/5→23.1%; per-category cells 6/6→60.97%, 3/3→43.85% (match frozen gate). Fisher one-sided:
  transfer 3/5 vs 0/5 **p=0.083** (above .05 → state as directional, n=5); redesign vs S2
  24/31 vs 12/31 **p=0.0021** (significant). → `A4_*.md`.
- **A5 (Edit 4) --- plan-size vs depth.** "Check-writer input tokens" is degenerate (=3;
  CLI logs uncached input only); proxy = plan-event output tokens. Execution depth barely
  varies across archetypes (spread 1.3x) and plan/execution are weakly coupled (Pearson
  0.30), so proportionality is untestable → the honest sentence is (ii): **sub-linear / depth
  escape not closed, scope the coupling to the fan-out regime** (plan is a non-trivial
  0.32--0.86 of execution in every task). → `A5_*.md`.
- **A6 (Edit 8) --- clean-failure gap.** S1 clean 9/12 vs redesign 8/12 (one run). All four
  redesign clean failures at **zero interrupts**; they are worker-deliverable shortfalls
  (missing citations, null fields, validation not run) the no-monitor S1 arm shows too
  (d1 seed s35465 fails identically under both). Monitoring-independent. → `A6_*.md`.
- **A7 / A8 --- NOT RUN.** Spend + author-approval gated. Mini pre-registrations only:
  `A7_benign_noise_smoke_PREREG.md`, `A8_warm_cache_writer_floor_PREREG.md`. A8 gates Edit 2d.

## Files
| analysis | script | paste-ready | raw |
|---|---|---|---|
| A1 bar robustness | a1_bar_robustness.py | A1_bar_robustness.md | a1_bar_robustness.json |
| A2 break-even | a2_breakeven_inversion.py | A2_breakeven_inversion.md | a2_breakeven_inversion.json |
| A3 waste decomposition | a3_waste_decomposition.py | A3_waste_decomposition.md | a3_waste_decomposition.json |
| A4 statistics | a4_statistics.py | A4_statistics.md | a4_statistics.json |
| A5 plan-size vs depth | a5_plansize_vs_depth.py | A5_plansize_vs_depth.md | a5_plansize_vs_depth.json |
| A6 clean-failure gap | a6_clean_failure_gap.py | A6_clean_failure_gap.md | a6_clean_failure_gap.json |
| A7 benign-noise (PREREG only) | --- | A7_benign_noise_smoke_PREREG.md | --- |
| A8 warm-cache floor (PREREG only) | --- | A8_warm_cache_writer_floor_PREREG.md | --- |

Reproduce: `python analysis/v5_hardening/aN_*.py` (uses only banked inputs under `runs/`).
