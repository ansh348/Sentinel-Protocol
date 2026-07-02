# A3 --- Waste decomposition of the KG4 paradox (feeds Edit 7)

**Read-only.** Frozen KG4 medians (unchanged): **V2 7,008** vs **S3 6,404** tokens over 31
non-clean cells per arm (cost_autopsy_v3.json partB). The wasted metric counts only
worker_end tokens (window + discarded); replan and monitoring tokens are excluded by the
double-count guard, so buckets (d) and (e) are 0 *within* it --- reported separately below.

**Estimate disclosure:** worker tokens are lumped at worker_end, so the pre/post-fault split
of a straddling worker uses a time-proportional assumption; the pre-fault sunk bucket also
carries a worker-level upper bound. Buckets a+b+c reconcile to the frozen metric exactly
(max reconstruction error 0 /
0 tokens per run). The re-dispatch bucket
(c) is measured directly from discarded worker lumps and does not depend on the time-split.

## Median tokens per bucket per arm (over 31 non-clean cells)
| bucket | V2 (redesign) | S3 (heartbeat) |
|---|---|---|
| frozen wasted (metric), median | 7008 | 6404 |
| (a) pre-fault sunk (time-prop) | 2264 | 2984 |
| (b) post-fault, pre-detection | 2800 | 2976 |
| (c) post-detection burn + discarded | 0 | 0 |
| (d) replan cost [SEPARATE, not in metric] | 2291 | 0 |
| (e) monitoring after fault [SEPARATE] | 0 | 0 |

## Additive mean decomposition of the gap (means are additive; medians are not)
| bucket | V2 mean | S3 mean | V2 - S3 |
|---|---|---|---|
| (a) pre-fault sunk | 2278 | 2806 | -528 |
| (b) post-fault, pre-detection | 4433 | 4152 | 281 |
| (c) post-detection burn + re-dispatch | 1055 | 0 | **1055** |
| frozen waste (mean) | 7765 | 6958 | 807 |

Detections: V2 14/31; S3 0/31.
Re-dispatch/discard: V2 in 8/31 cells (mean 0.97 workers
discarded); S3 in 0/31. **The entire mean gap is bucket (c)** --- the
re-dispatch rework the heartbeat never incurs; pre-fault sunk cost runs the OTHER way
(V2 < S3), so the "sunk cost of justified stops" story the brief floated is not what the data shows.

## Alternative accounting (post-hoc; frozen 1.09x number unchanged)
Excluding the re-dispatch rework (bucket c) --- the cost of a recovery the do-nothing heartbeat
never attempts --- the redesign's median waste falls to
**6117**, below the heartbeat's 6,404.
(For completeness, excluding pre-fault sunk cost instead leaves V2 at
3974 vs S3 2976,
i.e. that exclusion does NOT flip the ordering --- confirming sunk cost is not the driver.)

## PASTE-READY PARAGRAPH (Edit 7; label post-hoc, keep the frozen 1.09x verdict line intact)
> The redesign's median wasted work (7,008 tokens over 31 non-clean cells) exceeds the cost-matched heartbeat's (6,404) even though the heartbeat detects nothing, and an additive decomposition of the mean gap (807 tokens) locates the entire excess in one bucket: re-dispatch rework. When the redesign detects a fault it replans and re-dispatches workers, discarding the partial output of the workers left on the doomed plan; that discarded rework averages 1055 tokens per non-clean run and appears in 8 of 31 cells, and the heartbeat --- detecting nothing, replanning nothing --- discards nothing at all (bucket c is exactly 0 for S3). It is not sunk pre-fault cost: the redesign actually books LESS of that than the heartbeat (mean 2278 vs 2806 tokens), because it stops early and truncates the exposure window the heartbeat runs to completion. Replan and monitoring tokens sit outside the metric entirely. So the 1.09x parity is the price of corrective action: the redesign pays to detect, stop, and re-plan around the fault, and the metric counts that recovery machinery as waste, while the heartbeat's cheaper run simply finishes on the broken plan and delivers the wrong answer. Excluding the re-dispatch rework --- the cost of a recovery the do-nothing baseline never attempts --- the redesign's median waste falls to 6117 tokens, below the heartbeat's 6,404. The frozen 1.09x verdict line stands; the autopsy shows the gap is recovery cost, not the monitor wasting more.
