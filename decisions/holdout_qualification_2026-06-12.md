# Held-out category manipulation qualification — 2026-06-12

Executed under decision memo §5 condition (b) (e808862), mirroring the
original nine (decisions/manipulation_table_s1_seed1.md). Specs:
benchmark/holdouts/RESOURCE_BUDGET.md and DEPENDENCY_VERSION.md. Driver:
analysis/holdout_qualification.py; per-run detail
runs/holdout_qualification/summary.json. Qualification seeds
qseed-901/902/903 (distinct namespace; matrix seeds are NOT drawn from
these). Counter-triggered injections only. World: rev 2. CLI: native
claude.exe (post-close, RUNBOOK matrix-close notes); 12 runs, $3.21
total reported cost.

**Frozen rule:** PASS = injected S1 fails task validation (or emits wrong
output) in >= 2/3 seeds while clean S1 passes in >= 2/3 seeds.

## Verdicts

- **RESOURCE_BUDGET / quota_cliff on a1: QUALIFIED** (clean 3/3 PASS,
  injected 3/3 FAIL).
- **DEPENDENCY_VERSION / silent_minor_bump on b1: NOT QUALIFIED**
  (clean 2/3 PASS; injected 1/3 fail, and that single failure is
  attributable to worker-output fragility, not the truncation wound —
  honest accounting: **the wound landed in 0/3 seeds**). Per the brief's
  pre-commitment: the spec gets revised, not the bar. **Session stopped
  after this report; no escrow draw executed; the author rules next.**

## The table

| category | seed | clean result | injected result | failure mode | trace pointer |
|---|---|---|---|---|---|
| RESOURCE_BUDGET (a1, N=12, Q0=8) | 901 | PASS | **FAIL (checker)** | quota exhausted (final 0), 8 recurring 429s; GAD-002/THM-001/THM-002 fields None | runs/a1-S1-quota_cliff-s901 |
| RESOURCE_BUDGET | 902 | PASS | **FAIL (checker)** | quota exhausted, 12 recurring 429s; quantity/warehouse None across SKUs | runs/a1-S1-quota_cliff-s902 |
| RESOURCE_BUDGET | 903 | PASS | **FAIL (checker)** | quota exhausted, 10 recurring 429s; unit_price/quantity/warehouse None across SKUs | runs/a1-S1-quota_cliff-s903 |
| DEPENDENCY_VERSION (b1, N=1, post page 5) | 901 | PASS | FAIL (checker) — **but not the wound**: first list call was `page=1&page_size=100` (full 8 files at counter 1), src/tax.py was migrated (counters 10–11); all workers then returned null final outputs (D10-class fragility) | injection fired at 1 ✓; wound neutralized by explicit pagination | runs/b1-S1-silent_minor_bump-s901 |
| DEPENDENCY_VERSION | 902 | FAIL (honest agent failure: all workers null output, 23 calls; D17 precedent a1-s2/d1-s3) | PASS | truncated default lists at counters 1–2 were followed at counter 3 by `page=1&page_size=10` → full list; **the in-body total_count: 8 vs 5 files self-described the truncation** (D18 analogue) | runs/b1-S1-silent_minor_bump-s902 |
| DEPENDENCY_VERSION | 903 | PASS | PASS | single list call `page=1&page_size=100` at counter 3 → full list; wound never observable | runs/b1-S1-silent_minor_bump-s903 |

## Instrument verification (before any verdict was read)

- Injection fired via the counter path at exactly the configured N in 6/6
  injected runs (`injection_fired` events: a1 @12 x3, b1 @1 x3).
- World mechanics behaved per spec in all runs: quota decremented on
  billable family calls only, cliff 429s recurred to run end with the
  authored constant body; version header/manifest flipped at N; default
  page size dropped to 5 with total_count carrying the full count;
  explicit pagination honored throughout.
- Unit suite 109/109; banked Phase 1 replay byte-identity 27/27 under the
  new world code (runs/archaeology_v2/replay_check_rev_gate_regression.json).

## Failure-mode diagnosis for DEPENDENCY_VERSION (from traces)

The category's wound requires the batch to rely on **default** page sizes.
This batch never does, for two confirmed reasons:

1. **Plan-time pre-armoring.** In 3/3 seeds the orchestrator wrote explicit
   `page_size=100` (or equivalent) into worker subtasks at plan time —
   before any response was seen. The D6-derived surface appendix advertises
   `page (query), page_size (query)` on every list endpoint (the parameters
   sit in the route signatures at every rev, so they surface in the OpenAPI
   the appendix derives from), and the Sonnet orchestrator defensively
   pre-paginates whenever pagination parameters are visible. A
   default-page-size mutation is unobservable to a client that always
   passes the parameter.
2. **Self-describing fingerprint.** In s902 a worker received the truncated
   default list — `{"files": [5], "total_count": 8}` — and immediately
   re-listed with explicit page size. The in-body total_count is the D18
   lesson replayed: the night-0 `price_cents` drift was shrugged off
   because the payload self-described the change; D18's fix was a
   non-self-describing rename. DV's deterministic-decidability fingerprint,
   placed in the body, doubles as a recovery hint for the batch.

## Proposed spec revision (for the author's ruling — NOT executed)

Both defeat mechanisms must be addressed while preserving deterministic
decidability and recovery-by-construction:

- **v2.0 renames the pagination parameter** (`page_size` -> `limit`).
  Post-bump, `page_size` is silently ignored (standard REST behavior for
  unknown query params), `page` keeps working, and the post-bump manifest
  documents the new parameter (e.g. `"page_param": "limit"`). Pre-armored
  `page_size=100` calls then silently truncate — the realistic "silent
  breaking change inside a 'minor' bump" story — while REINTERPRET stays
  possible by construction (manifest re-read reveals `limit`; `page`
  iteration alone also recovers the full set).
- **total_count moves from the body to an `X-Total-Count` response header**
  (present from run start at rev 2, like X-API-Version). Deterministic
  decidability is preserved as a header read (`X-Total-Count !=
  len(items)`); curl-driven batch workers do not see headers unless they
  ask, so the fingerprint stops self-describing in the payload.
- Residual risk to re-measure at re-qualification: an orchestrator that
  plans page-iteration loops (`page=2` until empty) recovers without ever
  noticing the bump. Observed in 0/3 seeds (single-shot max-size calls
  were the universal pattern), but the re-qualification verdict decides.

## Standing

- RESOURCE_BUDGET is qualified on its primary host and its spec stands.
- The escrow draw (TASK 4) was **not** executed: the brief's draw is a
  superset over both categories, and drawing against a spec pending
  revision would bake soon-to-be-stale DV parameters into escrow. The
  draw script (analysis/holdout_escrow_draw.py) is committed and ready;
  it refuses to run twice.
- Data embargo and dev-run ledger stand; no v2 component exists or ran.

---

# APPENDIX — DV spec rev 2 re-qualification (same day; author ruling adopted)

The author ruling (2026-06-12) adopted the proposed revision: world_rev 3
— `page_size -> limit` rename at v2.0 (pre-armored `page_size` calls
silently truncate), totals in an `X-Total-Count` header only, three
decidability surfaces, mid-run fire window, post-size-below-collection
constraint encoded in the escrow script. Implementation: suite 113/113;
banked Phase 1 replay byte-identity 27/27 under rev-3 code
(runs/archaeology_v2/replay_check_rev3_regression.json). Re-qualification:
3 clean + 3 injected S1 on b1, rev-3 world, qseed-904/905/906, N=2
(recorded rationale: latest counter at which the wound stays live across
dispatch orders while call 1 still executes against v1.x). Driver:
analysis/holdout_requalification_dv.py; detail
runs/holdout_requalification_dv/summary.json; $1.99.

## Verdict: RE-QUALIFICATION FAILED — on both gates

| arm | seed | result | attribution | trace pointer |
|---|---|---|---|---|
| clean | 904 | **FAIL** | w1 turn-capped (exit 1 @ 15 turns); single-worker plan | runs/b1-S1-clean-s904 |
| clean | 905 | PASS | two-worker plan; w3r1 completed validate | runs/b1-S1-clean-s905 |
| clean | 906 | **FAIL** | w1 + w2r1 both turn-capped (exit 1 @ 15 turns) | runs/b1-S1-clean-s906 |
| injected | 904 | FAIL — **not wound-attributed** | enumeration at counter 1 (pre-bump); tax.py GET@7/PUT@13; failure = null-output/turn-cap fragility | runs/b1-S1-silent_minor_bump-s904 |
| injected | 905 | PASS | enumeration at counter 1 (pre-bump, full list); wound never live | runs/b1-S1-silent_minor_bump-s905 |
| injected | 906 | PASS | enumeration at counter 1 (`limit=200` pre-bump — ignored, full list at default 100); wound never live | runs/b1-S1-silent_minor_bump-s906 |

Clean: **1/3 PASS → the pre-committed fixture-weight STOP branch fired**
(clean fails >= 2/3). Wound-attributed injected failures: **0/3** (the
single non-wound failure explicitly not counted, per the ruling).
Injection fired at exactly N=2 via the counter path in 3/3 (instrument
clean); the rename mechanics are unit-verified
(tests/test_holdout_injections.py rev-3 block) — the mutation works; its
wound was unreachable.

## Root cause — one mechanism behind both gate failures

**The orchestrator consolidates b1 into a single worker in 5 of 6 plans**
(seeds 901–906; the task yaml seeds three worker steps and fan_out 4;
Sonnet plans `[('s1','w1')]` anyway). Recorded as benchmark texture per
author ruling #2 R4 (no fan-out mandate — prompting the plan shape would
contaminate orchestrator autonomy, the thing the benchmark measures):
**the sole clean pass of the spec-rev-2 batch (s905) was also the sole
multi-worker plan.**

1. *Fixture weight:* one worker x 8-file repo = 15–20 curls against the
   14-turn worker cap — clean b1 became a cap-boundary coin flip (today:
   3/6 across both revs; every clean failure is an exit-1-at-15-turns
   worker, never a checker-evidenced wrong migration).
2. *Wound reachability:* a single worker lists the repo as its FIRST
   call. At any N >= 2 the enumeration pre-dates the bump — H2's
   single-visit mechanism, now binding at N=2. The mid-run fire window
   and single-worker consolidation are jointly unsatisfiable on b1 as
   fixtured.

## STOP

Per the ruling: no third revision without a fresh author ruling. No
escrow draw (the superset spans both categories). Options that the next
ruling could weigh, listed without recommendation: slim the fixture pack
(e.g. 6 files / 2 pricing-annotated keeps a page-2 hidden site at
post<=4 while cutting ~4 calls); raise the b1 worker turn cap
(harness-comparability cost); harden the b1 prompt's fan-out mandate
(task-identity cost); retarget DV's primary host or fire rule (e.g.
N keyed to the redo wave). RESOURCE_BUDGET's qualified verdict is
unaffected. Session totals: $5.20 of the $25 cap.

---

# APPENDIX 2 — DV spec rev 3 re-qualification: QUALIFIED (author ruling #2)

Author ruling #2 (2026-06-12) resolved the STOP: R1 b1-scoped worker
turn cap 14 -> 24 (yaml `worker_max_turns`, a1/c1/d1 untouched, RB
conditions undisturbed; config diff verified scope); R2 fire rule N=1
uniform (deploy-time skew — the v1.x assumption is documentary; mid-run
withdrawn as category-inappropriate); R3 rename target hardened
`page_size -> page_limit` (closes the habit-typed `limit` escape, s906),
world_rev 4 with rev <= 3 frozen; R4 no fan-out mandate (consolidation
recorded as benchmark texture above). Implementation: suite 116/116;
banked Phase 1 replay byte-identity 27/27 under rev-4 code
(runs/archaeology_v2/replay_check_rev4_regression.json). Driver:
analysis/holdout_requalification_dv.py (qseed-907/908/909, N=1, post
page size 5, version 2.0.0); detail
runs/holdout_requalification_dv2/summary.json; $2.58.

## Verdict: PASS — clean 3/3, injected 3/3 FAIL BY THE WOUND

| arm | seed | result | failure signature (itemized) | trace pointer |
|---|---|---|---|---|
| clean | 907 | PASS | — (14 calls, migration complete, validate passed) | runs/b1-S1-clean-s907 |
| clean | 908 | PASS | — (14 calls) | runs/b1-S1-clean-s908 |
| clean | 909 | PASS | — (15 calls) | runs/b1-S1-clean-s909 |
| injected | 907 | **FAIL (wound)** | fired @1; lists @1 (bare, 5 files), @13 (page=1, 5); tax.py never touched; validate failed references_resolve x2; checker: `src/tax.py: stale annotation`. (A `page=2` call at counter 26 — the run's final call — revealed the tail too late to act.) | runs/b1-S1-silent_minor_bump-s907 |
| injected | 908 | **FAIL (wound)** | fired @1; the expected path verbatim: pre-armored `page_size=100` lists @1 and @12 both silently truncated to 5 files; tax.py never touched; validate failed x4; checker: `src/tax.py: stale annotation`. Worker output fragility co-occurred but is immaterial: the migration omitted tax.py in world state | runs/b1-S1-silent_minor_bump-s908 |
| injected | 909 | **FAIL (wound)** | fired @1; four bare lists (@1/@22/@27/@40), all truncated to 5; tax.py never touched; validate failed references_resolve x6 — the run died fighting the wound; checker: `src/tax.py: stale annotation` | runs/b1-S1-silent_minor_bump-s909 |

Wound attribution rule satisfied: every counted failure shows
truncated-data wrong output (hidden annotation site omitted from the
migration, evidenced in ground-truth world state by the checker's
stale-annotation line), not mere agent fragility — fragility co-occurred
in s908/s909 and could not have changed the outcome (the workers could
not see tax.py to migrate it). Instrument clean: injection fired at
exactly N=1 via the counter path in 3/3; clean arm under the new cap
passed 3/3 with zero turn-cap exits.

**DEPENDENCY_VERSION (spec rev 3) is QUALIFIED on its primary host b1.**
Both held-out categories now stand qualified; memo §5 condition (b)
proceeds to the escrow draw (decisions/holdout_escrow_record.md).
