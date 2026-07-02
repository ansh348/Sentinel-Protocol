# A7b — Phase 2 note (offline build; arm-(b) target-surface selection)

Ratified A7b pre-reg: `A7b_family_close_PREREG.md` (commit `3a36491d`). This note logs the
frozen-rule surface selection, its evidence, and the offline build validation. No metered spend.

## Arm-(b) target surface — pinned by the frozen selection rule (non-discretionary)

Rule (from the pre-reg): *the most-frequently-armed load-bearing surface in the A7 armed-probe
evidence for the task* (a1). Computed over the 3 A7 a1/V2 cells' `tripwire_set` armed probes:

```
armed-probe frequency (a1 V2, across the 3 A7 cells; a7_fir_evidence-style read):
   36 probes | in 3 cells | /pricing/quote/{sku}     <-- SELECTED
   18 probes | in 3 cells | /shipping/rates/{sku}
    6 probes | in 1 cells | /inventory/items/{sku}
    3 probes | in 3 cells | /auth/token
    3 probes | in 3 cells | /auth/validate
    3 probes | in 3 cells | /inventory/items
    2 probes | in 2 cells | /shipping/destinations
```

**Selected: `/pricing/quote/{sku}`** — 36 armed probes (12/cell in all 3 cells), a clear winner
(2x the runner-up). Arm (b) places the transient-500 on this surface (glob `/pricing/quote/*`).
Deterministic, evidence-logged, no discretionary choice.

## Refinement to the A7 interpretation (flagged; A7 report not rewritten)

The evidence shows **`/auth/token` WAS armed in A7** (3 probes, all 3 cells). So the A7 report's
phrasing — "the 500 landed on `/auth/token`, a surface V2 does not compile a probe for" — is
**imprecise**: V2 *does* compile a probe there, yet the A7 transient-500 on `/auth/token` still did
not fire a V2 interrupt. This sharpens arm (b): the question is not "monitored vs unmonitored
surface" but whether V2's detection **sees worker-path noise at all** (its probes read the
perturbation-isolated side channel; the transient is injected on the worker path). Placing the 500
on the *most-armed* surface (`/pricing/quote`) is the decisive test. This refinement is recorded
here for the A7b closing section; the committed A7 report's prose is left as-is (post-hoc record).

## Build — `transient_500` target-surface param (gated, default None)

- `world/state.py`: `WorldState.noise_500_target` (default None); set from
  `noise_profile.params["target_surface"]` for a transient_500 run.
- `world/noise.py`: `trip_transient_500(state, n, path)` — when a target glob is set, fires on the
  first worker call whose path matches it (heals on retry); else the A7 first-call behavior.
- `world/server.py`: passes `path` to `trip_transient_500`.
- **Default None ⇒ every A7 config + every non-A7 config is byte-identical** (the param is only
  read on a transient_500 run that sets it).

## Offline validation

- **A7 + A7b unit tests: 11/11** (`tests/test_a7_noise.py`), incl. the new target-surface test
  (500 lands on `/pricing/quote/*`, not the token call; heals; only one 500).
- **Flag-off byte-identity: 3/3** on banked clean traces (a1/b1/c1), 0 mismatches — the build is
  inert with the flag off.
- Full suite: green (regression check with the `trip_transient_500` signature change).

## Run plan (Phase 3, metered, $8 cap)

Arm (a) first: V2 noiseless, a1/b1/c1 at seeds 4/5/6, 7/8/9, 10/11/12 (9 cells). Then arm (b): V2,
a1 at seeds 16-19, transient-500 on `/pricing/quote/*` (4 cells). Foreground chunks, resumable
ledger `runs/a7b/a7b_results.jsonl`, `v2_interrupts` banked per cell. `analysis/a7b_runner.py`.
