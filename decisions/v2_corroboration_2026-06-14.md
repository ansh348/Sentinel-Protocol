# v2 Corroboration (persistence layer) — Build Session Report (2026-06-14)

**Scope:** the probe-primary corroboration layer — the **deterministic** persistence
decision that sits above the typing engine and decides whether an *ambiguous* signal earns
a route to the orchestrator. No LLM on the corroboration path (spend $0). The judgment
layers it depends on (event-gated cadence + the guaranteed pre-completion sweep, the
firing/inventory audit harness, the rebuilt-judge arm, arm registration) remain HARD STOPS
for sessions with the author present.

**Commits:** master, `fe40752` (C0) → `acdf165` (C5); this report + ledger close the session.
Prior state: `2990be7` (D4 compile-prompt close) and `e1651cb` (paper v0.2).

---

## What was built

### C0 — custody (commit fe40752)
Author ruling recorded as deviation **D28** (committed BEFORE any code) and as design §2.2 in
`probe_compiler_design_v0.4.md`; the dead v0.3 "second independent signal" clause is retired
in §2.1. The ruling, frozen pre-data:
- **Corroboration = persistence over time** (not breadth — correlated noise self-corroborates).
- **Threshold = ONE confirming re-look** (least-latency default): two consecutive anomalous
  observations of the same surface.
- **Promote to CAUTION** grade (recommended action routed to the orchestrator), distinct from
  the hard interrupt-and-replan path.
- **Status-coded fast path retained** (no persistence for status signals).
- **No raw-count aggregation** (hard prohibition — the v1 escalation-cap pathology).

### C1 — pure persistence decision (e6428a1)
`sentinel_v2/corroboration.py::decide_persistence(anomaly_flags) -> PROMOTE | TELEMETRY`.
PROMOTE iff two **consecutive** anomalous observations (first sighting + one confirming
re-look). Single observation and healed-by-re-look stay telemetry; never promoted blind. It
is **adjacency, not a count** — short-circuits on the first consecutive pair, tallies nothing.

### C2 — wire into the seam; retire the inert seam (1e6cc83)
The typing engine now types a **single** observation: the inert `Corroboration(confirmed)`
seam and its second-signal→INTERRUPT path are **removed**; shapeless drift returns telemetry,
full stop. The corroboration **layer** (`corroborate_signal` / `corroborate`) routes each
surface from its ordered observation sequence: any engine **INTERRUPT** fires on its own
(clean fault-shapes, hard invariants, the status-coded fast path) at INTERRUPT grade;
shapeless drift that **persists** across a confirming re-look promotes to **CAUTION** grade;
everything else stays telemetry. Tested end-to-end on a real seen-category world (404 fast
path; healthy surface emits nothing).

### C3 — re-observation interface, the cadence seam (546277e)
`ReObservationSource` is the minimal interface corroboration pulls a surface's ordered
observations through; `TraceReObservations` reconstructs them from the trace probe side
channel (pairing `probe_call`/`probe_response` by `probe_seq`). A surface with no confirming
re-look stays telemetry. The **guaranteed pre-completion sweep** that supplies a final re-look
is recorded as a named dependency on the cadence layer
(`PRE_COMPLETION_SWEEP_DEPENDENCY`) and is **NOT built** this session. Cadence scheduling is a
hard stop; corroboration only declares the requirement. Tested incl. reconstruction from a
real world trace.

### C4 — anti-aggregation guard + regression (49a37c2)
Behavioural guards that the v1 escalation-cap pathology cannot recur:
- many transient wobbles on a healthy surface promote **nothing** and **grind nothing**
  (one decision per surface — no per-fire escalation exists);
- output is **persistence-keyed, not count-keyed** (500 anomalies → exactly one caution);
- breadth of unconfirmed wobbles across 50 surfaces promotes **nothing** (no breadth
  interrupt — breadth is the orchestrator's replan decision);
- several confirmed cautions are **separate** invalidations with **no** cross-surface merge;
- the persistence decision is **count-invariant** (no "exceeds N" threshold anywhere).

### C5 — recording, replay, cost (acdf165)
Corroboration decisions are written to the trace as a `corroboration` event (a new v2-gated
event type; banked Phase-1 traces have none). `replay_corroboration` reconstructs the exact
invalidations with **no recomputation and no model call** — byte-identical to what was
recorded, grades and persistence preserved; the reader takes the last set (keep-not-flush
replans append later decisions). The path spends **$0 LLM** by construction (asserted: no
runner imported; recorded `cost_usd` 0.0).

---

## Test counts

| step | file | new tests |
|---|---|---|
| C1 | test_corroboration.py | 8 |
| C2 | test_corroboration.py | 9 |
| C3 | test_corroboration.py | 3 |
| C4 | test_corroboration.py | 5 |
| C5 | test_corroboration.py | 4 |
| **total new** | | **29** |

`test_typing_engine.py` updated (the dead-seam test reframed; still 13 tests).

**Full suite 287/287 passing, flag OFF and flag ON (`TRIPWIRE_V2=1`)** (258 prior + 29 new).
Banked-world byte-identity **27/27 both flag states** (injection-counter parity 27/27; outputs
`runs/archaeology_v2/replay_check_v2_corroboration_close*.json`; banked `replay_check.json`
restored byte-identical, sha256 `f5b44b6…` verified).

## The deviation (D28, verbatim ruling)

> **Persistence over time.** An ambiguous signal — non-status-coded, and not already a clean
> fault-shape or a hard-invariant violation — promotes only if a confirming re-observation of
> the SAME surface still shows the anomaly. A one-shot wobble that has healed by the re-look
> stays telemetry. **Threshold = ONE confirming re-look** (least-latency default), two
> consecutive anomalous observations; a surface with no re-observation stays telemetry,
> backstopped by the cadence pre-completion sweep, never promoted blind. **Promote to CAUTION**
> (a recommended action routed to the orchestrator), distinct from the hard
> interrupt-and-replan path. **Status-coded fast path retained** (no persistence). **No
> raw-count aggregation (hard prohibition)** — each persistence-confirmed surface is a separate
> invalidation; the layer aggregates nothing; breadth is the orchestrator's replan decision.

Full text + rationale: `deviations.md` D28.

## Spend
**$0 LLM.** The corroboration path is deterministic; the only executions were pytest
(test worlds) and `analysis/replay_check.py` (world re-instantiation). Detail:
`analysis/dev_run_ledger.md`.

## Rule Zero (design-blindness) compliance
- **General + category-blind:** the persistence logic names no holdout category and has no
  quota/version/resource-specific behaviour — it reasons over an abstract anomaly-flag
  sequence and the engine's general fault-shapes.
- **Test worlds only:** synthetic anomaly-flag/probe-event fixtures and seen-category test
  worlds (auth/inventory/pricing/docs). No benchmark or held-out cell touched; sealed escrow
  files NEVER read.
- **Flag-gated off:** sentinel_v2 stays behind `TRIPWIRE_V2`; flag-off byte-identical to
  Phase 1 (27/27 regression). The new `corroboration` event type and the typing-engine
  changes are entirely behind the flag.

## HARD STOPS — verified NOT built
- **Event-gated cadence semantics / the pre-completion-sweep MECHANISM** — `scheduler.py`
  still NoOp-only; corroboration only declares the dependency (C3 `PRE_COMPLETION_SWEEP_DEPENDENCY`).
- **Firing + inventory audit harness** — not built (D25 quarantine governs it).
- **Rebuilt-judge arm / arm registration** — `arms.py` untouched (`resolve_arm` still raises).
- **Any held-out or real-benchmark evaluation** — none run.

---

## Decisions still waiting (for sessions with the author)
1. **Event-gated cadence semantics + the guaranteed pre-completion sweep** — when to sweep;
   the work-at-risk weighting; the §3.1/B4 runtime re-observation guarantee that supplies the
   confirming re-look corroboration depends on (C3 named dependency).
2. **Firing + inventory audit harness** — the §7 audits, obeying the D25 held-out-denominator
   quarantine.
3. **Arm registration** — provisional ids V2/V2J and the two-tier/rebuilt-judge arms remain
   unregistered until the author wires them.
4. **Phase-1c probe-failure policy (D26, OWED)** — still owed before any 1c data; the
   deterministic mock has no transport weather, so nothing this session exercises it.
