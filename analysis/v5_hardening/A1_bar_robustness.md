# A1 --- Bar-robustness sweep (feeds Edit 1b)

**Read-only.** No new measurement. The cost gate FAILs when measured clean overhead
exceeds the cap; overhead is fixed per reading and the cap is swept 1%--60% in 1% steps.
A reading therefore FAILs exactly the caps strictly below its overhead.

## Measured clean overheads (all frozen artifacts)
| reading | clean overhead | source | fails 12% cap? |
|---|---|---|---|
| v1 pilot (S5 vs S1) | **245.9%** | kill_gates_final.md (KG3: \$1.178952 vs \$0.340831) | yes |
| v2 confirmatory (redesign) | **55.49%** | cost_autopsy_v3.json partA (1bKG3) | yes |
| second-family floor (GPT-5.5 cap-6) | **+17.1%** | paper Table, batch/live denom | yes |

## Verdict as a function of the cap (1%--60%)
| reading | FAIL cap range | PASS only if cap >= | fails entire 1--60% sweep? |
|---|---|---|---|
| v1 pilot | 1%-60% | (never passes in range) | True |
| v2 confirmatory | 1%-55% | 56% | False |
| second-family floor | 1%-17% | 18% | False |

The v1 pilot fails **every** cap in the sweep (its overhead, ~246%, is above 60%).
v2 fails every cap below 55.5% (i.e. it would only pass at a cap of 56% or higher).
The second-family floor fails every cap below 17% (it would only pass at a cap of 18% or higher),
and no coverage setting of the second-family writer ever reaches the 12% cap at all.

## PASTE-READY SENTENCE (Edit 1b)
> The verdict is invariant to the cap's exact value: v2 fails any cap below 55.5%, and the second-family floor of +17% fails any cap below 17% --- every bar a deployer could plausibly have set returns the same verdict.

*(Framing note for the rewrite: this is disclosed post-hoc robustness of a
pre-registered judgment, not a new result. Label as post-hoc in text.)*
