"""The guaranteed pre-completion sweep (D29 §3.1; D31 C2).

Corroboration (D28) declared this as a NAMED DEPENDENCY but did not build it
(corroboration.py:175 PRE_COMPLETION_SWEEP_DEPENDENCY): a load-bearing surface that
no worker barrier re-observed — most importantly a side-channel-only SHADOW surface
the worker can never touch (the §4 gate shadow) — would otherwise never get its
guaranteed final re-look before run end. This module supplies it.

Pure mechanism, deterministic, $0 dollars (every read is a side-channel probe). The
caller owns scheduling (fire once, after the last worker drains, before aggregate),
budget accounting (the count submetric), and invalidation routing. Anything the
sweep cannot reach over the side channel routes to the UNCOVERED valve (the caller's
`emit`), never silently dropped.
"""
from __future__ import annotations

from typing import Callable, Optional


def pending_sweep_targets(probes, observed, interrupted) -> list:
    """The load-bearing probes that still owe a final re-look: those whose surface
    was NOT re-observed at a barrier this run (FRESH surfaces are not redundantly
    swept) and is not already an open incident (wobble dedup)."""
    return [p for p in probes
            if p.target not in observed and p.target not in interrupted]


def run_pre_completion_sweep(probes, observed, interrupted, *, client,
                             auth_token: Optional[str], baselines, queries,
                             judge: bool, emit: Callable[[str, dict], None]) -> dict:
    """Re-observe every still-owed load-bearing surface over the side channel and run
    corroboration. Unreachable surfaces (a transport failure on the side channel)
    route to the uncovered valve via `emit('uncovered', …)`. Returns the seam:
    invalidations + the swept/reachable/uncovered target lists ($0; count submetric)."""
    from sentinel_v2.arms import run_v2_detection
    from sentinel_v2.probes import ProbeExecutor

    pending = pending_sweep_targets(probes, observed, interrupted)
    if not pending:
        return {"invalidations": [], "swept": [], "reachable": [], "uncovered": []}

    ex = ProbeExecutor(client, auth_token=auth_token)
    reachable, uncovered = [], []
    for p in pending:
        try:
            ex.get(p.target)                 # reachability over the side channel ($0)
            reachable.append(p)
        except Exception as exc:             # the uncovered valve — never silent
            uncovered.append(p.target)
            emit("uncovered", {"where": "pre_completion_sweep", "target": p.target,
                               "reason": "unreachable side-channel surface",
                               "detail": str(exc)[:120]})

    invalidations = []
    if reachable:
        det = run_v2_detection(reachable, client, auth_token=auth_token,
                               baselines=baselines, queries=queries, judge=judge)
        invalidations = det["invalidations"]
    return {"invalidations": invalidations,
            "swept": [p.target for p in pending],
            "reachable": [p.target for p in reachable],
            "uncovered": uncovered}
