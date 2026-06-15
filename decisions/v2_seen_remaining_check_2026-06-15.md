# Remaining-category seen check — TOOL_CONTRACT misses; PERMISSION_AUTH detects

**Date:** 2026-06-15  **Status:** DIAGNOSIS ONLY — no fix applied (brought back per brief).
**Scope:** SEEN cells only; NO held-out/escrow read; matrix NOT run; no push.
**Suite:** 373/373 flag OFF and ON. **Byte-identity:** 27/27 both (banked `f5b44b6…` restored).
**Dev-run:** ~$1.82 seen-only (3 real cells $1.636 + b1 diag compile $0.188; controlled world check $0).

## Why this check

D30 validated the two *content-shaped* seen categories (schema_drift, doc_contradiction)
and the *status* path (endpoint_404) through the real V2Conductor. The two remaining
seen categories ride **different** probe mechanisms and were unexercised end-to-end:

- **PERMISSION_AUTH = token_expiry** → the **status fast path** (401 on a trusted surface).
- **TOOL_CONTRACT = gate_skip_trap** → the **§4 gate-shadow / premise re-read** probe
  (`GET /repo/gate_status`, `LensOp.GATE_SHADOW`, hard invariant `enforcing == True`) —
  the "validation machinery silently stopped checking while still admitting outputs" case.

D30 passing drift/contradiction does **not** establish the gate path works: it is a
distinct mechanism (a premise re-read, not a baseline content diff).

## Cells (frozen seen values, rev-4 1b world)

| cell | task+injection | n_inject | result |
|---|---|---|---|
| gate  | b1+gate_skip_trap | 4  | **MISS** — detected=False, 0 int, gate_probe_armed=False, $0.41 |
| clean | b1 (none)         | —  | **FALSE POSITIVE** — detected=True, FIR=1.0, value_changed on settings.yaml, $0.48 |
| token | a1+token_expiry   | 12 | **DETECT** — status fast path, 2 int / 2 replan, FIR=0.0, ttd 11, $0.75 |

## Finding 1 — PERMISSION_AUTH (token_expiry) DETECTS, with a nuance

Detected via the status fast path (401 on `/inventory/items`, `/pricing/quote/GAD-001`,
`/auth/validate`, `/shipping/destinations`). **But 2 interrupts / 2 replans, not
endpoint_404's 1/1.** token_expiry is a *global* auth lock — it 401s **every** authed
surface, so each distinct affected surface trips the fast path once (per-surface wobble
dedup coalesces the rest: 46 `suppressed_refire`), bounded by `max_replans=2`. The brief's
"one interrupt / one replan" expectation holds only for single-surface faults (a removed
route); a global fault legitimately produces one interrupt per affected surface, bounded.
FIR 0.0, cost sane, $0 detection-machinery dollar impact. **Robust.**

## Finding 2 — TOOL_CONTRACT (gate_skip_trap) MISSES — three stacked wiring gaps

The §4 premise probe is the right mechanism, but it **never functions on the real loop**.
All three gaps are *implementation* gaps in the D30 mold (the §4 seam is built and
unit-tested in `sentinel_v2/gate_route.py`); **none is an architectural limit**.

**(a) NOT ARMED.** `V2Conductor.compile_and_arm()` (`conductor/run_v2_loop.py:68`) calls
`compile_pipeline(soft, world_rev=...)` **without a `world`**. In `compile_probes.py:264-282`
an enforcement-gate surface needs a live world to run the §4 non-perturbation trapdoor;
with `world is None` every gate assumption is routed to **UNCOVERED → caution (D1)** and
no probe is armed. Controlled compile on the b1 soft set (32 assumptions, 5 naming
`/repo/validate`):

```
world=None  (the real V2Conductor call): 27 probes,  0  /repo/gate_status probes
world=live  (what the trapdoor needs):   32 probes,  5  /repo/gate_status probes
            gate probe: target=/repo/gate_status lens.op=GATE_SHADOW
                        comparison=HARD_INVARIANT predicate=enforcing==True
```

Confirmed live: the real b1 gate run armed only content probes; gate_status absent.

**(b) NOT SWEPT.** Even if armed, the §4 probe is `PRE_COMPLETION` cadence on a *shadow*
surface the worker never touches. The guaranteed pre-completion sweep is **declared but
unbuilt** (`corroboration.py:175 PRE_COMPLETION_SWEEP_DEPENDENCY`), and `_v2_worker_barrier`
filters probes to worker-touched surfaces (`_worker_surfaces`) — so a shadow-surface probe
would not fire at a barrier. `run()` goes compile → dispatch → drain → aggregate with no
pre-completion sweep in between.

**(c) NOT EVALUATED.** Even if armed and observed, `run_v2_detection` / `_signal_for`
(`arms.py`) builds an **empty `Invariant()`** for a `HARD_INVARIANT` + `VALUE_CHANGED`
probe (the `else` branch) instead of the `enforcing == True` invariant that
`evaluate_gate_probe` uses → `evaluate_hard_invariant` returns CLEAN. The generic
detection seam does not route GATE_SHADOW probes through the gate evaluator.

**The signal is present and detectable in principle** ($0 controlled world check):

```
CLEAN  (pre-trap): POST /repo/validate -> passed, checks_run=3
                   GET  /repo/gate_status -> enforcing=True,  checks_run=3
TRAPPED:           POST /repo/validate -> passed, checks_run=0   (silently stopped checking)
                   GET  /repo/gate_status -> enforcing=False, checks_run=0   (shadow reveals it)
```

Confound (does not change the conclusion): the b1 gate run's worker looped on
settings.yaml and failed before validating (rev-4 single-worker flakiness, per the b1
requalification record). The structural miss (gate unarmed) and the $0 controlled check
are independent of worker success.

## Finding 3 — b1+clean FALSE POSITIVE (same root-cause family)

The matched clean cell is **not quiet**: FIR 1.0, a `value_changed` interrupt on
`config/settings.yaml`. b1 is a *migration* task — worker w1 legitimately PUTs settings.yaml
(rename `pricing.source_field` → `pricing.price_source`, the task's whole point). The
arm-time baseline captured the pre-migration file at counter 1; the worker's own write at
counter 4 differs → false drift at counter 15. `compile_and_arm` **also drops
`planned_write_set`**, so the planned write target is actively probed instead of being left
PASSIVE (the attachment policy already supports `planned_write_set`). This would inflate FIR
on every b1 clean cell in the matrix.

## Unified root cause

`V2Conductor.compile_and_arm`'s `compile_pipeline` call is **under-parameterized** relative
to the standalone pipeline — it drops `world` (→ gate miss), `auth_token` (→ docs/authed
gate), and `planned_write_set` (→ clean false positives). The mechanisms exist and are
unit-tested; the run loop never feeds them.

## Proposed fix (general, category-blind — NOT applied; bring back first)

1. **Arm:** pass the run's live world + the v2 worker token + the plan's write-set to
   `compile_pipeline` in `compile_and_arm` (and replan recompiles). §4 gate probes then arm
   for **any** enforcement gate (repo or docs), driven by the soft assumption naming a gate,
   not by category; write targets go PASSIVE.
2. **Sweep:** build the declared guaranteed pre-completion sweep — before `aggregate`, fire
   every `PRE_COMPLETION` probe (gate probes included) on the same world/token through
   corroboration. Category-blind: it re-observes every load-bearing surface.
3. **Evaluate:** route `GATE_SHADOW`-lens probes through `evaluate_gate_probe`'s
   `enforcing == True` invariant (or have `_signal_for` set `Invariant(equals=True)` for a
   GATE_SHADOW lens). General: any gate-enforcement premise probe.

No tuning toward gate_skip_trap; every change generalizes to any enforcement gate and any
write-heavy task. **Stop here per the brief: bring this back before any further step.**

## Fences honored

Category-blind, injection-blind; no held-out/escrow read (escrow mtimes unchanged); nothing
run against the held-out; matrix NOT run; seen cells only; byte-identity 27/27 both flag
states (banked restored); $0 detection-machinery dollar impact (count submetric only);
D28/D29/D30 preserved; dev-run ledgered (+2 rows); no production code changed (only
`analysis/v2_seen_remaining_smoke.py` added, not imported by suite/world); no push.
