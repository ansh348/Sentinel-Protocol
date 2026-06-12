# Phase 1b Pre-registration — FROZEN

**Status: FROZEN 2026-06-12.** Author rulings on AUTHOR-1..15 received and
recorded inline 2026-06-12 (ratification message, A.M.); the AUTHOR-8
ex-ante recovery-class manifest CONFIRMED as drafted 2026-06-12, with the
author's PERMISSION_AUTH categorical-basis ruling recorded beside §3a.
**The commit of this revision constitutes the author's ratification
signature** (§7; the memo's signature-clause pattern). Changes hereafter
only via numbered deviations (next: D23). Assembled 2026-06-12 by
transcription from the records of
ratification; nothing in this document originates with the assembler. Every
clause carries a provenance pointer (file § / commit). Sources of record:
decisions/decision_memo_phase1.md §4–§7 (e808862, signed within the 48-hour
window); decisions/phase1b_precommitments.md P1–P3 + RATIFIED VALUES
(structure 823549e, committed before any battery result; values appended and
ratified at e808862 per the memo's signature clause);
sentinel_protocol_v6_1.md §11.9 (as amended), §11.10–§11.11 (cabf760);
benchmark/holdouts/RESOURCE_BUDGET.md and DEPENDENCY_VERSION.md (qualified
specs, 124ab99/6729e1b/cf23819);
decisions/holdout_qualification_2026-06-12.md incl. Appendix 2;
decisions/holdout_escrow_record.md (4597a64, receipt 4b1634d);
analysis/archaeology_v2.md (508772f); prereg.md (Phase 1, structural
inheritance); RUNBOOK.md; deviations.md.

Upon ratification (§7), this document is FROZEN by commit; thereafter
changes only via numbered deviations (next: **D23**, per memo §7).

---

## [AUTHOR RATIFICATION REQUIRED]

Every parameter below is underdetermined by the records of ratification.
Per the assembly rule (transcribe, never invent), none is resolved in the
body of this document; each carries a proposed default, a one-line
rationale, and provenance. **The freeze commit may occur only after the
author rules on each item; rulings are recorded inline here (pattern:
"Ratified: …, A.M.", per memo §4) before the FROZEN stamp.**

**RULINGS RECORD (2026-06-12, ratification message, A.M.):** defaults
ACCEPTED on AUTHOR-1(a), 2, 3, 5, 6, 9, 10(i)+(ii), 11, 12, 13, 14, 15 —
with amendments on 4, 5, and 12 recorded inline below; AUTHOR-7 OVERRIDDEN
to option (b) with the author's recorded rationale; AUTHOR-8 resolved by
manifest-plus-confirmation procedure (label manifest drafted and presented
to the author; FROZEN stamp gated on the author's confirmation message).
Each per-item ruling is recorded beside its item.
**CONFIRMATION (2026-06-12, A.M.):** the nine-row AUTHOR-8 manifest is
CONFIRMED as drafted, including pair 8's recorded caveat (§3a verbatim);
the PERMISSION_AUTH categorical-basis question is RULED (recorded beside
§3a). All fifteen items closed; this revision is the freeze.

**[AUTHOR-1] Category-gate denominator: 5 or 7 categories.**
The inherited clause "≥50% in ≥4/5 categories" (prereg 6.2 KG1 via P1)
predates the held-out categories; the ratified 1bKG1 text quotes it
verbatim *and* separately places the holdouts "inside the recall
denominator" (memo §4). Two readings:
  (a) **PROPOSED DEFAULT — categorical hard clause stays over the original
      five categories** (API_SURFACE, SCHEMA_DRIFT, PERMISSION_AUTH,
      TOOL_CONTRACT, RETRIEVAL_INTEGRITY); the two holdout categories count
      inside the overall ≥60% recall gate and are reported per-category
      with Wilson lower bounds, descriptive only where n<3 — exactly the
      ratified sentence structure read literally.
  (b) A 7-category restatement (e.g. ≥50% in ≥5/7 or ≥6/7).
Rationale for (a): P1 forbids inventing thresholds at freeze time
("inherits v1's pre-verdict thresholds verbatim for all shared quantities";
no quantity may derive from anything the battery reported) — any 7-category
fraction would be a new number chosen today, after the holdout results'
shape is partially known (qualification hosts, n per category); and G13
("category clause unstable at small n", HOLDS by arithmetic) cuts hardest
at the holdouts' n. Option (a) is the only reading that adds zero new
threshold content. Provenance: phase1b_precommitments.md P1 + RATIFIED
VALUES 1bKG1; decision_memo_phase1.md §4; archaeology_v2.md G13.
**Ruling (2026-06-12, A.M.): option (a) RATIFIED** — categorical hard
clause over the original five; holdouts inside overall recall, Wilson-
bounded reporting, descriptive where n<3.

**[AUTHOR-2] Matrix shape: seeds per cell, clean-cell coverage, cell count.**
v6.1 §11.10 fixes arms, categories, and anti-overfit structure but not the
seed count or totals. PROPOSED DEFAULT: 3 seeds per (task, variant) for
original-category and clean cells (Phase 1 structural inheritance,
prereg/pilot_protocol §5); clean cells for every arm (4 tasks × 3 seeds);
with AUTHOR-3/AUTHOR-4 defaults this yields per arm 27 original-injected +
10 holdout + 12 clean = 49 cells, × 5 arms = **245 cells**. Rationale: the
only committed precedent for every structural choice is the Phase 1 matrix;
nothing in the ratified record licenses a different seed count.
Provenance: v6.1 §11.6 (13 variants × 5 systems × 3 seeds); prereg.md;
pilot_protocol.md §5.
**Ruling (2026-06-12, A.M.): DEFAULT RATIFIED** — 3 seeds, clean cells for
every arm, 49 cells per arm, 245 cells total.

**[AUTHOR-3] Holdout consumption from the 40-cell escrow superset.**
The superset (4 tasks × 5 seeds × 2 categories) deliberately exceeds what
the matrix uses; the escrow record says the matrix "consumes the qualified
(task, category) pairs drawn from within" without fixing seeds-per-pair.
PROPOSED DEFAULT: the two qualified primary-host pairs only —
RESOURCE_BUDGET on a1, DEPENDENCY_VERSION on b1 — each consuming **all 5
escrowed seeds** (10 holdout cells; drawn values shared across arms, as
Phase 1 injections were identical across systems). Rationale:
qualification verdicts attach to primary hosts only, and 5 seeds gives each
holdout category n=5, the largest n the sealed draw permits under the
Wilson/small-n clause without touching unqualified combinations (e.g. c1's
recorded-weak DV wound). Provenance: holdout_escrow_record.md (superset
shape + consumption clause); holdout_qualification_2026-06-12.md (verdicts
attach to a1/b1); RATIFIED VALUES 1bKG1 (Wilson, n<3 descriptive).
**Ruling (2026-06-12, A.M.): DEFAULT RATIFIED** — RB-a1 and DV-b1 only,
all 5 escrowed seeds each.

**[AUTHOR-4] Exploratory rebuilt-judge arm scope.**
P3 designates the arm exploratory but not its size. PROPOSED DEFAULT: full
parity with the primary arm (all 49 cells under AUTHOR-2/3 defaults), so
the two-tier-vs-judge comparison v6.1 §11.9 #6 promises is computable on
the same denominator — confirmatory claims still attach to the two-tier arm
only (P3; no post-selection). Alternative if cost binds: Phase 1's
exploratory convention (1 seed, injected pairs only, excluded from gate
math; pilot_protocol §5). Provenance: phase1b_precommitments.md P3;
decision_memo_phase1.md §2 (KG2 branch); v6.1 §11.9 amendment #6.
**Ruling (2026-06-12, A.M.): full-parity judge arm RATIFIED, with a
pre-committed descope order** — if the AUTHOR-14 cost cap binds
mid-matrix, the exploratory rebuilt-judge arm descopes FIRST (to
injected-only, then out entirely); the confirmatory arms and baselines
(two-tier v2, S1, S2, S3) are never descoped.

**[AUTHOR-5] Fresh-draw mechanism and custody for the ORIGINAL five
categories (fire counters, payload parameters, run seeds).**
§11.10 item 3 mandates "injection fire-counters re-drawn from fresh seeds;
payload parameters varied; v2 designers do not see the drawn values before
freeze" — and fixes no mechanism. PROPOSED DEFAULT, mirroring the only
in-repo precedent (the holdout escrow): a run-once draw script
(holdout_escrow_draw.py pattern, `secrets` module, refuses to run twice)
executes after ratification and before any v2 build code, drawing per
original-injected cell: run seed from 10000–99999 (disjoint by construction
from matrix seeds {1,2,3}, qseeds 901–909, and the holdout-escrow namespace
1000–9999); fire counter N uniform in [40%, 60%] of the task's clean-median
call count, floored (the RB convention generalizing Phase 1's fixed 50%
point; medians a1 24, c1 12, d1 21 — Phase 1 finals — and b1 14, rev-4
re-qualification, per the escrow record's draw basis); payload-parameter
variation only within wound-preserving ranges enumerated per injection in a
build-time draw spec (benchmark authorship). Values sealed in
escrow/matrix_escrow.json (gitignored, SHA-256 committed publicly,
transmitted to the same escrow holder under the same custody rules); the
launcher consumes the file programmatically and never prints or logs drawn
values. Rationale: the blindness obligation is in ink and the holdout
escrow is the committed pattern for satisfying it. Provenance: v6.1 §11.10
item 3; RESOURCE_BUDGET.md §6; holdout_escrow_record.md;
decisions/holdout_qualification_2026-06-12.md (qseed namespaces).
**Ruling (2026-06-12, A.M.): DEFAULT RATIFIED with amendment** — the
wound-preserving payload ranges (the draw spec) are written and committed
**in the ratification commit, before the draw executes**; the draw remains
run-once / `secrets` / sealed / hash-public; matrix_escrow.json gitignored
(verified via `git check-ignore` before writing); transmitted to the same
holder; the loader never prints values.

**[AUTHOR-6] Re-qualification scope for original pairs under changed
conditions.**
The nine original pairs were qualified at exactly N = 50%-of-median on
rev-1 worlds (decisions/manipulation_table_s1_seed1.md, 9/9 QUALIFIED), but
1b runs at world_rev 4 with the b1 fixture pack changed (8 files at
rev ≥ 2, REPO_FILES_V2) and the b1 worker cap at 24 (ruling #2 R1), plus —
under AUTHOR-5 — drawn rather than fixed counters and varied payloads.
Whether the Phase 1 qualification verdicts transfer is the author's call.
PROPOSED DEFAULT: one S1 qualification pass (frozen rule unchanged: 3 clean
+ 3 injected, ≥2/3 each way; fresh qseed namespace 910+) for the two b1
pairs (b1+schema_drift, b1+gate_skip_trap) whose host fixtures and cap
changed; other seven pairs' verdicts stand (their hosts and mechanics are
untouched at rev 4 — banked-replay byte-identity 27/27 under rev-4 code);
any payload variation that could weaken a wound (AUTHOR-5 draw spec)
triggers the same pass or an explicit author waiver. Rationale: the
qualification bar is frozen and the b1 environment demonstrably moved
(clean b1 was a "cap-boundary coin flip" at the old cap). Provenance:
manipulation_table_s1_seed1.md; DEPENDENCY_VERSION.md §8 + rev-2 fixture
note; holdout_qualification_2026-06-12.md Appendix 1 root-cause + Appendix
2 (R1); dev_run_ledger (rev-4 regression 27/27).
**Ruling (2026-06-12, A.M.): DEFAULT RATIFIED** — one S1 qualification
pass for the two b1 pairs at qseeds 910+, frozen rule, ledgered; executed
on confirmation (this session), before any v2 build code.

**[AUTHOR-7] S3 cost-matching basis for 1b.**
Phase 1 calibrated heartbeat-k so S3's overhead matched S5's measured
compile+judge overhead (decisions/heartbeat_k_calibration.md, fd21d9a:
a1=2, b1=21, c1=4, d1=5). v2 has no judge and a different overhead profile
(compile + side-channel probes); nothing ratified says what S3 matches in
1b. Options: (a) **PROPOSED DEFAULT — inherit the Phase 1 k values
verbatim** (committed pre-verdict artifact; derives from nothing the
battery reported; requires no embargo-sensitive measurement), with a
mandatory descriptive note that b1's k=21 was inflated by a 320-call clean
calibration grind and exceeds b1's rev-4 clean median of 14 — S3-b1 may
never revalidate within a clean run (the cadence-starvation mechanism of
archaeology_v2 §E.4); (b) recalibrate k from v2's measured clean overhead
via a pre-specified, ledgered procedure inside the matrix (clean cells
first). Rationale for (a): P1's inheritance discipline plus embargo
hygiene; the mismatch is reported, not hidden. Provenance:
phase1b_precommitments.md E.3 + P1; archaeology_v2.md §E.3–E.4;
holdout_escrow_record.md (b1 median 14).
**Ruling (2026-06-12, A.M.): OVERRIDE to option (b).** S3's k per task is
recalibrated from the **two-tier arm's measured clean overhead** using
Phase 1's matching formula, transcribed verbatim from
decisions/heartbeat_k_calibration.md (fd21d9a): *"k = ceil(worker_calls /
n_revals) with n_revals = round(sentinel_overhead / revalidation_turn_cost)"*
— with `sentinel_overhead`, `revalidation_turn_cost` (mean
orchestrator-turn cost), and `worker_calls` taken as the per-task MEAN over
ALL of that task's two-tier-arm clean cells (the Phase 1 source-run choice
applied to the 1b primary arm's clean slice). Computed **after the
two-tier arm's clean cells complete and before any S3 cell launches**;
the computation is ledgered (dev-run ledger entry with inputs and
resulting k per task); the inherited Phase 1 k values (a1=2, b1=21, c1=4,
d1=5) are reported descriptively beside the recalibrated ones. **Author's
rationale, recorded:** the inherited k matches a cost structure (judge)
that no longer exists, and k=21 > b1's clean median of 14 would render S3
structurally inert on b1, flattering v2's TTD comparison. The 1bKG4
thresholds themselves inherit untouched.

**[AUTHOR-8] Ex-ante recovery-class labels for the original nine pairs.**
1bKG1 computes strict recall "on recoverable-class cells", and §11.10
item 3 requires "retreat-condition cells labeled ex ante." The holdout
specs carry their labels (RESOURCE_BUDGET §3: mechanical rule,
REPLAN-recoverable iff Q0 ≥ expected remaining required calls at the drawn
N, else RETREAT-condition; DEPENDENCY_VERSION §3: retreat NEVER justified —
binding asymmetry). The original nine carry none. PROPOSED DEFAULT: the
author labels each original (task, injection) pair before matrix launch,
recorded in the launch manifest; candidate retreat-condition class to
weigh: token_expiry post-D19 (issuance suspended, no refresh path — D19's
mechanism makes recovery-by-re-auth impossible by design). Rationale: the
labels gate the 1bKG1 denominator and the abort-economics clause; they
cannot be derived mechanically for the original pairs. Provenance: RATIFIED
VALUES 1bKG1; v6.1 §11.10 item 3; memo §3 (abort economics → CLAUSE);
RESOURCE_BUDGET.md §3; DEPENDENCY_VERSION.md §3; deviations.md D19.
**Ruling (2026-06-12, A.M.): manifest-plus-confirmation procedure.** The
ex-ante recovery-class manifest for the nine original pairs (label +
one-line rationale each, candidate retreat-condition classes flagged,
incl. token_expiry post-D19) is drafted and presented to the author; the
FROZEN stamp waits on the author's confirmation message. The confirmed
manifest is recorded in §3a of this document and governs the 1bKG1
denominator.
**CONFIRMED (2026-06-12, A.M.):** manifest confirmed as drafted, incl.
pair 8's caveat; recorded verbatim in §3a together with the author's
PERMISSION_AUTH categorical-basis ruling.

**[AUTHOR-9] Wilson confidence level.**
P2 #8 left the per-category lower-bound confidence at [freeze]; the
ratified text names "Wilson lower bounds" with no level. PROPOSED DEFAULT:
95% (two-sided convention; any other number is equally data-free but
non-standard). Provenance: phase1b_precommitments.md P2 #8; RATIFIED VALUES
1bKG1.
**Ruling (2026-06-12, A.M.): DEFAULT RATIFIED** — 95%.

**[AUTHOR-10] Two P2 placeholders never ratified — strike or value them.**
(i) P2 #2's "time-to-first-false-interrupt on clean cells ≥ [freeze]
calls": absent from the RATIFIED VALUES. PROPOSED DEFAULT: strike from the
gate set, record as not ratified; report TTFFI descriptively (the ratified
P95/max/zero-grind caps carry the storm rationale). (ii) P2 #5's "probe
perturbation rate ≤ [freeze]": absent from the RATIFIED VALUES. PROPOSED
DEFAULT: no separate rate threshold — the ratified clauses already bind
harder (probe-induced clean-run failures = 0 hard, P2 #5 first clause,
value pre-committed; the 100% non-perturbing probe-validity audit with
class exclusion; side-channel isolation as a hard gate per v6.1 §11.9
amendment #1); perturbation events reported descriptively. Rationale: the
freeze may not invent values the ratification skipped; both rationales are
already serviced by ratified clauses. Provenance: phase1b_precommitments.md
P2 #2, #5 vs RATIFIED VALUES (absence); v6.1 §11.9 amendment #1.
**Ruling (2026-06-12, A.M.): DEFAULTS RATIFIED, (i) and (ii)** — TTFFI
struck from the gate set (descriptive only); no separate perturbation-rate
threshold (descriptive only; hard clauses stand).

**[AUTHOR-11] Amortized-view workload composition.**
1bKG3's descriptive amortized view is "over a pre-specified 10-task
repeated-plan workload" — composition unspecified. PROPOSED DEFAULT: per
task archetype, 10 same-archetype repeated-plan runs amortizing one
compilation (compile cost ÷ 10 per run), computed analytically from matrix
cells (no extra runs), reported per archetype, descriptive only. Rationale:
the only reading that requires no new executions and no new measurement
channel. Provenance: RATIFIED VALUES 1bKG3; phase1b_precommitments.md
P2 #10.
**Ruling (2026-06-12, A.M.): DEFAULT RATIFIED.**

**[AUTHOR-12] Probe-validity audit mechanics: sampling seed and auditor.**
The hard gate specifies "a seeded 20% audit of probe-generated interrupts"
without naming the seed or auditor. PROPOSED DEFAULT: sampling seed fixed
in this document at ratification (proposed constant: 1102); the author
audits each sampled interrupt against written criteria — targeted / fresh /
non-perturbing / independent-of-trigger, semantic-vs-deterministic basis
marked per probe (P2 #4 wording) — with the worked audit table committed
beside the gate output. Rationale: mirrors Phase 1's attribution-audit
pattern (rule first, human audit on a fixed sample). Provenance: RATIFIED
VALUES 1bKG1; phase1b_precommitments.md P2 #4; prereg.md 6.1 (TTD audit
pattern).
**Ruling (2026-06-12, A.M.): DEFAULT RATIFIED with amendment** — sampling
seed 1102; author audits per the P2 #4 criteria; additionally, an optional
non-implementer spot-check of 3 audit rows is recorded as an INVITED
(non-gating) strengthening.

**[AUTHOR-13] Tooling pins: CLI version and model strings for 1b.**
Phase 1 pinned CLI 2.1.170 wire-to-wire (matrix-close record; post-close
daily CLI now 2.1.175) and fixed models (orchestrator/compile
claude-sonnet-4-6; workers/judge claude-haiku-4-5-20251001;
pilot_protocol §3.5). Nothing ratified binds 1b to either. PROPOSED
DEFAULT: pin the CLI version current at v2 build start, recorded in the
queue meta with the Phase 1 halt-on-change guard and DISABLE_AUTOUPDATER
re-applied for the matrix duration (RUNBOOK pattern); inherit Phase 1 model
strings unchanged (the judge string applies to the exploratory arm only).
Rationale: comparability with Phase 1 numbers wherever the gates compare
across phases; pinning discipline is inherited apparatus. Provenance:
pilot_protocol.md §3.5; RUNBOOK.md; decisions/matrix_close_2026-06-12.md.
**Ruling (2026-06-12, A.M.): DEFAULT RATIFIED.**

**[AUTHOR-14] LLM cost cap for the v2 build + 1b matrix.**
No ratified cap exists for 1b (Phase 1 ran ~$131 of a $300 cumulative
envelope; the Phase 1 matrix alone recorded $120.05; holdout sessions ran
under a $25 session cap, ~$8 spent). PROPOSED DEFAULT: a fresh 1b envelope
of **$250** — build ≤ $50, matrix ≤ $200 — scaling Phase 1's measured
matrix spend by the default cell count (245/195 × $120.05 ≈ $151) plus
margin for v2 compile cells and re-qualification passes; queue halts at the
cap and the author rules. Rationale: the only measured cost basis in the
record. Provenance: kill_gates_final.md ops close-out;
holdout_qualification_2026-06-12.md (session totals); AUTHOR-2 cell count.
**Ruling (2026-06-12, A.M.): DEFAULT RATIFIED** — $250 envelope (build ≤
$50, matrix ≤ $200); if the cap binds mid-matrix, the AUTHOR-4 descope
order applies (exploratory judge arm first; confirmatory arms and
baselines never).

**[AUTHOR-15] Consistency flags — paper draft and records (dispositions
owed at next edit; nothing edited this session).**
paper/fse_draft.md (34bb7a0) §7 was checked against this assembly:
  (i) §7 says "pre-detection false-interrupt budget ≤ 2 on injected cells"
      — the ratified clause is **median** ≤ 2; the word "median" must be
      restored. (RATIFIED VALUES 1bKG2.)
  (ii) §7 paraphrases the honesty clause as "dominates v2 on recall at
      comparable noise" — the ratified condition is "at ≤ FIR"; the paper
      should carry the operative inequality. (RATIFIED VALUES, Standing.)
  (iii) §1/§3 present tense ("is being re-measured", "the form under
      confirmatory evaluation") overstates state at this freeze: the build
      has not begun; accurate once the matrix launches, premature today.
  (iv) §7 omits the descriptive amortized view over the pre-specified
      10-task workload (1bKG3 ratified text); minor omission.
  (v) §7 quotes "≥50% in ≥4/5 categories" — consistent with AUTHOR-1
      option (a); requires editing if (b) is chosen.
  (vi) Record staleness, not paper: RESOURCE_BUDGET.md §8 names "rev 3 …
      current for 1b" — superseded by author ruling #2 R3 (world_rev 4,
      revs ≤3 frozen); RB mechanics unaffected (hosted at rev ≥ 2). The
      spec is a frozen qualified artifact and is not edited; this note is
      the disposition.
**Ruling (2026-06-12, A.M.): DEFAULT RATIFIED** — dispositions owed at the
next paper edit as listed; nothing edited this session.

---

## 1. Identity and authority

1. This document pre-registers the **Phase 1b confirmatory pilot**
   authorized by decision memo §5 (e808862), all five conditions
   addressed: (a) gate thresholds frozen at the memo's commit, before any
   v2 build code (memo §5(a), §4); (b) held-out categories RESOURCE_BUDGET
   and DEPENDENCY_VERSION authored, manipulation-qualified
   (holdout_qualification_2026-06-12.md: RB on a1 clean 3/3 / injected 3/3;
   DV spec rev 3 on b1 clean 3/3 / injected 3/3 FAIL BY THE WOUND, Appendix
   2), and the value superset escrowed with a non-implementer — **memo
   §5(b) CLOSED** (holdout_escrow_record.md, transmission confirmed
   2026-06-12); (c) data embargo + dev-run ledger standing (§6 below);
   (d) v2 build scope = v6.1 §11.9 as amended (§5 below); (e) instrument
   fixes regression-evidenced and deviation-logged (§5 below).
2. **Arms (per pre-commitment P3, in ink before any battery result —
   no post-selection):** the **two-tier (no-judge) v2** configuration is
   the designated PRIMARY arm; the **rebuilt-judge v2** configuration is
   EXPLORATORY only; whichever arm "wins" later, the confirmatory claim
   attaches to the two-tier arm only. (phase1b_precommitments.md P3; memo
   §2 KG2 branch; v6.1 §11.9 amendment #6.)
3. **Comparison arms:** S1 (batch), S2 (naive interrupt), S3 (cost-matched
   heartbeat; matching basis AUTHOR-7). S2 is a **mandatory head-to-head
   arm** under the ratified honesty clause, verbatim: *"S2 is a mandatory
   head-to-head arm with an honesty clause (if S2 dominates v2 on recall
   at ≤ FIR, the paper says so in the results, not a footnote)."*
   (RATIFIED VALUES, Standing; memo §4.) S2's measurement convention
   inherits Phase 1's instrument rule — first attributable pause — exactly
   as mirrored in the battery (memo Appendix C).
4. **Ratified interrupt policy for v2 (both v2 arms):** corroboration is
   **probe-primary** — the second-signal clause (E.1 (i)) is DELETED per
   memo §3 (6/18 false interrupts self-corroborated, two on a clean cell;
   G11); clause (ii) (one confirming probe) is the ratified policy; the
   **status fast path is retained as operationalized (status ≥ 400)**
   (G10, attack refuted in-corpus). (RATIFIED VALUES, Corroboration
   policy; archaeology_v2.md §E.4.)
5. v1's verdict appears in the paper regardless of v2's outcome (memo §7;
   v6.1 §11.10 item 1).

## 2. Gates — transcribed verbatim from the ratified values

The four gates and standing requirements below are transcribed **verbatim**
from decisions/phase1b_precommitments.md RATIFIED VALUES (823549e lineage,
ratified at e808862 via memo §4; "where wording differs, the committed
rationale text governs"). Per P1, shared quantities inherit v1's
pre-verdict thresholds verbatim and derive from nothing the archaeology-v2
battery reported.

> - **1bKG1 (detection):** strict recall ≥60% on recoverable-class cells;
>   ≥50% in ≥4/5 categories (reported with Wilson lower bounds; any category
>   with n<3 is descriptive only); kill floor <40%. Probe validity is a HARD
>   gate: a seeded 20% audit of probe-generated interrupts must show 100%
>   targeted/fresh/non-perturbing/independent; any failure excludes that
>   interrupt class from recall before the gate computes. Recovery quality:
>   detect-only, detect-and-recover, detect-and-justified-abort counted
>   separately; ≥50% of strict detections must be the latter two. Held-out
>   categories (memo §5: RESOURCE_BUDGET, DEPENDENCY_VERSION, seeds escrowed
>   with a non-implementer) are inside the recall denominator.
> - **1bKG2 (noise/self-harm), absolute caps:** clean-cell median FIR = 0;
>   P95 ≤ 1; max false interrupts per clean cell ≤ 3; zero escalation-cap
>   grinds on clean cells (hard). Pre-detection false-interrupt budget on
>   injected cells: median ≤ 2 before first true detection. Clean success:
>   absolute floor ≥ 60% AND ≥ (S1 clean − 10 points). (Ratified: 60/10,
>   A.M.)
> - **1bKG3 (economics):** clean overhead ≤ 12% (inherited), probe costs
>   included in waste. Primary view unamortized per-run; amortized view
>   reported descriptively over a pre-specified 10-task repeated-plan
>   workload. No crossover-plausibility gate (resolved against v1; the full
>   study carries the claim).
> - **1bKG4 (vs heartbeat):** TTD ≥ 2× (inherited) AND wasted-work
>   parity-or-better vs cost-matched S3 with probe costs included.
>   Sensitivity row: undetected cells censored at run end.
> - **Standing:** instrumentation-integrity replay (Task-A pattern) runs on
>   100% of injected 1b cells BEFORE gates compute; S2 is a mandatory
>   head-to-head arm with an honesty clause (if S2 dominates v2 on recall at
>   ≤ FIR, the paper says so in the results, not a footnote).

Clarifications bound to the transcription (no new content):

- The categorical clause's denominator under the holdouts is **AUTHOR-1
  (ruled: option (a))**; its computation basis is per-category strict
  detection over ALL injected cells per the PERMISSION_AUTH ruling beside
  §3a; the Wilson confidence level is **AUTHOR-9 (ruled: 95%)**; the
  recoverable-class denominator (overall recall gate + kill floor only)
  follows the confirmed ex-ante labels of **AUTHOR-8 / §3a** (holdout
  labels fixed by the qualified specs: RESOURCE_BUDGET.md §3 mechanical
  rule; DEPENDENCY_VERSION.md §3 — retreat never justified, binding
  asymmetry).
- Probe-validity audit mechanics (seed, auditor) are **AUTHOR-12**; an
  unjustified abort on a recoverable cell never counts toward any gate
  (phase1b_precommitments.md P2 #6; memo §3 abort-economics CLAUSE).
- Wasted-work parity reads (v2 post-invalidation worker tokens + v2 total
  probe overhead) ≤ 1.0 × S3, i.e. the ratified "parity-or-better … with
  probe costs included" applied to P2 #7's clause form; probe overhead is
  booked in the **waste** column, never a separate forgivable line (v6.1
  §11.9 amendment #1; G15 measured warrant).
- Overhead retains its frozen Phase 1 operational definition — total cost
  on clean runs minus S1's total cost on clean runs (prereg.md 6.1) — as do
  wasted work, TTD, detection recall, FIR (0/0 = 0), and success; the 1b
  additions (salvage score, abort quality, probe validity, probe overhead
  as waste) extend, never redefine (paper §4 metrics list mirrors this).
- **Delta-FIR is reported descriptively alongside the absolute caps; gates
  remain absolute per H5** (memo §3, Gemini disposition).
- Phase 1 posteriors enter v2 **only as weakly-informative priors, labeled
  exploratory; no gate consumes them** (memo §3, PARTIAL WAIVER —
  calibration leakage). Five-R: primary recovery_class retained; optional
  secondary hint permitted, exploratory (memo §3 WAIVER with mitigation).
- Instrumentation-integrity replay = raw-trace-to-label replay, Task-A
  pattern (archaeology_v2.md §A prototype; G17 HOLDS), on **100% of
  injected 1b cells**, completed and committed BEFORE `make gates`-
  equivalent computation.

## 3. Matrix design

**Determined by the records (transcribed):**

- **Tasks:** the four archetypes a1/b1/c1/d1 (structural inheritance:
  prereg.md; pilot_protocol.md §4; world fixtures unchanged for original
  categories at rev 4 — banked Phase 1 replay byte-identity 27/27 under
  rev-4 world code, runs/archaeology_v2/replay_check_rev4_regression.json).
- **World revision:** all 1b cells run at **world_rev 4**; revs 1–3 are
  frozen (rev 1 byte-identical to Phase 1; rev 2/3 frozen at the spec-rev-1
  and spec-rev-2 qualification semantics). (DEPENDENCY_VERSION.md §8;
  holdout_qualification_2026-06-12.md Appendix 2, ruling #2 R3.)
- **b1 worker turn cap 24, b1-scoped** (yaml `worker_max_turns`; a1/c1/d1
  untouched) — standing harness config from ruling #2 R1, config-diff
  verified in the qualification record.
- **Injection categories:** the five original categories via the nine
  Phase 1 qualified pairs — a1+endpoint_404, a1+schema_drift,
  a1+token_expiry, b1+schema_drift, b1+gate_skip_trap,
  c1+doc_contradiction, c1+token_expiry, d1+gate_skip_trap,
  d1+endpoint_404 (manipulation_table_s1_seed1.md, 9/9 QUALIFIED; subject
  to AUTHOR-6) — plus the two held-out categories per their qualified
  specs. Counter-triggered injections only (M1 amendment 3 path, both
  holdout specs §1; Phase 1 convention).
- **Arms:** five — v2 two-tier (primary), v2 rebuilt-judge (exploratory),
  S1, S2, S3 (§1 items 2–3). No S4: the no-judge configuration *is* the v2
  primary; the v1 architecture is not re-run (memo §2: the v1 claim is
  killed, continuation is solely the 1b path).
- **Holdout consumption (build requirement, binding):** holdout cells
  consume `escrow/holdout_escrow.json` **programmatically at launch** —
  per-cell run seed, N, Q0 (RB), post version + post page size (DV), and
  service-family designation. The loader (i) verifies the file against the
  public SHA-256
  `df1dcd8bd1cad04f815576cc1d6876807e95bbf25ffc959ada40ff0fa2bb3c88`
  before any cell runs, and (ii) **must never print or log drawn values**
  — no console echo, no log lines, no plaintext manifest entries; the
  author does not open the file. (holdout_escrow_record.md custody rule;
  RESOURCE_BUDGET.md §8; DEPENDENCY_VERSION.md §8.)
- **Ex-ante labels:** retreat-condition cells labeled before launch (v6.1
  §11.10 item 3): RB by the mechanical rule at the drawn N/Q0 (spec §3,
  computed by the loader without printing values); DV none (spec §3);
  original pairs per AUTHOR-8.
- **Instrument fixes required before launch (#7-class):** D6 surface
  derivation and D13 pattern-liveness samples become rev-aware, plus the
  dead-pattern-class fix with the compile-time pattern-liveness regression
  sweep — regression-evidenced and deviation-logged (memo §5(d)–(e); v6.1
  §11.9 amendment #7; both holdout specs §8: without rev-awareness, 1b
  tripwires targeting /manifest would be classified dead — the exact #7
  wound).
- **Tracing:** complete JSONL traces, byte-replayable from config (Phase 1
  apparatus, prereg custody discipline; archaeology_v2 Phase 0 is the
  precedent the replay gate consumes).

**Resolved by the 2026-06-12 rulings (recorded beside each item):** 3
seeds per (task, variant), clean cells every arm, 49 cells/arm, **245
cells total** (AUTHOR-2); holdouts = RB-a1 + DV-b1 × 5 escrowed seeds
(AUTHOR-3); exploratory judge arm at full parity with pre-committed
descope order (AUTHOR-4); original-category draws sealed via
matrix_escrow.json with the draw spec committed in the ratification
commit, before the draw (AUTHOR-5); b1-pair re-qualification at qseeds
910+ (AUTHOR-6); S3 k recalibrated from the two-tier arm's clean cells,
Phase 1 formula verbatim, before any S3 cell launches (AUTHOR-7 override);
CLI pinned at build start + Phase 1 model strings (AUTHOR-13); $250
envelope with the AUTHOR-4 descope order (AUTHOR-14). **Open: the
AUTHOR-8 manifest below (§3a), pending the author's confirmation — the
FROZEN stamp waits on it.**

### 3a. Ex-ante recovery-class manifest — original nine pairs (AUTHOR-8)

**CONFIRMED by the author 2026-06-12 ("The nine-row manifest is CONFIRMED
as drafted, including pair 8's recorded caveat"), recorded verbatim.**
Governs the 1bKG1 recoverable-class denominator. Holdout labels are fixed
by the qualified specs and are not part of this manifest: RB mechanical
rule at the drawn N/Q0 (RESOURCE_BUDGET.md §3); DV always recoverable,
retreat never justified (DEPENDENCY_VERSION.md §3).

| # | pair | label | passing recovery | rationale (one line) |
|---|---|---|---|---|
| 1 | a1+endpoint_404 | **RECOVERABLE** | REMAP | `/pricing/quotes` (query form) is an authored alternative surface, in the OpenAPI from run start — built "so endpoint_404 on /pricing/quote/* is plan-invalidating but task-recoverable" (world/services/pricing.py docstring). |
| 2 | a1+schema_drift | **RECOVERABLE** | REINTERPRET (+REDO) | Same route keeps serving 200; recovery = remap `unit_price`→`price` and convert integer cents→dollars; manipulation precedent: S1 PASS after forced redo. |
| 3 | a1+token_expiry | **RETREAT-CONDITION** ⚑ | justified RETREAT + salvage | D19: all tokens revoked AND issuance suspended for the run's remainder (`auth_locked`); /inventory, /pricing, /shipping all bearer-gated → unfetched data is unreachable by construction; salvage pre-expiry results, report the gap. |
| 4 | b1+schema_drift | **RECOVERABLE** | RECONCILE + REDO | Drifted settings.yaml stays fully re-readable/re-writable (repo needs no auth); the gate runs its checks genuinely; manipulation precedent: S1 PASS after forced redo. |
| 5 | b1+gate_skip_trap | **RECOVERABLE** | REDO + independent verification | The trapped gate returns "passed"/checks_run 0, but b1's output contract requires only `validate_status: "passed"` (checkers/b1.py has **no** checks_run clause) and the checker judges ground-truth world state — a correct, self-verified migration passes despite the dead gate; manipulation precedent: S1 PASS after forced redo. |
| 6 | c1+doc_contradiction | **RECOVERABLE** | RECONCILE | The contradicted passage stays retrievable; recovery = detect the flip, reconcile against the planning premise, and surface the discrepancy in the brief (the frozen premise probe accepts "30"/"thirty", so a discrepancy-flagging brief passes); validate/package remain functional. |
| 7 | c1+token_expiry | **RETREAT-CONDITION** ⚑ | justified RETREAT + salvage | Same D19 mechanism; every /docs route is bearer-gated → grounding, validate, and package are all unreachable post-N. |
| 8 | d1+gate_skip_trap | **RETREAT-CONDITION** ⚑ | justified RETREAT + salvage | d1's contract and checker require `validate.checks_run > 0` (checkers/d1.py, D16: "what separates a genuinely-run gate from the gate_skip_trap"); the trapped gate returns checks_run 0 for the run's remainder → honest completion post-N is unsatisfiable (fabricating the gate report is the dishonest path the adjudication principle excludes). *Caveat recorded: formally completable iff the final document validates genuinely before N — outside d1's call profile (N ∈ [8,12] of clean median 21; validate sits at plan steps s3–s4, post-fetch).* |
| 9 | d1+endpoint_404 | **RETREAT-CONDITION** ⚑ | justified RETREAT + salvage | `/docs/package` is removed for the run's remainder with **no alternative route** (world/services/docs.py); `package_id` is unobtainable; salvage = validated document + validate report. Asymmetric with pair 1 by authored construction — the same deliberate asymmetry as RB (retreat sometimes justified) vs DV (never). |

**Denominator consequences (recorded with the confirmation):** strict-
recall (1bKG1) denominator = 15 original recoverable cells (pairs 1, 2, 4,
5, 6 × 3 seeds) + 5 DV cells + the REPLAN-recoverable fraction of the 5 RB
cells (sealed, labeled mechanically at launch) → 20–25 cells.
Retreat-condition: 12 original cells (+ the RB remainder); on those,
detection is still measured and reported, and detect-and-justified-abort
is the passing recovery bucket; an unjustified abort on a recoverable cell
never counts toward any gate.

**PERMISSION_AUTH categorical-basis ruling (2026-06-12, A.M., verbatim):**
*"the categorical clause ('≥50% in ≥4/5 categories', Wilson-bounded, n<3
descriptive) computes per-category strict DETECTION over ALL injected
cells, inheriting v1's computation basis per P1 (v1's per-category
thresholds were defined over injected cells; recoverability did not exist
as a concept in v1, so 'verbatim inheritance' includes the denominator
basis). The overall ≥60% strict-recall gate and the <40% kill floor remain
recoverable-class only, exactly as the ratified sentence attaches them.
Recovery on retreat-condition cells is governed by the recovery-quality
clause (detect-and-justified-abort = passing bucket)."* Effect: every
category — PERMISSION_AUTH included — stays populated for the categorical
clause (per-category n: API_SURFACE 6, SCHEMA_DRIFT 6, PERMISSION_AUTH 6,
TOOL_CONTRACT 6, RETRIEVAL_INTEGRITY 3, over all injected cells of the
original five categories per the AUTHOR-1(a) universe); the
recoverable-class restriction binds only the overall recall gate and kill
floor.

## 4. Category-gate denominator

**Ruled: AUTHOR-1 option (a) RATIFIED (2026-06-12, A.M.).** The
categorical hard clause ranges over the original five categories; the
holdout categories sit inside the overall ≥60% recall denominator and are
reported per-category with Wilson lower bounds (95%, AUTHOR-9),
descriptive only where n<3. The gate text in §2 is transcribed verbatim;
this ruling fixes its denominator universe and the holdouts' reporting
mode.

## 5. Execution and schedule

1. **v2 build window: 2026-06-13 → 2026-06-22** (v6.1 §13). Scope = §11.9's
   eight changes **as amended** (memo §5(d)): #1 compiled active probes on
   a perturbation-isolated side channel, event-gated work-at-risk-weighted
   cadence with a guaranteed pre-completion sweep, probe overhead booked as
   waste; #2 probe-primary corroboration, status fast path retained; #3
   calibration loop under the memo §3 partial waiver (exploratory priors
   only); #4 priced ABORT/RETREAT; #5 recovery-typed replan hints +
   checkpointed salvage; #6 two-tier primary / judge exploratory (P3);
   #7 dead-pattern-class fix + pattern-liveness regression sweep
   (instrument-class, regression-evidenced, deviation-logged); **#8
   descoped from 1b** (convergent FATALs; full-study exploratory arm).
   Probe freshness clause: probes recompile on every replan; freshness is
   an audited probe-validity criterion (memo §3, probe staleness CLAUSE).
   Harness graduations permanent, all systems: strict reply schemas both
   directions, void-run invariant, launcher probe, version pin, canary
   isolation (v6.1 §11.9).
1a. **Ratification-session sequence (per the 2026-06-12 rulings), upon
   AUTHOR-8 confirmation and before any v2 build code:** (i) FROZEN stamp
   committed; (ii) the AUTHOR-5 draw spec written and committed in the
   ratification commit, then the run-once matrix-escrow draw executes and
   its custody record is committed (SHA-256 only; no values printed);
   (iii) the AUTHOR-6 b1-pair re-qualification pass runs (qseeds 910+,
   frozen rule, ledgered). No v2 build code in the ratification session.
2. **Matrix launch: 2026-06-23 → 2026-07-15**, unattended, continuous,
   concurrency 1, pause-on-demand; zero decisions scheduled in this window
   by design (v6.1 §13). **In-matrix ordering (AUTHOR-7 override):** the
   two-tier arm's clean cells complete first; S3's per-task k is then
   computed by the verbatim Phase 1 formula (AUTHOR-7) and ledgered before
   any S3 cell launches; no other gate-relevant quantity is read from the
   clean cells at that point (the k computation consumes overhead,
   orchestrator-turn cost, and call counts only).
3. **Product-launch precedence:** the product launch (Jul 15) outranks the
   matrix; the queue pauses **losslessly** on demand (memo §7; v6.1 §11.10
   item 6; RUNBOOK interruption semantics: stale running jobs reset to
   pending, nothing lost or duplicated).
4. **Gates computed ONCE on the complete matrix** — `make ops` style
   operations-only monitoring until then; no gate quantity is computed,
   displayed, or estimated on a partial matrix (RUNBOOK "no peeking";
   Phase 1 precedent: kill_gates_final.md "first and only computation").
   The instrumentation-integrity replay (§2) completes first.
5. **Attribution audit:** by trace rule first, manual audit on a 20% sample
   plus every disagreement case (prereg.md 6.1, inherited; Phase 1 returned
   13/13 — memo §1).
6. **Schedule gate 2 (pre-committed):** Phase 1b **verdict in hand by
   2026-07-18 23:59**, else the FSE submission retargets per §13 fallbacks
   (NIER Oct 23 / SEAMS / ASE 2027). **No extension may be granted by the
   author to the author.** (memo §6.) The post-gate decision memo executes
   within 48 hours of the gate table, per the Phase 1 pattern.
7. **Deviation log continues uninterrupted at D23** (memo §7); D22 remains
   a CANDIDATE pending the author's disposition (deviations.md). Erratum
   discipline: corrected claims stay visible with their errata (memo §7;
   v6.1 §11.7 pattern).
8. **Schedule gate 3 (recorded for continuity, not a 1b gate):** ≥ 50
   validated onboarded real-suite tasks by 2026-08-31, else descope
   (30–49: single-suite; <30: retarget ASE 2027). (memo §6; Ratified: 50,
   A.M.)

## 6. Embargo and custody

1. **Data embargo (standing, from this freeze to matrix launch):** no
   benchmark-world output is observed by the author or any v2 component
   development loop before the matrix launches; build-window verification
   is **unit tests on test worlds only** (the holdout-build pattern:
   traces to tmpdir, no benchmark cells). (memo §5(c); v6.1 §11.10 item 3;
   dev_run_ledger entries 2026-06-12 as the executed precedent.)
   **Carve-out (by the AUTHOR-6 ruling):** the post-freeze S1-only b1
   re-qualification pass (qseeds 910+) — S1 contains no v2 component;
   benchmark qualification work under the holdout-qualification precedent
   (memo §5(b) pattern); ledgered like every other execution.
2. **Dev-run ledger (standing):** every execution involving any v2-style
   component — probe construction, probe execution, policy replay,
   deterministic-world re-instantiation — is logged in
   analysis/dev_run_ledger.md with timestamp, component, purpose, inputs,
   LLM cost. No executions are expected by the assembly session that
   produced this draft; if any occur, they are ledgered. (Ledger header,
   opened a9143b7; memo §5(c).)
3. **Escrow custody (restated from the record):**
   `escrow/holdout_escrow.json` is gitignored and SEALED — never opened,
   read, printed, or copied by the author; custody is split between the
   escrow holder (Zeynep Sağlık, co-founder, non-implementer; receipt
   CONFIRMED 2026-06-12) and the public SHA-256
   `df1dcd8bd1cad04f815576cc1d6876807e95bbf25ffc959ada40ff0fa2bb3c88`.
   The holder produces her copy only on the author's written request; the
   local copy is consumed programmatically by the harness at launch after
   hash verification; integrity at launch is verified against the public
   hash. (holdout_escrow_record.md, incl. the custody-note attestation.)
4. **Run-once guards:** the escrow draw script refuses to run twice
   (holdout_escrow_record.md; ledger 2026-06-12T13:05Z); any AUTHOR-5
   matrix-escrow draw carries the same guard; the gates computation runs
   once on the complete matrix (§5.4); the launcher's version-pin halt
   guard and void-run invariant stand (D21; RUNBOOK).
5. **Blindness statement:** the drawn holdout values remain unseen by the
   author (escrow record attestation); under AUTHOR-5's default the
   original-category draws acquire the same status at draw time.

## 7. Freeze mechanics

1. This document freezes **only upon the author's ratification**: the
   author rules on AUTHOR-1 … AUTHOR-15, the rulings are recorded inline
   (the "Ratified: …, A.M." pattern of memo §4), the status banner is
   changed to FROZEN, and the commit of that revision constitutes the
   ratification signature — mirroring the memo's signature clause
   (memo, Signature; prereg.md freeze pattern). **Executed 2026-06-12: all
   fifteen rulings recorded inline; the §3a manifest confirmed by the
   author's message of 2026-06-12; this revision carries the FROZEN stamp
   and its commit is the ratification signature. — Ansuman Mullick,
   ratified 2026-06-12.**
2. The freeze commit records SHA-256 hashes of: this file as frozen; the
   two qualified holdout specs (benchmark/holdouts/RESOURCE_BUDGET.md,
   DEPENDENCY_VERSION.md); and restates the escrow hash (§6.3). v2
   artifact hashes cannot exist at freeze (the build follows the freeze by
   construction, memo §5(a)) and are pinned by the build's own commits.
3. After the FROZEN stamp, **changes occur only via numbered deviations**
   (next: D23), each recorded in deviations.md with evidence before data
   collection — prereg.md's standing rule, unchanged.
4. Until the FROZEN stamp: **no benchmark cells, no world/harness/v2
   code, no edits to specs, records, the proposal, or the paper draft**
   may proceed under this document's authority. (Assembly-session
   boundary, recorded here so the freeze gap cannot be mistaken for
   authorization.)

---

*Assembled 2026-06-12 from the records cited in the header; transcription
only — the assembler resolved nothing. All fifteen rulings and the §3a
confirmation are the author's (messages of 2026-06-12, recorded inline).
FROZEN 2026-06-12; changes hereafter only via numbered deviations
(next: D23).*
