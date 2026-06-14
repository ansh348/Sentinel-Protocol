# Cadence Dial Calibration — Recommendations (2026-06-14)

**Task:** ground every `PROPOSED` value in `cadence_semantics_D29_draft.md` in the SEEN
pilot corpus and first principles, and recommend. **This is a recommendation only — no
spec edit, no freeze.** Anshu ratifies.

**Method.** Calibrate by principle and robustness, using the seen corpus to check
feasibility and coherence, never to optimize a metric. Legitimacy test applied to every
value: *would I set it this way having never seen a recall number.* Where a robust value
and a seen-corpus-optimal value would differ, the robust value is recommended.

**Rule Zero (held — see close).** Reasoning is restricted to the six general change-shapes
(field vanished, status moved, structure changed, value moved, order scrambled, relation
broke) and to run geometry (run lengths, surface-visit patterns, probe-cost distribution,
wobble rate, transport-failure rate). No value below is justified by, or tuned toward, any
named failure category, seen or held-out. No escrowed/held-out file was read; nothing that
touches the held-out set was run; no dev-run was performed (pure analysis of existing seen
artifacts).

---

## A. Seen-corpus geometry used (category-blind), with artifacts

| Geometry fact | Value (seen corpus) | Artifact |
|---|---|---|
| Load-bearing assumptions per task | **5** (a1–a5), all four seen tasks | `tasks/{a1,b1,c1,d1}.yaml` |
| Clean run length (tool calls), median | **a1 24 · b1 8 · c1 12 · d1 21** | `decisions/manipulation_table_s1_seed1.md` |
| Run length under noise grind (S5) | up to **107–129** calls (sentinel-induced grind, not clean work) | `archaeology_v2.md §D`; `archaeology_v1.md §4` |
| Surface-visit pattern | mix of **single-visit reads** (read once, early) and **re-touched** surfaces (re-read every call); single-visit was the class that went invisible under passive monitoring | `archaeology_v1.md §1, §5`; `archaeology_v2.md §B` |
| Write/commit-bearing tasks | b1 (PUT renames + validate gate); c1/d1 (validate → package commit). a1 is pure read-aggregation (no external write) | `tasks/{a1,b1,c1,d1}.yaml` plan blocks |
| Paid-probe flood under *naive* heartbeat-k cadence | **378–2322** probe calls/run, **16–22×** the run's own traffic (a1 k=2: 2322 vs 107) | `archaeology_v2.md §E.1, §E.3` |
| Re-touch can fail to cover (write-side clobber) | a re-read that a later PUT overwrote, sight-unseen | `decisions/b1_requalification_2026-06-12.md` (s911) |
| Wobble / noise rate | **18 unattributable interrupts / 39 cells**; **14/18 on field-shape (structure/value) reads of healthy traffic**; one cell stormed **172 fires** (collapses under D28 dedup to a few distinct `(surface,assumption)`) | `archaeology_v1.md §3`; `archaeology_v2.md G12` |
| Transport-failure rate | **0** — the deterministic mock has no transport weather (timeouts/5xx/429 never occur) | `archaeology_v2.md §C, §E`; `deviations.md` D26 |
| Worlds replay byte-identically | 27/27 injected cells | `archaeology_v2.md §0(iii)`, `replay_check.json` |

Two framing facts drive most of what follows. (1) The worker **already reads every
load-bearing surface as its job**, so most coverage can be *harvested* free; the paid
probes are the freshness re-looks and relation snapshots, not the bulk of coverage. (2) The
budget denominator is **USD** (probe LLM + tool-call cost booked as waste); in the mock a
probe is an LLM-free side-channel read ≈ $0, so the call-count view and the USD view diverge
sharply — and the spec's own submetric is what surfaces that gap.

---

## B. Section 3 — Work-at-risk

### B.0 Does the four-factor formula order the SEEN surfaces sensibly?

**Verdict: ordering YES, threshold coherence NO (one required fix).**

Holding the multiplicative form and walking the seen surface classes (work-at-risk =
`remaining_dependent_work × irreversibility × P(no_later_obs) × actionability`):

| seen surface class | irrev | P(no-later-obs) | actionable | rises? |
|---|---|---|---|---|
| single-visit read feeding a commit (b1 settings→PUT; c1/d1 passage→validate/package) | 1.0 | 1.0 | 1.0 | **highest** ✓ |
| write/commit-bearing, re-touched | 1.0 | 0.2 | 1.0 | high ✓ |
| single-visit read feeding only a report (a1 inventory/pricing/shipping) | 0.3 | 1.0 | 1.0 | mid ✓ |
| re-touched read feeding only a report | 0.3 | 0.2 | 1.0 | low ✓ |
| already-consumed (sunk) | — | — | 0.0 | zero ✓ |

So **single-visit and write/commit-bearing surfaces do rise**, exactly as intended, and the
naturally-re-observed (re-touched) surfaces correctly sink. The ordering is principled and
category-blind.

**But the thresholds 0.5 / 0.8 are incoherent as written**, because the first factor is a
**raw count** ("count of not-yet-executed plan steps … downstream"), while the other three
are in [0,1] and the thresholds read as fractions of a [0,1] score. In the seen plans
(4–5 steps), `remaining_dependent_work` is 1–4, so e.g. a single-visit read feeding a commit
with 3 steps downstream scores `3×1.0×1.0×1.0 = 3.0`, and even a pure-read single-visit
scores `3×0.3×1.0×1.0 = 0.9 > 0.8` → **blocking**. With raw counts, almost every
write-bearing or single-visit surface clears 0.8 and routes to `UNCOVERED_BLOCKING` whenever
budget is tight: a **flood-to-blocking** failure mode on the short tasks.

**Recommendation (required for coherence):** normalize `remaining_dependent_work` to (0,1] —
the fraction of the plan's downstream steps still pending for this assumption — so
work-at-risk ∈ [0,1] and the multiplicative form reads as "fraction of maximal risk." Under
that normalization the class table above maps cleanly onto the thresholds (worst class → 1.0,
half-consumed single-visit-commit → 0.5, re-touched pure-read → 0.06), and 0.5 / 0.8 become
meaningful. With 4–5-step plans the normalized factor is coarse (quantized), but the ordering
holds; the coarseness is a measured residual, not a tuning target. This is a legitimacy-test
pass: I would normalize regardless of any recall number, purely for the score to mean
something.

### B.1 irreversibility constant `PROPOSED 0.3`
- **(a) verdict:** well-grounded (as a prior); it is the dial that decides whether a
  *pure-read* single-visit surface clears the high-risk bar.
- **(b) seen corpus:** the seen tasks split cleanly into commit-bearing (b1 PUTs; c1/d1
  validate→package) and pure-read aggregation (a1). A wrong read that only reaches a report
  is recoverable (replan/re-run); a wrong read feeding a PUT/commit is not. The corpus also
  shows a re-touch is not a guarantee of coverage (b1 s911: a later PUT clobbered the read),
  which is why the *irreversibility* axis, not just re-observability, carries weight.
- **(c) recommended: keep 0.3.** First principles: a non-committing assumption should be
  *meaningfully* less urgent than a committing one but not negligible. 0.3 places pure-read
  single-visit at 0.30 (normalized, full work remaining) — below the 0.5 paired-reserve bar,
  i.e. "caution + speculative probing," which matches the recoverable-wrong-report stakes.
- **(d) confidence: medium. Sensitivity: moderate at one boundary.** Anywhere in **0.2–0.4**
  the ordering is unchanged; the *only* consequential crossing is raising it to ≥0.5, which
  would pull pure-read single-visit surfaces into the (2-probe) paired reserve and tighten
  the budget on short runs. Below 0.2 it under-weights recoverable single-visit reads.
- **(e) failure mode:** at ≥0.5 combined with the high-risk bar, pure-read single-visit
  surfaces all demand paired observation → on the 8-call task this alone can exceed the cap
  → uncovered-valve trips on otherwise-cheap reads.

### B.2 P(no_later_natural_observation) constant `PROPOSED 0.2`
- **(a) verdict:** well-grounded.
- **(b) seen corpus:** single-visit surfaces were the dangerous, invisible-under-passive
  class; re-touched surfaces were re-observed for free. But re-touch ≠ guaranteed coverage:
  the seen corpus has a re-read that a later write overwrote before it was inspected
  (b1 s911), so a re-touched surface still carries residual risk that no *useful* later
  observation lands.
- **(c) recommended: keep 0.2** (i.e. single-visit 1.0 vs re-touched 0.2). First principles:
  a re-touched surface is mostly self-covering, so the probability of *no* later natural
  observation is small but non-zero; 0.2 encodes "usually re-observed, occasionally not."
  Zero would wrongly treat every re-touch as a guarantee (contradicted by s911).
- **(d) confidence: medium-high. Sensitivity: low.** Anywhere in **0.1–0.3** re-touched
  surfaces stay well below single-visit ones; outcomes barely move. Exact 0.2 is fine.
- **(e) failure mode:** only at the extremes — 0.0 would silently trust write-clobbered
  re-reads (the s911 pattern); ≥0.5 would over-probe naturally-covered surfaces and waste
  budget that single-visit surfaces need.

### B.3 high-risk threshold `PROPOSED 0.5` (paired-observation reserve)
- **(a) verdict:** well-grounded (conditional on the B.0 normalization).
- **(b) seen corpus:** the paired reserve exists so a terminal-time wobble on a high-stakes
  surface can still be confirmed (D28: one confirming re-look). The surfaces that most need
  it are single-visit-feeding-commit; under the normalized formula those sit at 0.5–1.0.
- **(c) recommended: keep 0.5** as the midpoint that separates "reserve a second look" from
  "single look + speculative." It cleanly admits single-visit-commit and write-bearing
  surfaces while excluding recoverable pure-reads.
- **(d) confidence: medium. Sensitivity: moderate (budget-coupled).** 0.5→0.4 pulls more
  surfaces into the 2-probe reserve → higher admission cost → more uncovered-valve trips on
  the 8–12-call tasks; 0.5→0.6 frees budget but leaves more mid-stakes surfaces single-look.
  Because the shortest seen run is 8 calls, lean **not below 0.5**.
- **(e) failure mode:** set too low, the paired reserve doubles coverage cost on short runs
  and the valve trips on surfaces that did not need two looks (a starve-by-over-reserving).

### B.4 blocking threshold `PROPOSED 0.8` (uncovered → blocking)
- **(a) verdict:** well-grounded.
- **(b) seen corpus:** blocking is the strongest action (refuse to finalize). The v1
  pathology was *over*-intervention (noise storms, replan churn, 7/9 clean failures
  sentinel-induced); the safe direction for any hard-halt threshold is therefore
  conservative — block only the near-maximal, irreversible-and-unconfirmable case.
- **(c) recommended: keep 0.8.** Under the normalized formula, 0.8 is reached only by
  single-visit-feeding-commit with most work still pending and a live action window — the
  one class where finalizing blind is genuinely unrecoverable. Everything else routes to
  caution, not a halt.
- **(d) confidence: medium-high. Sensitivity: low-to-moderate.** Lowering toward 0.6
  introduces a new failure (runs that refuse to finalize → availability loss), which is the
  v1 over-intervention pattern in a new guise; raising toward 0.9 means it essentially never
  blocks. 0.8 is the conservative, defensible choice.
- **(e) failure mode:** with the *un-normalized* formula (B.0), 0.8 is crossed by almost
  everything → mass blocking. This is the single most important reason to adopt the B.0
  normalization before freezing either threshold.

---

## C. Section 4 — Budget

### C.1 Budget feasibility (coverage lower bound + confirmation under 12%)
- **(a) verdict:** feasible under the frozen USD denominator; **tight, and valve-dependent,
  under a raw call-count view** (the submetric, and the real-suite worst case).
- **(b) seen corpus:** coverage lower bound = 5 sufficient observations/run (one per
  assumption; two for high-risk). By **raw call count** against clean run length that is
  5/24 (21%), **5/8 (63%)**, 5/12 (42%), 5/21 (24%) — all above 12% *if every observation
  were a paid probe*. They are not: the worker reads every load-bearing surface as its work,
  so the **worker barrier harvests** those reads for free; the paid probes are the freshness
  re-looks (single-visit read early, consumed late) and relation snapshots. By **USD**, a
  probe is an LLM-free side-channel read ≈ $0 against an LLM-dominated worker cost, so the
  paid overhead is ≈ 0% — far under 12%. The naive-cadence flood (378–2322 calls) was a
  *cadence* artifact (probe every k calls × every surface), which the barrier cadence
  removes by construction (one sweep over output-dependency surfaces at the barrier).
- **(c) recommended:** keep the **12% USD cap** and the harvest-first priority; **add the
  paid-probe-count / run-length ratio as the reported submetric** (the spec already commits
  barrier/matcher/retry as a submetric — extend it to this ratio). It is the only view that
  makes the short-run tightness visible *before* the one-shot matrix, and it is where the
  real-suite (non-free tool calls) will bite first.
- **(d) confidence: high (USD) / medium (call-count). Sensitivity: structural.** Under USD
  the cap is slack; under call-count the binding case is the 8-call write-bearing task, where
  harvest-first must deliver or the valve trips.
- **(e) failure mode:** if harvest-first under-delivers — e.g. a re-read clobbered by a later
  write (the s911 pattern), so the harvested observation is not *fresh* at the consume point —
  paid freshness re-looks spike on the shortest task and the valve trips there first. Name
  this as the expected first valve-trip locus.

### C.2 Uncovered-valve trip frequency (seen geometry)
- Under the **USD** denominator: **rare** — coverage + confirmation is ≈-free, so the cap is
  essentially never exceeded; the valve trips only if a run needs many *paid* probes, which
  the barrier cadence avoids.
- Under the **call-count** submetric: trips **on the shortest write-bearing runs first**
  (the 8-call task), where even a few paid freshness re-looks are a large fraction of run
  length. This is the honest, category-blind feasibility statement: the valve is a real,
  occasionally-exercised mechanism on short runs, not dead code — which is the correct design
  (Section 2's declared coverage debt is meant to fire there).

### C.3 confirmation-reserve cap `PROPOSED 40%` of the post-coverage remainder
- **(a) verdict:** well-grounded as a guardrail; **low sensitivity** on the seen corpus.
- **(b) seen corpus:** confirmation demand = one re-look per distinct open
  `(surface,assumption)` wobble (D28 dedup/coalesce). The raw noise was concentrated (14/18
  unattributable interrupts on field-shape reads; one 172-fire storm) but **collapses to a
  handful of distinct surfaces per run** after dedup — realistically 0–3 open wobbles/run.
  Three re-looks is a tiny claim on the remainder, so a 40% cap is almost never binding.
- **(c) recommended: keep 40%.** First principles: confirmation (incident response) should
  outrank speculation but must not be able to *fully* starve it, or a noisy run converts the
  whole remainder into confirmation demand — v1's flood re-emerging as confirmation cost.
  40% gives confirmation a strong-but-bounded first claim. The value passes the legitimacy
  test (it is a split prior, independent of any recall number).
- **(d) confidence: medium-high. Sensitivity: low.** Because seen confirmation demand is
  small, outcomes barely move across 30–50%. Prefer the robust 40% over any seen-optimal
  point (there is no meaningful optimum to chase).
- **(e) failure mode:** only in a hypothetical high-wobble run not present in the seen
  geometry would a *too-low* cap defer genuine confirmations to `UNCOVERED_CAUTION`; the
  D28 dedup makes that unlikely, and the terminal-state machine keeps it safe (deferred ≠
  dropped).

---

## D. Section 11 — Minimum confirmation interval (`PROPOSED` next scheduled re-observation)

- **(a) verdict:** well-grounded; this is the robust choice (no magic number).
- **(b) seen corpus:** the 172-fire storm and 14/18 field-shape false interrupts were
  driven by **immediate re-fire** on the same transient state; coalescing + "wait for the
  next natural look" is the direct structural fix, and it is exactly what D28 already
  encodes (persistence over time, not a second concurrent signal).
- **(c) recommended: keep "next barrier or harvest opportunity."** First principles:
  re-confirming at the next *scheduled* re-observation (a) lets transients heal (so a wobble
  that self-resolves is never escalated), and (b) adds no dedicated re-probe cost (the
  re-look is a barrier/harvest that was going to happen anyway). If no further scheduled
  observation exists before output (single-visit, no later barrier), Section 12 correctly
  terminates the wobble as `UNCOVERED_CAUTION` — never promoted blind. The mechanism is
  coherent with the terminal-state machine and with the budget (it spends nothing extra).
- **(d) confidence: high. Sensitivity: low.** As an event anchor rather than a numeric
  interval it has no brittle constant to mis-set; the only design choice is "next scheduled"
  vs "immediate," and the seen corpus is decisive against immediate.
- **(e) failure mode:** none new. The one edge — a high-work-at-risk single-visit surface
  whose "next opportunity" is the final barrier — is exactly what the Section 2 paired
  reserve and Section 12 terminal rule exist to catch; the interval defers to them correctly.

---

## E. Section 13 — Probe retry budget (`PROPOSED 1`)

- **(a) verdict:** well-grounded **by principle; NOT calibratable against the seen corpus.**
- **(b) seen corpus:** the deterministic mock has a **zero** transport-failure rate (no
  timeouts/5xx/429 ever occur). The retry budget therefore has **no seen distribution to
  ground it** and **no effect on any seen run** — it becomes load-bearing only in the
  real-suite study (consistent with the owed D26, which D29 discharges).
- **(c) recommended: keep 1.** First principles: one retry separates a single transient blip
  from a persistent failure at minimal cost (2 attempts total, one extra latency unit). Zero
  retries makes a single transient drop a surface to `UNCOVERED` (over-conservative; more
  spurious coverage debt); two or more adds cost/latency and risks masking a genuinely
  persistent failure as "still trying." This mirrors D28's "one confirming re-look" — a
  single corroborating attempt, not a loop — and is the standard retry-once default.
- **(d) confidence: high (principle) / N/A (seen). Sensitivity: nil on the seen corpus**
  (rate 0); real on the real suite, where it should be revisited as a fresh logged deviation
  if measured transport-failure rates warrant.
- **(e) failure mode (real-suite only):** with a non-trivial transient rate, retry=1 will
  occasionally still route a recoverable surface to `UNCOVERED` (a transient that outlasts
  one retry) — acceptable and safe (uncovered, never a false detection), but worth measuring
  before any increase. Flag: this is the one dial whose seen-corpus grounding is *absent by
  construction*; it rides on principle plus the real-suite revisit.

---

## F. Section 17 table — remaining arbitrary or internally incoherent values

- **Work-at-risk first factor vs thresholds (the headline coherence flag):** see B.0 —
  `remaining_dependent_work` is a raw count but 0.5/0.8 read as [0,1] fractions. **Normalize
  before freeze**, else mass flood-to-blocking. This is the one *required* change.
- **`Provisional promotion` at "maximum work-at-risk" + `blocking threshold 0.8`
  (flood-to-blocking risk):** an unregistered output-feeding worker read is promoted at
  *max* risk; combined with the 0.8 blocking rule, a single off-plan incidental read could
  route to `UNCOVERED_BLOCKING` and **halt the whole run** — re-introducing v1-style
  over-intervention through a new door. The seen plans are explicit (off-plan reads are rare),
  so this is latent, not observed, but it is incoherent with the conservative-blocking stance
  of B.4. **Recommend:** provisional surfaces default to **high-risk (≥0.5, paired reserve)
  but capped below blocking (<0.8)** until a barrier or the dependency-graph audit confirms
  they genuinely feed an irreversible commit. Fail-safe coverage without fail-*stop*.
- **`Status fast-path threshold: status >= 400` vs the design's "unexpected per compiled
  expectation":** the table says ≥400, but the cadence doc's own §5.3 rationale (and the
  status-moved change-shape) is "a status that is *unexpected for that surface at the current
  plan phase per a compiled expectation*," not a bare ≥400. The §8 exclusion (worker
  request-side 4xx is request-not-surface) covers the worst case, but a phase-expected 4xx in
  a branch could still trip a bare ≥400. On the seen corpus this is empirically safe (zero
  false interrupts carried status ≥400; `archaeology_v2.md` G10), so it is a **wording
  coherence** item, not a behavior bug. **Recommend:** align the table cell with §5.3
  ("status outside the compiled expectation for the surface, well-formed observations only").
- **`high-risk` paired reserve (2 obs) interaction with the 8-call task:** not a value error,
  but a coherence note — Section 2's "two observations for high work-at-risk" multiplies
  coverage cost on the shortest run; it is consistent with C.1/C.2 (the valve trips there
  first) and should be reported via the C.1 submetric so the tightness is explicit pre-matrix.
- **Everything else in the table** (overhead denominator, three-way priority, freshness rule,
  harvest equivalence, barrier set, relation coverage, wobble dedup, persistence threshold,
  terminal-time singleton, transport-vs-world, replan retirement, UNCOVERED accounting) is
  **internally coherent** and either inherited from D28/KG3 (already ratified) or a structural
  rule with no free numeric dial. No further arbitrary constant found.

---

## G. Inline summary table

| value | proposed | recommended | grounding | confidence |
|---|---|---|---|---|
| irreversibility constant | 0.3 | **0.3 (keep)** | recoverable wrong-report vs irreversible commit; robust in 0.2–0.4; the dial for pure-read single-visit reserve eligibility | medium |
| P(no-later-obs) constant | 0.2 | **0.2 (keep)** | re-touch usually self-covers but not always (write-clobber seen, b1 s911); robust 0.1–0.3 | medium-high |
| high-risk threshold | 0.5 | **0.5 (keep; do not lower)** | midpoint separating paired-reserve from single-look; lowering tightens the 8-call budget | medium |
| blocking threshold | 0.8 | **0.8 (keep)** | conservative hard-halt; safe direction given v1 over-intervention | medium-high |
| work-at-risk formula | count × 3 multipliers vs [0,1] thresholds | **normalize `remaining_dependent_work` to (0,1]** (ordering already correct) | high |
| confirmation-reserve cap | 40% of remainder | **40% (keep)** | bounded-but-strong claim; seen wobble demand small (0–3/run) so cap rarely binds | medium-high |
| budget feasibility | under 12% | **feasible under USD denominator; add paid-probe/run-length submetric** | high (USD) / medium (count) |
| uncovered valve frequency | — | **rare (USD); trips on shortest write-bearing run first (count)** | medium |
| min confirmation interval | next scheduled re-observation | **keep (robust event anchor; matches D28)** | high |
| probe retry budget | 1 | **1 (keep)** — principle only; seen transport-failure rate = 0 | high (principle) / N/A (seen) |
| provisional promotion risk | maximum (→ can hit 0.8 blocking) | **cap below blocking (<0.8) until confirmed load-bearing** | medium |
| status fast-path wording | status ≥ 400 | **align to §5.3 "unexpected per compiled expectation"** (seen-safe; wording) | medium |

---

## H. Rule Zero confirmation

- **Category-blind:** every value above is grounded in the six change-shapes and run
  geometry only (run lengths, single-visit vs re-touched, write/commit-bearing, probe-cost
  distribution, wobble rate, transport-failure rate). No recommendation references, optimizes
  for, or was set by a named failure category (seen or held-out). The seen per-category
  archaeology tables were read for *geometry* (visit patterns, run lengths, noise counts),
  never as category targets.
- **No held-out read or run:** no escrowed/held-out parameter file was opened; nothing that
  touches the held-out set was executed; the one-shot matrix was not spent.
- **No dev-run:** this was pure analysis of existing seen artifacts (`tasks/*.yaml`,
  `archaeology_v1.md`, `archaeology_v2.md`, `decisions/*.md`). No world was instantiated, no
  v2 component was run, $0 LLM — so no dev-run-ledger entry is owed.
- **Calibrated by principle and robustness:** each value passes the legitimacy test (set
  without reference to a recall number); robust values were preferred over seen-optimal ones.

**Not frozen. Spec not edited.** Anshu ratifies; on ratification this folds into D29 (and
discharges D26). STOP.
