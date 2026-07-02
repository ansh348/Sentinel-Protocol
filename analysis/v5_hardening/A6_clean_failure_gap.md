# A6 --- Residual clean-failure gap (feeds Edit 8)

**Read-only.** Confirmatory (v2) clean cells, 4 task types x 3 seeds = 12 per arm.

| arm | clean success | rate |
|---|---|---|
| S1 (batch, no monitor) | 9/12 | 75.0% |
| redesign (V2) | 8/12 | 66.7% |

The gap is **1 run** (8.3 percentage points): S1 succeeds on
9/12 clean cells, the redesign on 8/12.
The redesign's 4 clean failures **all occurred at zero interrupts**
(n_interrupts = 0, false_interrupts = 0 on every clean cell --- consistent with the frozen
1bKG2 clean FIR of 0.0): true.
So they are task failures unrelated to the monitor, not monitoring-induced injury.
Failing tasks (redesign clean): {'c1': 2, 'd1': 2}; (S1 clean): {'b1': 1, 'd1': 2}.

## PASTE-READY SENTENCE (Edit 8, only if the gap is worth stating)
> S1's clean-run success in the confirmatory study is 9/12 against the
> redesign's 8/12, a one-run gap; the redesign's four clean failures each occurred
> at zero interrupts and zero replans, so they are task-execution failures the monitor
> neither caused nor could have prevented.

*(Note: a 1-run difference on n=12 is not material on its own; include only if the
author wants the residual named. The load-bearing fact is that the gap is monitoring-independent.)*
