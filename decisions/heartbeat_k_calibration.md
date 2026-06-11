# Heartbeat-k calibration (protocol 5.1) — from S5 seed-1, before any S3 run

Recorded 2026-06-11, immediately after the S5 seed-1 drain (queue jobs
45-57) and BEFORE any S3 cell was enqueued. Method follows
`conductor/calibrate_k.py`: k = ceil(worker_calls / n_revals) with
n_revals = round(sentinel_overhead / revalidation_turn_cost).

**Source-run choice (implementation note, recorded a priori to S3):**
protocol 5.1 says k is "calibrated after S5's first seed" without pinning
which run per task. Applied choice: the per-task MEAN over ALL of that
task's S5 seed-1 runs (clean + injected) for overhead, revalidation-turn
cost (mean orchestrator-turn cost), and worker calls — the literal "first
seed", no cherry-picking. The clean-run-only variant is recorded alongside
for comparison. Where S5's seed-1 overhead was inflated by NOISE grinds,
cost-matching hands S3 the same budget — conservative in the baseline's
favor, per the M4 condition-2 principle already on record.

| task | mean overhead | mean reval cost | mean calls | n_revals | **k (applied)** | clean-only k |
|---|---|---|---|---|---|---|
| a1 | $0.523 | $0.028 | 36.0 | 19 | **2** | 3 |
| b1 | $0.349 | $0.058 | 125.3 | 6 | **21** | 64 |
| c1 | $0.461 | $0.056 | 25.0 | 8 | **4** | 4 |
| d1 | $0.672 | $0.090 | 30.0 | 7 | **5** | 3 |

Notes: a1's overhead includes two escalation-cap grinds (53 judge calls
each) and b1's mean calls include a 320-call clean-run worker grind — both
honest S5 seed-1 behavior under the pre-registered caps; the mean-based k
therefore over-budgets S3 exactly where S5 burned most (baseline's favor).
Source data: runs of jobs 45-57; per-run numbers in the S5 seed-1 ops
extract (session record, 2026-06-11).
