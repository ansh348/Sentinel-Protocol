# v2 Cadence Layer — Build Session Report (2026-06-14)

**Scope:** implement the frozen **D29** cadence semantics (decisions/cadence_semantics.md)
behind the v2 flag — coverage ledger, live re-observation source + harvest gate, barrier
hierarchy, budget allocator + work-at-risk, wobble throttling + probe-failure, provisional
promotion + replan GC, UNCOVERED accounting — plus the live scheduler policy, the §17
two-build replay discriminator, and the §19 dependency-graph audit. DETERMINISTIC, $0 LLM,
category-blind. Source of truth built to verbatim; where the directive and the doc agreed
they were built together, no disagreement arose.

**Commits:** master, `c70…`→ this report. Chain (one per checkpoint):
C1 ledger+work-at-risk → C2 harvest → C3 barriers → C4 budget → C5 throttle → C6
provisional → C7 accounting → close. Prior state: `903ed1d` (D29 freeze).

---

## What was built (package `sentinel_v2/cadence/`)

- **C1 — ledger + terminal-state machine + admission + work-at-risk** (`ledger.py`,
  `workatrisk.py`). Five terminal states; exactly-one-per-assumption invariant
  (queued/prioritized/deferred illegal at finalization); the 5-tuple key. Admission
  computes the minimum-coverage lower bound (≥1/assumption, ≥2 for high-risk) and declares
  coverage debt up front on the lowest-work-at-risk surfaces. Work-at-risk is the frozen
  four-factor product with the **normalized** first factor (fraction in (0,1]); thresholds
  0.5 / 0.8. (Work-at-risk lands at C1 because admission depends on it — the doc order.)
- **C2 — live header-carrying ReObservationSource + harvest gate** (`harvest.py`). The
  six-condition equivalence predicate; anything less is telemetry, never coverage. A
  malformed worker 4xx (and any write's 4xx) is request-side and never becomes a surface
  observation → never trips the D28 status fast path; a well-formed surface 401 stays a
  coverage observation that does. `LiveReObservationSource` satisfies corroboration's
  Protocol + `PRE_COMPLETION_SWEEP_DEPENDENCY` and carries headers.
- **C3 — barriers + freshness + relation coverage** (`barriers.py`). Worker/relation/global
  barriers each close the ledger for what they consume; worker barriers run in finish order
  (an early-finishing worker is not missed); their union is the load-bearing set. Freshness
  = strictly after the last consume-affecting point (recency cannot waive). Relations are
  first-class, covered only by a consistent snapshot, else UNCOVERED for that relation.
- **C4 — budget allocator + work-at-risk** (`budget.py`). KG3 gate pinned verbatim:
  `(clean_treatment − clean_batch)/clean_batch ≤ 0.12` (US dollars). Three-way priority
  (coverage → confirmation capped at 40% of remainder, risk-ordered → speculation); the
  uncovered valve drops lowest-work-at-risk surfaces rather than breach; the
  paid-probe-per-run-length COUNT is the reported submetric.
- **C5 — wobble throttling + terminal-time + probe-failure** (`throttle.py`). One open
  wobble per (surface, assumption), repeats coalesce; confirmation is the next scheduled
  re-look (not immediate), via D28 persistence (count-invariant); unconfirmed →
  UNCOVERED_CAUTION. Terminal-time ambiguous singleton → UNCOVERED_CAUTION (status-coded
  keeps the fast path). Probe-failure: retry 1, transport failure → UNCOVERED; predicate
  violation on a clean response → detection (discharges D26 operationally).
- **C6 — provisional promotion + replan GC** (`provisional.py`). An unregistered
  output-feeding read becomes a provisional at high work-at-risk (0.65) capped below
  blocking — earns coverage + paired reserve, cannot by itself halt; promotable to blocking
  only after a barrier confirms an irreversible-commit dependency. Replan GC retires only
  with a complete no-dependency proof, else carries forward (keep-not-flush, D28).
- **C7 — UNCOVERED accounting, escrow-side under D25** (`accounting.py`). UNCOVERED is never
  a hit; an uncovered surface over a real injected change is a risk-weighted recall miss
  (loophole closed); coverage-purchased denominator reported. Reads no held-out file,
  computes no held-out denominator in-line.
- **Close — live scheduler + audit + discriminator** (`policy.py`, `audit.py`).
  `EventGatedCadence` makes the scheduler live (sweeps on barrier / pre-completion /
  uncovered-high-risk events; never the withdrawn fixed-k flood); `make_cadence_policy`
  selects it. `dependency_graph_audit` (§19) reports silent misses, terminal completeness,
  coverage-vs-overhead, and runs the discriminator. `two_build_replay_discriminator` (§17)
  confirms two builds with identical dials but a different hidden choice produce identical
  outcomes — with a negative control proving it catches a hidden-knob leak.

---

## Test counts

| checkpoint | file | new tests |
|---|---|---|
| C1 | test_cadence_ledger.py | 12 |
| C2 | test_cadence_harvest.py | 11 |
| C3 | test_cadence_barriers.py | 9 |
| C4 | test_cadence_budget.py | 8 |
| C5 | test_cadence_throttle.py | 10 |
| C6 | test_cadence_provisional.py | 6 |
| C7 | test_cadence_accounting.py | 7 |
| close | test_cadence_discriminator.py | 5 |
| **total new** | | **68** |

**Full suite 355/355 passing, flag OFF and flag ON (`TRIPWIRE_V2=1`)** (287 prior + 68).
Byte-identity **27/27 both flag states** (banked `replay_check.json` restored byte-identical,
sha256 `f5b44b6…`; outputs `runs/archaeology_v2/replay_check_v2_cadence_close*.json`).

## Close verifications

- **$0 LLM:** the cadence package imports no model runner (grep: no `run_claude`,
  `COMPILE_MODEL`, `conductor.sessions`, `anthropic`, `claude`). The entire layer is
  deterministic; the only v2 LLM step remains the pre-existing compile prompt, not invoked
  here.
- **Two-build replay discriminator (§17):** outcomes identical across two builds differing
  only in a hidden choice (input ordering) — the freeze is complete (no hidden knob affects
  the outcome). Negative control confirms the discriminator catches a deliberate
  hidden-knob leak.
- **Dependency-graph audit (§19):** runs escrow-side; reports silent misses (the §14
  residual), asserts one terminal state per assumption, checks coverage-vs-overhead, runs
  the discriminator.
- **Relation under-emission (C3 VERIFY):** the soft-assumption compile format
  (`SoftAssumption`) has no partner-surface field and `compile_pipeline` builds no
  `RELATION_BROKEN` probe — the substrate **under-emits relations** (compile-prompt §9.1).
  Per D29 this is **not patched**; recorded as the measured residual
  `RELATION_UNDER_EMISSION_RESIDUAL` for threats to validity (§21). The cadence layer still
  accounts relations as first-class coverage objects; the gap is purely upstream emission.
- **Scheduler live behind the flag:** `EventGatedCadence` sweeps on events;
  `sentinel_v2/scheduler.py` is byte-identical to HEAD (NoOp baseline intact, live policy
  additive in `cadence/policy.py`); flag-off unchanged (byte-identity 27/27).

## Rule Zero (design-blindness) compliance

- **Category-blind:** no quota/version/resource-specific behavior anywhere in the ledger,
  scheduler, barriers, allocator, throttle, or accounting — every dial is plan geometry or a
  general fault-shape.
- **D28 preserved exactly:** cadence supplies corroboration's re-observations (the live
  header-carrying source) but does not change D28's decision logic — persistence is one
  confirming re-look, the status fast path stays `status >= 400` on well-formed observations,
  grades stay {INTERRUPT, CAUTION}, no raw-count aggregation (the throttle's `raw_count` is
  diagnostic only and decides nothing).
- **D25 quarantine:** the accounting and dependency-graph audit are escrow-side; they read no
  held-out file, compute no held-out denominator in-line, and never feed compiler iteration.
- **No held-out read/run; the one-shot matrix untouched.** Test worlds + synthetic fixtures
  only. Flag-off byte-identical to Phase 1.

## Spend
**$0 LLM.** Only pytest (test worlds) and `analysis/replay_check.py` (world re-instantiation)
ran. Detail: `analysis/dev_run_ledger.md`.

---

## Decisions still waiting (for sessions with the author)
1. **Arm registration** (V2, V2J, S1, S2, S3) in conductor SYSTEMS + the launch manifest,
   then the one-shot matrix (D29 build-order step 8). Not started.
2. **Firing + inventory audit harness** wiring at run scale under the D25 quarantine
   (the `dependency_graph_audit` here is the per-run escrow-side primitive).
3. **Relation extraction** in the compile prompt (§9.1) — the named upstream residual; a
   future deviation if the author chooses to enrich the soft format.
4. **Real-suite probe-failure rates** — the retry budget (1) is principled (seen transport
   rate 0); revisit as a fresh deviation once real transport rates exist (D29 §13).
