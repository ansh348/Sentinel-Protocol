# v2 Run-Loop Fidelity — Session Report (2026-06-14)

**Scope:** validate the REAL v2 matrix detection path on SEEN cells before the one-shot —
cadence firing probes at worker barriers mid-run, harvesting worker reads through the §8
equivalence gate, with same world-instance and token discipline (NOT the arm-smoke
direct-harvest shortcut). Dev-run, seen-only; the matrix is NOT run. Prior state: arm
registration close.

---

## What was built

- **`conductor/run_one.py`** — minimal, backward-compatible refactor: `Conductor.__init__`
  accepts an optional `system_config` (so a v2 subclass plugs in without polluting
  `SYSTEMS`) and a `probe_channel` flag (off for baselines → byte-identical world config).
  `system_id` stays the baseline path. No behaviour change for S1–S5.
- **`conductor/run_v2_loop.py`** — `V2Conductor`, the REAL v2 run loop. Reuses the
  conductor's world / plan / worker / aggregate machinery; replaces v1 detection with: the
  category-blind v2 compile (probes); a **worker barrier** at each worker completion that
  (a) harvests the worker's reads from the world trace through the §8 gate for clean
  baselines (capturing the worker's query for §8 same-projection), (b) fires probes for
  that worker's surfaces on the SAME world instance with the re-used worker token, (c) runs
  corroboration; a corroborated INTERRUPT routes to a real `replan` (recompile + redispatch,
  reusing the v1 pause/replan so the trace stays M6-readable). Per-surface **D29 wobble
  dedup** (one open incident per surface; re-detections logged as `suppressed_refire`).
- **`sentinel_v2/arms.py`** — `dispatch(arm_id, …)` routes baselines through `run_one` and
  v2 arms through `V2Conductor`, collecting a uniform `ArmResult` (now with `replans`).
- Tests + the live runner (`analysis/v2_runloop_smoke.py`).

## Per-seen-cell result via the REAL path

| arm | seen cell | detected | interrupts | replans | FIR | ttd | cost | source |
|---|---|---|---|---|---|---|---|---|
| V2 | a1 + endpoint_404 | **True** | 1 | 1 | **0.0** | 9 | ~$0.39–0.53 | v2_runloop |
| V2 | a1 (clean) | **False** | **0** | 0 | — | — | ~$0.30–0.37 | v2_runloop |
| V2 | a1 + schema_drift | False (see finding) | 0 | 0 | — | — | ~$0.28 | v2_runloop |
| S2 | a1 + endpoint_404 | True | 2 | — | 0.5 | 20 | ~$0.34 | conductor |

**The directive's assertions, on the real path:** V2 **detects** the injected status-coded
cell (endpoint_404) and is **quiet (0 interrupts)** on the clean world; **FIR is sane** (0.0
injected / none clean) with **no spurious 401/405 false-positive blowups** after the fixes;
**cost is in a sane range** (~$0.3–0.5/cell); the **same world-instance + token discipline
holds** (probes fire on the run's world subprocess re-using the trace's bearer token — a
cross-instance token cannot manufacture a 401). The baseline **dispatches correctly through
the runner**.

**Sustained-violation behavior (KG3-relevant):** a sustained 404 does **NOT** translate into
multiple replans/cost. The D29 per-surface dedup coalesces re-detections of the same surface
into one open incident → **one interrupt, one replan**; later barriers log `suppressed_refire`,
not new interrupts. (Before the dedup fix, a sustained 404 flooded to 19 interrupts — the v1
escalation pathology in a new form — now closed.)

## Integration issues found

1. **Status fast path fired on a request-side 405 (FIXED).** A probe GET to the POST-only
   `/auth/token` returns **405**; the status fast path treated it as a surface anomaly →
   false-positive flood, and would have broken the clean-quiet check. Fixed by excluding
   request-malformation codes `{400, 405, 422}` per §8 (a 4xx that belongs to the request,
   not the surface). After the fix: clean is quiet, and the real 404/401 still fast-path.
2. **Sustained-violation flood (FIXED).** The barrier re-detected the same surface every
   wave. Fixed with the D29 wobble dedup (one open per surface) → bounded, KG3-safe.
3. **Drift-path §8 projection bug (FIXED).** A probe GET that omitted the worker's `?dest=`
   query observed a different projection than the worker and false-positived on
   `/shipping/rates/...` (NOT the injected surface; M6 correctly scored it false). Fixed by
   replaying the worker's observed query so the probe sees the same view (§8 same-projection).

## Residual flagged (matrix-fire item, not patched)

After the §8 query fix, **schema_drift detected nothing** — the real `/pricing` drift was
**missed** because no clean pre-injection baseline was harvested for the *exact grounded
SKU* (the worker's read order didn't cover it clean before the injection counter). This is a
**parity difference vs the arm smoke**: the smoke's direct-harvest shortcut fabricated a clean
baseline and "detected" schema_drift, whereas the real path depends on the worker actually
reading the grounded surface clean in time. **Status-coded faults (endpoint_404, token_expiry)
are robust end-to-end (no baseline needed); the DRIFT path's detection is conditioned on a
clean pre-injection baseline for the grounded surface.** Options for matrix-fire (author):
ground drift probes to the surface the worker reads first, or fire an early baseline-capture
sweep at admission. Recorded, not patched (it edges into compile/grounding).

## Detection parity with the smoke
- **endpoint_404:** real path detects (status fast path) — **matches** the smoke. ✓
- **schema_drift:** smoke detected (via the shortcut's fabricated baseline); the real path
  missed it — a **parity difference that the shortcut had masked**, which is the whole point
  of validating the real path. Reported above.

## Close verifications
- **Suite:** **371/371 passing, flag OFF and ON** (364 prior + 7 new run-loop helper tests:
  §8 harvest-from-trace, token re-use, per-worker surfaces).
- **Byte-identity:** **27/27 both flag states**; banked `replay_check.json` restored
  byte-identical (sha256 `f5b44b6…`). The conductor refactor is backward-compatible
  (`probe_channel` defaults off → baseline world config byte-unchanged).
- **Dev-run spend ≈ $4.0** (several real multi-worker runs during debugging + validation;
  bounded, seen-only). Logged in `analysis/dev_run_ledger.md`.
- **No held-out file read or loaded; the matrix was NOT run.** SEEN cells only (a1 +
  endpoint_404 / schema_drift, both in the seen corpus).

## Rule Zero
Category-blind throughout (the fixes are general HTTP/§8 rules — request-malformation codes,
query projection, per-surface dedup — none category-specific). No escrow/held-out file read;
nothing run against the held-out set; the one-shot not spent. Flag-off byte-identical.

---

## Decisions still waiting (for the author)
1. **Drift-path baseline grounding** (the residual above) — ground drift probes to the
   worker's first-read surface, or an early baseline-capture sweep. Needed for drift-fault
   recall in the matrix; status-coded recall is already robust.
2. **The one-shot matrix** — 215 cells × 5 arms, held-out from escrow at fire, gates once.
   The real V2 path is now exercised end-to-end on seen cells; this is the remaining step.
3. **Rebuilt-judge tier (V2J)** — still the exploratory pass-through seam.
