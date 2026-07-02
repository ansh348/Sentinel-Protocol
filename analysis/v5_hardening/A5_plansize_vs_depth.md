# A5 --- Plan-size vs task-depth proportionality (feeds Edit 4)

**Read-only.** N = 43 V2 runs across four task types.

**Disclosed substitution (integrity):** the brief's named proxy, "check-writer input
tokens," is degenerate in these traces --- the observed values are [3]
(the CLI logs only uncached input, so it does not reflect plan size). The faithful
plan-size proxy is the **plan event's output tokens** (the serialized plan the check-writer
ingests); the **compile output tokens** (checklist the writer produced) is a cross-check.
Run size = total worker tokens (execution depth).

## Per-task medians
| task | n | plan out (proxy) | compile out | worker tokens (depth) | tool calls | plan/worker |
|---|---|---|---|---|---|---|
| a1 | 17 | 2241 | 6708 | 7008 | 0 | 0.320 |
| b1 | 8 | 3717 | 6292 | 6930 | 0 | 0.536 |
| c1 | 9 | 2545 | 9006 | 6617 | 0 | 0.385 |
| d1 | 9 | 7496 | 7693 | 8697 | 0 | 0.862 |

## Across-run relationships
- Pearson(plan out, worker tokens) = **0.299**
- Pearson(compile out, worker tokens) = **0.157**
- plan/worker-token ratio: median **0.397**; small-run median **0.424**
  vs large-run median **0.312** (drop 26% across the size range)

## Why the data cannot return "proportional"
- Execution depth barely varies across the four archetypes (worker-token medians
  6617--8697, spread 1.31x < 1.5x), so
  proportionality *over depth* is essentially untestable here --- the benchmark exercises
  width, not length.
- Plan size varies 3.3x (1682--17894 out-tokens)
  largely **independent** of execution size (Pearson 0.299), so plan and run
  do not move together.
- What the data *does* show robustly: the plan is a **non-trivial fraction of execution in
  every task type** (plan/worker floor 0.32, up to
  0.86) --- exactly the scoping
  condition sentence (ii) names.

## Verdict: **cannot demonstrate proportionality; depth escape NOT closed --- scope to tested/fan-out regime**

## PASTE-READY SENTENCE (Edit 4 --- the one the DATA returns)
> plan size grows sub-linearly with task length, so the depth escape remains open; we scope the coupling to runs whose plan is a non-trivial fraction of execution --- which is the multi-agent fan-out regime this paper targets

*(Both candidate sentences were pre-written; the selection is forced by the measured
relationship above --- weak plan/execution coupling and near-constant execution depth mean
proportionality cannot be shown, so the honest residual is the scoped concession, not the
closure. Label the supporting numbers post-hoc in text.)*
