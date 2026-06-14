# Sentinel Protocol v2 — Cadence Layer: Frozen Semantics (Design of Record)

**Status:** RATIFIED and FROZEN as deviation **D29** (complete frozen cadence
semantics); discharges the owed **D26** (probe-failure policy, Section 13). Any later
change to any knob below is a new logged deviation requiring separate measurement (per
cold-review finding 14). **No cadence behavior is implemented by this freeze** — the
scheduler stays NoOp, no ledger/barrier/allocator/scheduler code is written, and the
flag-off path stays byte-identical to Phase 1.

**Discipline:** category-blind throughout (Rule Zero). Every committed value is set from
the seen pilot corpus and first principles, never from the escrowed held-out two. The
matrix is a one-shot. Build, smoke-test, then fire.

**Ratification folds applied at freeze (vs. the draft; calibration in
`decisions/cadence_dial_calibration_2026-06-14.md`):**
1. **Section 3** — `remaining_dependent_work` is normalized to a fraction in (0,1] so the
   0.5 / 0.8 thresholds are meaningful (as a raw count it crossed 0.8 on short plans). The
   ordering is unchanged.
2. **Section 4** — the gated 12% denominator is pinned to the KG3 value **verbatim**
   (US dollars, `total_cost_usd`); the paid-probe-per-run-length **count** is reported as a
   submetric.
3. **Section 14** — a provisional surface defaults to high work-at-risk but is **capped
   below the blocking threshold**; it is promotable to blocking only after a barrier confirms
   it feeds an irreversible commit.
   Plus: **Section 13** retry budget `1` is recorded as a principled value (the seen
   transport-failure rate is zero), to be revisited as a fresh deviation once real transport
   rates exist.
**Held (considered, not applied):** the status fast path stays **status >= 400** (D28); the
"unexpected per compiled expectation" rewording was considered and HELD.

---

## 0. What this layer is

Cadence decides WHEN and WHETHER each compiled probe re-observes its surface, and
accounts for whether every load-bearing assumption was actually re-tested before
output. It supplies corroboration's confirming re-look (`ReObservationSource`,
satisfying `PRE_COMPLETION_SWEEP_DEPENDENCY`) and resolves the header-watched-probe
limitation that the trace-only `TraceReObservations` could not (a live source
carries headers).

Both cold passes converged on the same correction: cadence is a coverage-accounting
layer, and not only a scheduler. The scheduler decides when to look; the ledger
guarantees nothing is silently called covered. Sections 1 and 14 are the heart.

---

## 1. The coverage ledger (cold-review findings 1, 18)

Every load-bearing assumption carries a ledger entry keyed at the
assumption-and-shape level:

`(surface_id, assumption_id, required_shape, observation_id, verdict)`

"Covered" requires the compiled predicate to have been re-evaluated against a
sufficient observation. Touching the endpoint does not qualify; the observation
must contain the monitored shape (the field, status, value, structure, order, or
relation the assumption checks).

**Terminal states** (exactly one per load-bearing assumption before final output):

- `OBSERVED_FRESH` — re-evaluated after the last consume-affecting point, predicate holds.
- `OBSERVED_STALE_BUT_RECHECKED` — an early observation went stale, a later one re-confirmed it.
- `UNCOVERED_CAUTION` — could not be covered or confirmed within budget; flagged loud, routed to caution.
- `UNCOVERED_BLOCKING` — could not be covered on a surface whose work-at-risk crosses the blocking threshold (Section 4).
- `NOT_LOAD_BEARING` — retired with a proof (Section 17).

**Invariant:** `queued`, `prioritized`, `reserved`, `deferred`, or absent are
non-terminal and illegal at finalization. "Prioritized" is only an ordering
function over the work queue and can never stand as a coverage outcome.

---

## 2. Admission-time feasibility (cold-review finding 1)

At plan admission, compute the minimum coverage cost: at least one sufficient
observation per load-bearing assumption, and at least two for any assumption whose
work-at-risk crosses the high threshold (so a terminal-time wobble can still be
confirmed, Section 12).

If the minimum coverage lower bound exceeds the 12% budget, the run starts with
**declared coverage debt**: the surfaces that cannot fit are named `UNCOVERED` at
admission and reported up front. The run never discovers the debt at the end.

---

## 3. Work-at-risk (committed dial 1; cold-review finding 7)

Forward-looking, computed from the plan DAG, category-blind:

`work_at_risk = remaining_dependent_work × irreversibility × P(no_later_natural_observation) × actionability_if_caught_now`

- **remaining_dependent_work** *(committed, normalized at freeze)* = a fraction in **(0,1]**:
  the downstream-dependent **remaining** plan steps and branches of this assumption divided
  by the **total remaining** plan steps and branches at evaluation time. Sunk (already
  executed) work is reported as waste and never prioritizes, and is excluded from both
  numerator and denominator. Normalizing here keeps `work_at_risk ∈ [0,1]` so the 0.5 / 0.8
  thresholds below are meaningful; as a raw count the product crossed 0.8 on the short seen
  plans (4–5 steps), pushing nearly every write- or single-visit surface to blocking. **The
  ordering of surfaces is unchanged by the normalization.**
- **irreversibility** = `1.0` if any downstream step writes, commits, or has external side effects, else `0.3`.
- **P(no_later_natural_observation)** = `1.0` if the plan touches the surface once (single-visit, the dangerous class the pilot showed went invisible under passive monitoring), else `0.2` if the plan re-touches it. This term automatically prioritizes single-visit surfaces.
- **actionability_if_caught_now** = `1.0` if a replan can still avoid the dependent work, else `0.0` once the work is already consumed.

All four factors derive from the plan, never from the held-out categories. The two
multiplicative constants (`0.3`, `0.2`) are committed.

A surface is **high work-at-risk** (gets the paired-observation reserve, Sections 2
and 12) above `0.5`, and **blocking** (an uncovered miss routes to
`UNCOVERED_BLOCKING` rather than caution) above `0.8`. Both thresholds are committed.

*Ordering check on the seen surfaces (unchanged by the fold): single-visit-feeding-commit
rises to 0.5–1.0; write/commit-bearing rises; pure-read single-visit sits at ~0.3 (caution
+ speculative, recoverable wrong-report); naturally re-observed (re-touched) surfaces sink
toward 0. Single-visit and write-bearing surfaces do rise, as required.*

---

## 4. Budget (committed dial 2; cold-review findings 6, 12, 16)

**Hard cap (KG3, frozen — denominator pinned verbatim):** clean-run probe overhead under
12%. The KG3 gate as computed (`analysis/gates.py`, the only computation, 2026-06-11) is in
**US dollars** on the run's `total_cost_usd`:

```
clean5 = median(total_cost_usd) over treatment clean cells
clean1 = median(total_cost_usd) over S1 batch clean cells
overhead_ok  ⇔  (clean5 - clean1) / clean1 <= 0.12
```
verbatim KG3 line: `KG3 cost: S5 med $1.178952 vs S1 med $0.340831; success S5=4% S1=22%;
clean overhead OVER (<=12%) -> FAIL`. The gated denominator is therefore **dollars**
(`total_cost_usd`), specifically the **clean-cell batch (S1) median `total_cost_usd`** as the
divisor, with the treatment clean median in the numerator. Probe LLM and tool-call cost roll
into `total_cost_usd` as **waste, with no separate forgivable line** (frozen). Barrier delay,
matcher-normalization compute, and retries are measured and reported as a **submetric**, so
the gate's scope is explicit rather than quietly understating true overhead.

**Submetric (committed at freeze):** alongside the dollar gate, report the
**paid-probe-per-run-length count** (paid probe calls ÷ the run's own tool-call length). The
seen corpus shows the dollar cap **slack** (a probe is an LLM-free side-channel read ≈ $0
against an LLM-dominated worker cost) but the **count tighter** — the coverage lower bound is
5 observations against clean run lengths of 8–24 calls, i.e. 21–63% by raw count. The
**uncovered valve trips first on the shortest write-bearing run** (the 8-call task), where
even a few paid freshness re-looks are a large count fraction. The dollar slack **rides on
worker reads clearing the Section 8 equivalence gate**: the worker reads every load-bearing
surface as its job, so most coverage is harvested free and only freshness re-looks and
relation snapshots are paid. If harvest-first under-delivers (e.g. a re-read clobbered by a
later write before inspection), paid re-looks spike on the shortest run and the valve trips
there first.

**Three-way priority inside the cap** (replaces the old two-way split):

1. **Coverage** — the barrier hierarchy (Section 9) and relation barriers, sized at the admission lower bound. First claim.
2. **Live-anomaly confirmation** — the persistence re-look for already-detected wobbles. Incident response outranks exploration.
3. **Speculative mid-run probing** — re-observation of quiet single-visit surfaces for detection speed. Gets the remainder.

**Committed split (committed dial 2):** the coverage lower bound is reserved first
at admission. Of the post-coverage remainder, confirmation gets first claim capped
at `40%` so speculation cannot fully starve it, and speculation takes the rest. (Seen
confirmation demand is small — open wobbles dedup to ~0–3 per run, Section 11 — so the 40%
cap is a guardrail that rarely binds.)

**Uncovered valve:** when coverage plus open-wobble confirmation alone exceed the
cap, the lowest-work-at-risk surfaces are flagged `UNCOVERED` (caution, or blocking
above the Section 3 threshold) rather than breaching the cap. No budget breach, no
silent skip.

**Cost honesty (committed measurement rule, cold-review finding 12):**
`UNCOVERED_CAUTION` is never scored as a detection hit. An uncovered load-bearing
surface that coincided with a real injected change is scored as a **miss against
KG1 recall**, weighted by work-at-risk. The cost table reports a coverage-purchased
denominator alongside overhead. This closes the path where the system passes the
12% gate by declining to probe.

---

## 5. Re-observation sources

Three sources feed the ledger, all under the Section 4 budget:

- **Harvested (free), preferred.** A worker's own read of a watched surface, subject to the Section 8 equivalence predicate. Preferred over a dedicated probe where both are available, because a harvested read is the true worker view (cold-review finding 11).
- **Mid-run dedicated probes (paid).** For single-visit surfaces the worker does not re-touch, work-at-risk-gated and risk-ordered, funded by the speculative reserve.
- **Barrier sweeps (paid).** The guaranteed coverage backstop (Section 9).

---

## 6. Freshness (cold-review finding 8)

A surface is `OBSERVED_FRESH` for an assumption only if observed **after the last
plan point at which that assumption's truth could still affect output** (its last
consume-affecting point). Wall-clock or call-count "seen recently" does not qualify
and can never waive a barrier re-observation. The operational anchor is the
per-worker barrier (Section 9), which re-observes every output-dependency surface
of that worker regardless of how recently it was last seen.

---

## 7. (reserved)

---

## 8. Harvest observation-equivalence predicate (cold-review findings 4, 11)

A worker call refreshes coverage only if **all** hold:

- same surface identity;
- same projection and lens (the response contains the monitored field, value, order, structure, or relation the assumption checks);
- same auth and principal class;
- cache-fresh or origin-revalidated;
- side-effect-free (a read, never a write);
- raw response captured before the worker transforms it.

Anything less is telemetry, never coverage. A worker write, a paginated or partial
subset that excludes the monitored region, a different-auth read, or a stale cached
read does not refresh coverage. A worker request-side error (for example a 4xx from
a malformed worker call) belongs to the request rather than the surface, so it is
never treated as a surface anomaly and never trips the status fast path.

---

## 9. Barrier hierarchy (cold-review findings 2, 9)

Replaces the single global pre-completion sweep. Each barrier closes the ledger for
exactly what it consumes:

- **Worker barrier** — fires before each worker returns its payload, over that worker's output-dependency surfaces. Catches the early-finishing worker that a global end-of-run sweep would have missed.
- **Shard barrier** — before a shard aggregates, over the shard's shared surfaces.
- **Relation barrier** — before a cross-surface relation is consumed (Section 10).
- **Global output barrier** — before the orchestrator emits, over cross-worker and shared surfaces not already closed.

The union of per-worker barrier surfaces equals the load-bearing set, so this is
the same total coverage cost as a single global sweep, timed correctly.

---

## 10. Relation coverage objects (cold-review finding 10)

A relation assumption is a first-class coverage object. It is covered only by a
consistent snapshot, meaning all constituent surfaces observed within one bounded
window. If the observation windows do not overlap, the relation is `UNCOVERED` for
that relation even when each side is individually fresh, because two sides fresh at
different times is false confidence.

**VERIFY before build:** confirm the substrate's compiler emits relation probes
for the sixth change-shape. Richer ORDER and RELATION extraction is a known-weak
open item (compile-prompt section 9.1). If the compiler under-emits relations, the
shortfall is a measured residual, named in threats to validity (Section 21), and
not patched toward any category.

---

## 11. Wobble throttling (cold-review finding 13)

Defends against v1's flood re-emerging as confirmation demand:

- **Per-surface dedup:** at most one open wobble per `(surface_id, assumption_id)` at a time.
- **Coalescing:** multiple raw wobbles on the same surface within a window collapse to one open wobble.
- **Minimum confirmation interval:** a wobble's confirming re-look is the next scheduled re-observation rather than an immediate re-fire. Committed interval: the next barrier or harvest opportunity for that surface.
- **Risk-ordered confirmation:** within the confirmation reserve, highest work-at-risk confirmed first.

**Invariant:** a throttled-but-unconfirmed wobble still reaches a terminal ledger
state. It becomes `OBSERVED` if a later observation shows clean, or
`UNCOVERED_CAUTION` at finalization. No raw-count aggregation: this preserves D28's
anti-aggregation rule, where breadth of confirmed problems is the orchestrator's
replan decision rather than a corroboration-layer dial.

---

## 12. Terminal-time anomaly (cold-review finding 3)

A single ambiguous (non-status-coded) observation first seen at a barrier or the
global sweep, with no budget or time left to confirm, terminates as
`UNCOVERED_CAUTION`. It is never scored clean and never fires a one-shot interrupt,
which would violate the D28 persistence rule. High work-at-risk surfaces reserve a
paired observation at admission (Section 2) so they can be confirmed in time.
Status-coded anomalies keep the D28 fast path.

---

## 13. Probe-failure policy (discharges owed D26; cold-review finding 17)

A probe that times out, hits a transport error, returns an unreadable or partial
payload, or exhausts its retries terminates as `UNCOVERED_CAUTION`, or
`UNCOVERED_BLOCKING` above the Section 3 blocking threshold. It never vanishes into
inconclusive telemetry.

- **Retry budget:** `1` retry, then terminate uncovered. **Principled, not corpus-calibrated:**
  the seen deterministic mock has a **zero** transport-failure rate (no timeouts/5xx/429
  occur), so this value has no seen distribution to ground it and no effect on any seen run;
  it mirrors D28's "one confirming re-look" (a single corroborating attempt, not a loop). It
  becomes load-bearing only in the real-suite study and **is to be revisited as a fresh
  logged deviation once real transport-failure rates exist.**
- **Persistence threshold:** the D28 value (one confirming re-look), so a single transport failure retries once before terminating.
- **Transport-versus-world classification:** a transport failure (timeout, connection) is a failure to observe and routes to `UNCOVERED`. A clean response that violates the predicate is a genuine detection and routes to the typing and persistence path.

This section, together with the persistence threshold and the transport-versus-world rule
above, is the complete probe-failure policy that **discharges the owed D26**.

---

## 14. Provisional surface promotion (the lightweight path; cold-review finding 5)

The harvest watch already observes worker reads. When it observes a worker reading
an **unregistered** surface that feeds output, it creates a **provisional**
load-bearing record and that record enters the same ledger, terminal-state machine,
and barrier coverage as a compiled one.

**Provisional risk default (committed at freeze):** a provisional surface defaults to **high
work-at-risk** — at or above the Section 3 high-risk threshold, so it earns coverage and the
paired-observation reserve — but is **capped below the blocking threshold**, so it **cannot
by itself trigger a hard halt** (`UNCOVERED_BLOCKING`). It is promotable to blocking **only
after a barrier confirms it feeds an irreversible commit** (a downstream write/commit/
external side effect, per the Section 3 irreversibility axis). This keeps fail-safe coverage
of unknown surfaces without letting a single off-plan incidental read halt the whole run.

**Replan garbage collection (cold-review finding 15):** a surface is retired to
`NOT_LOAD_BEARING` only with a retirement proof, meaning no live artifact, worker
output, pending decision, or relation still depends on it. Otherwise it is carried
forward through finalization. This is consistent with the keep-not-flush replan
behavior already built in D28.

**Residual (named, measured, not patched):** a surface a worker depends on without
any observable read stays unreachable. That residual is a threat to validity
(Section 21), measured by the dependency-graph audit (Section 19), rather than
papered over.

---

## 15. (folded into Section 14)

---

## 16. Rule Zero and embargo

Category-blind throughout: no quota, version, or resource-specific behavior
anywhere in the scheduler or ledger. Synthetic and seen-category fixtures only. The
flag-off path stays byte-identical to Phase 1. Nothing is ever tuned toward the
escrowed two. The matrix is a one-shot; readiness pulls the date, and the build is
smoke-tested before it fires.

---

## 17. The full frozen knob table (cold-review finding 14)

Every behavior that affects an outcome is committed here. The freeze is incomplete
if any is left implicit. Discriminator: replay one trace under two builds with
identical split ratio and work-at-risk formula but different hidden choices; if
outcomes differ, a knob is missing from this table.

| Knob | Committed value | Source |
|---|---|---|
| Budget cap | under 12% clean overhead; KG3 denominator `(clean treatment median − clean S1 batch median) / clean S1 batch median` of **`total_cost_usd`** (US dollars) `<= 0.12`; probe cost in `total_cost_usd` as waste, no separate line | KG3 (frozen); `analysis/gates.py` |
| Overhead denominator | `total_cost_usd` (US dollars); **paid-probe-per-run-length count reported as submetric**; barrier/matcher/retry as reported submetric | finding 16; D29 fold |
| Budget priority | coverage, then live-wobble confirmation, then speculative | finding 6 |
| Split ratio (dial 2) | coverage lower bound first; confirmation capped at `40%` of remainder; speculation the rest | finding 6 |
| Work-at-risk formula (dial 1) | `remaining_work(normalized (0,1]) × irreversibility × P(no-later-obs) × actionability` | finding 7; D29 fold |
| remaining_dependent_work | normalized fraction in (0,1] = downstream-dependent remaining steps/branches ÷ total remaining steps/branches at evaluation time; sunk work excluded | D29 fold |
| irreversibility constant | `1.0` (downstream write/commit/side effect) / `0.3` (else) | finding 7 |
| P(no-later-obs) constant | `1.0` single-visit / `0.2` re-touched | finding 7 |
| high-risk threshold | `0.5` (paired-observation reserve) | finding 3 |
| blocking threshold | `0.8` (uncovered routes to blocking) | finding 3 |
| Freshness rule | observed after last consume-affecting point; recency cannot waive a barrier | finding 8 |
| Harvest equivalence | the six-condition predicate; reads only; worker errors never trip the status path | findings 4, 11 |
| Barrier set | worker, shard, relation, global | findings 2, 9 |
| Relation coverage | consistent snapshot, else uncovered for that relation | finding 10 |
| Wobble dedup | one open wobble per `(surface, assumption)` | finding 13 |
| Confirmation interval | next scheduled re-observation | finding 13 |
| Persistence threshold | one confirming re-look | D28 |
| Status fast-path threshold | status >= 400, well-formed observations only | D28 + finding 4 |
| Terminal-time singleton | ambiguous singleton routes to `UNCOVERED_CAUTION` | finding 3 |
| Probe retry budget | `1` retry, then uncovered; principled (seen transport rate 0), revisit on real rates | D26 / finding 17; D29 fold |
| Transport-vs-world | transport failure uncovered; predicate violation a detection | D26 / finding 17 |
| Provisional promotion | unregistered output-feeding read becomes a provisional record at **high work-at-risk, capped below blocking**; promotable to blocking only after a barrier confirms an irreversible-commit dependency | finding 5; D29 fold |
| Replan retirement | retire only with a no-dependency proof, else carry forward | finding 15 |
| UNCOVERED accounting | never a hit; uncovered with real change is a recall miss, risk-weighted | finding 12 |

---

## 18. (folded into the table)

---

## 19. Dependency-graph audit (under D25 quarantine)

Built escrow-side so it never feeds compiler iteration (D25). For every completed
run it:

1. reconstructs the output-dependency graph from raw tool calls and asserts every dependency surface is in the registry, counting any absentee as a measured silent miss (the Section 14 residual);
2. asserts every load-bearing assumption has exactly one terminal ledger state;
3. checks coverage-purchased against overhead for cost honesty;
4. runs the Section 17 two-build replay discriminator.

---

## 20. (reserved)

---

## 21. Threats to validity (paper content)

These are concrete instances of the observation bound the paper studies, so naming
and measuring them strengthens the headline:

- **Unobservable dependency (finding 5 residual):** a surface depended on without any observable read. Measured by Section 19.
- **Side-channel view divergence (finding 11):** a dedicated probe may see a different world than the worker (auth, cache, replica, session). Harvested worker-view observations are preferred; the back-to-back diff is an audit technique rather than a runtime requirement.
- **Relation under-emission (finding 10):** if the compiler under-emits relation probes, those relations fall outside coverage. Measured, not patched.

---

## Build order after this freeze (no code in the freeze itself)

1. **Done at freeze:** D29 logged, D26 discharged (Section 13), KG3 denominator pinned
   (Section 4). The scheduler stays NoOp; flag-off byte-identical to Phase 1.
2. Ledger and terminal-state machine (Section 1), with the dependency-graph audit harness (Section 19) under quarantine.
3. Live `ReObservationSource` carrying headers; harvest equivalence gate (Section 8).
4. Barrier hierarchy (Section 9); admission feasibility (Section 2).
5. Budget allocator and work-at-risk (Sections 3, 4); wobble throttling (Section 11).
6. Provisional promotion and replan GC (Section 14).
7. Smoke-test the full stack, flag-off byte-identity, $0-LLM where deterministic.
8. Arm registration (V2, V2J, S1, S2, S3), then the one-shot matrix.
