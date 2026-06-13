# v2 Probe-Compiler Substrate — Build Session Report (2026-06-14)

**Scope:** the deterministic probe-compiler SUBSTRATE (design-of-record
`probe_compiler_design_v0.4.md`, in repo). The LLM-driven and judgment layers are
HARD STOPS reserved for sessions with the author present (see §"Still waiting").

**Branch/commits:** master, 31ebab8 (Step 0) → 99f5b37 (B7); this report + ledger
close the session. Prior state: d370376 (v2 night close N1–N5).

---

## What was built

### Step 0 — design lock (commit 31ebab8)
- `probe_compiler_design_v0.4.md` placed IN the repo (the v0.3 draft lived at the
  project root, untracked). Folds the v0.4 deltas: **Break-A** (§2.1 typing gates
  the drift path ONLY; hard invariants fire on their own), **Break-E**
  (stationary = no concurrent worker writes per the *global* write-set),
  **Break-G** (replan cost booked on the run it occurs on), the §3.1 attachment
  predicate rewrite (truth-not-carried-by-ordinary-traffic), the §0 honesty fix
  (typed-drift trades BOUNDED recall, not "nothing"), and the new ORDER/RELATION/
  FIELD-ADDED shapes.
- Records **author rulings D1** (§4 gate route = no-write wrapper + non-perturbation
  trapdoor) and **D2** (replan keep-not-flush) as design-of-record.
- Logs **GATE-Δ deviations D25** (probe-inventory audit held-out-denominator
  quarantine) and **D26** (owed Phase-1c probe-failure policy) in `deviations.md`.

### B1 — order-sensitive + relational/join primitives (04369c8)
`sentinel_v2/probes.py`: `ordered_subarray`/`ordered_digest` (order-sensitive;
catch a reorder the value-blind sorted-set fingerprint misses) and
`project_keys`/`relation_holds` (cross-surface referential coverage / set equality
= the RELATION_BROKEN lens, no single-surface baseline). Accept ProbeResult or raw
body. **Order-blindness repro** + cross-surface broken-relation tested.

### B2 — probe spec + fault-shape vocabulary (7f84988)
`sentinel_v2/probe_spec.py`: the `Probe` dataclass
`{method,target,lens,comparison,fault_shape,evidence_class,cost_class,cadence_hint,
provenance}` with structural validators; `FaultShape` enum = **6 general shapes**
(FIELD-ADDED folded into SCHEMA_SHAPE — see open reconciliation below).
`subject_to_typing()` encodes Break-A. Evidence trust priors + cadence_hint are
carried as inert DATA for the future corroboration/cadence layers.

### B3 — comparison + typing engine (4030469)
`sentinel_v2/typing_engine.py` (pure, synthetic fixtures): HARD_INVARIANT fires on
the current observation alone (gate-off-from-start interrupts with no baseline);
PROOF_BASELINE enforces the five obligations (any failure ⇒ DISQUALIFIED — a dirty
baseline certifies the mutated world as normal); §2.1 typing lets typed drift
interrupt and demotes shapeless content-hash drift to TELEMETRY unless corroborated.
Corroboration is an honored SEAM (wiring is a hard stop).

### B4 — attachment-policy evaluator (eb2ef53)
`sentinel_v2/attachment.py` (pure): gate order read-and-trust (global write-set, A4)
→ provenance (§3.3 ⇒ TELEMETRY_ONLY) → §3.1 truth-not-carried predicate (⇒ PASSIVE)
→ ATTACH with §1.1 lens selection. A self-reobserving-but-non-self-validating
surface (the enforcing gate, §3.2) earns a GATE_SHADOW probe.

### B5 — §4 gate route + equivalence + trapdoor (3d26fec)
World-side: each gate's enforcement factored into a shared pure predicate (POST gate
and shadow can never disagree); read-only `GET /repo/gate_status` &
`/docs/gate_status` run the REAL predicate no-write (repo: behavioral did-checks-run;
docs: real predicate vs a deliberately-invalid canary) — never a `gate_enabled`
flag. Registered ONLY on probe-channel worlds ⇒ byte-identical when off.
Compiler-side `sentinel_v2/gate_route.py`: the three-vector non-perturbation
**trapdoor** (ruling D1) — pass ⇒ probe armed; trip ⇒ route DISABLED, assumption
UNCOVERED → caution (§5.2). **Equivalence** (§5.1): the probe inherits the worker
token; a probe lacking worker context is DISQUALIFIED to telemetry, never under a
privileged key.

### B6 — replan keep-not-flush (94459d4)
`sentinel_v2/replan.py` (pure, ruling D2): keep-not-flush + recompile-add +
N2-prune-dead (GATE_SHADOW probes exempt) + coverage/liveness check. The
**death specimen** is averted by keep-not-flush and DETECTED when a live assumption
is left uncovered. The **in-flight-dropped** probe is kept and LOGGED — the named
residual is observable, not silent. `instrument_fire` marks every post-replan fire.

### B7 — rev-aware surface appendix (99f5b37)
`sentinel_v2/surface_appendix.py` (deferred D6): rev 1 delegates to
`world.surface.derive_surface` (byte-identical); rev ≥ 2 derives mechanically from
the rev-N OpenAPI + fixtures (mirrors `path_samples_for_rev`). probe_channel off in
every derivation ⇒ the §4 routes never leak into the appendix.

---

## Test counts

| step | test file | new tests |
|---|---|---|
| baseline (N1–N5) | — | 160 |
| B1 | test_probe_order_relation.py | 10 |
| B2 | test_probe_spec.py | 13 |
| B3 | test_typing_engine.py | 13 |
| B4 | test_attachment.py | 9 |
| B5 | test_gate_route.py | 8 |
| B6 | test_replan.py | 7 |
| B7 | test_surface_appendix.py | 6 |
| **total** | | **226** |

**Full suite 226/226 passing, flag OFF and flag ON (`TRIPWIRE_V2=1`).**

## Byte-identity regression (banked-world)
`analysis/replay_check.py` over the 27 injected S5 cells, **27/27 byte-identical
both flag states** (injection-counter parity 27/27). The B5 repo/docs gate refactor
and the gate_shadow route are probe_channel-gated, so banked configs (probe_channel
off) are byte-unchanged. Outputs: `runs/archaeology_v2/replay_check_v2_close_regression.json`
and `_flag_on_regression.json`; the banked `replay_check.json` was backed up and
restored byte-identical.

## Spend
**$0.00 LLM** this session. The substrate is fully deterministic; no LLM compile
prompt was built or run, no conductor/claude invocations. Well under the $5 cap.

## Rule Zero (design-blindness) compliance
- **NOT read:** `benchmark/holdouts/*`, `decisions/holdout_*`, `decisions/matrix_*`,
  `benchmark/matrix_draw_spec.md`, `decisions/b1_requalification_*`,
  `analysis/holdout_*`, `analysis/matrix_escrow_draw.py`,
  `analysis/requalification_b1_rev4.py`, and the sealed escrow data files.
- `world/state.py` and `world/server.py` were read (Phase-1/N-series world
  infrastructure required to build generic primitives and the §4 route). Their
  rev-2 sections carry comments referencing the holdout specs; those mechanics were
  used only as a GENERIC world surface — **no quota/version/resource-specific
  category, template, probe type, or heuristic appears anywhere in the build.** The
  6 fault-shapes, all lenses, the attachment kinds, and the §4 gate predicate are
  ontology-general; the §4 route works on the Phase-1 archetype gates
  (`/repo/validate`, `/docs/validate`), not on any holdout category.

---

## HARD STOPS — verified NOT built
- **D4 LLM compile prompt** — absent (`prompts/` has no probe/compile-v2 file).
- **Probe-primary corroboration wiring** — only an inert `Corroboration` SEAM the
  typing engine honors; nothing computes corroboration.
- **Event-gated cadence semantics** — `scheduler.py` still NoOp-only;
  `cadence_hint` is carried as data, consumed by nothing.
- **Firing + inventory audit harness** — not built; D25 logs only the pre-committed
  denominator-quarantine discipline.
- **Rebuilt-judge arm** — `arms.py` untouched (`resolve_arm` still raises).

---

## Judgment decisions still waiting (for sessions with the author)
1. **Compile prompt (D4)** — the LLM prompt that emits `Probe`s from plan+assumptions
   +surface; encodes §§1–6 and nothing more. Written last.
2. **Probe-primary corroboration** — the policy/wiring behind the §2.1 "OR
   corroborated" seam (which independent probe confirms shapeless drift, and how).
3. **Event-gated cadence semantics** — when to sweep; the work-at-risk weighting and
   the guaranteed pre-completion sweep that B4/§3.1 delegate runtime re-observation to.
4. **Firing + inventory audit harness** — the §7 audits; must obey the D25 held-out-
   denominator quarantine (escrow-side, aggregate-only, never fed back).
5. **Phase-1c probe-failure policy (D26, OWED)** — retry budget, persistent
   threshold, 429/5xx/timeout-vs-world classification, caution-vs-economics — to be
   frozen before any 1c data.
6. **Fault-shape count reconciliation (6 vs 7)** — this build implements 6 enum
   members with FIELD-ADDED folded into SCHEMA_SHAPE; if the author prefers a
   distinct FIELD_ADDED member it is a one-line addition. Recorded in the design doc
   top note and §"Open residuals".
7. **Arm wiring** — provisional ids V2/V2J and the two-tier/rebuilt-judge arms remain
   unregistered until the author wires them.
