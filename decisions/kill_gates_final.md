# Kill gates — computed once, complete planned matrix (2026-06-11)

Verbatim output of `make gates` (analysis/gates.py against the committed
195-cell matrix_manifest.json), first and only computation, immediately
after the manifest closed:

```
=== KILL GATES (computed once, on the complete planned matrix) ===
KG1 recall: 35% (>=60%) | categories >=50%: 1/5 (>=4) -> FAIL
KG2 FIR: S5=1.0 S2=0.0 S4=1.0 (S5<=0.5*S2 and S5<=0.7*S4) -> FAIL
KG3 cost: S5 med $1.178952 vs S1 med $0.340831; success S5=4% S1=22%; clean overhead OVER (<=12%) -> FAIL
KG4 vs heartbeat: wasted med S5=15014.0 S3=7950 (>=20% better) | TTD med S5=3 S3=9 (>=2x) -> PASS
Decide within 48 hours of seeing this table; do not negotiate with the data (protocol 6.2).
```

Pre-committed branches (prereg 6.2, frozen before any Phase 1 run):
- KG1 at 35% falls in the "< 40%: kill" branch of the detection claim.
- KG2 FAIL: "Judge adds nothing: reframe as compile-only architecture
  (two tiers), revise paper claims, continue."
- KG3 FAIL: fit the break-even model; if no plausible crossover at
  fan-out <= 8, kill the efficiency claim (correctness claims were KG1's,
  which failed).
- KG4 PASS via the TTD arm: S5 detects 3x faster than the cost-matched
  heartbeat (median 3 vs 9 tool calls) — the surviving claim. The wasted-
  work arm did not pass (S5 median 15014 vs S3 7950 tokens).

Operational close-out: 195/195 manifest cells banked; 220 queue jobs total
(209 done, 11 failed = 9 night-0 checker-crashes + 2 void runs, all with
banked replacement cells); zero throttle backoffs across the entire matrix
(the 5-hour window cap never bound at concurrency 1 — the planned
"nights-only" constraint was unnecessary on this tier); 0 malformed trace
lines; total recorded queue spend $120.05, cumulative project live spend
~ $131 of the $300 envelope.

Flag for the author's audit eye (information, nothing recomputed): S2's
FIR of 0.0 against S5/S4's 1.0 is stark enough to deserve a look during
the protocol 6.1 attribution audit (20% sample + disagreements) before the
decision memo cites it.

The author's pre-committed 48-hour decision window opened when this table
was first displayed (2026-06-11). Per prereg: do not negotiate with the
data.
