"""§4 gate-route compiler glue (B5; probe_compiler_design_v0.4.md §4, §5.1,
author ruling D1).

The §4 gate re-read is a thin no-write wrapper over the world-side shadow route
(world/services/gate_shadow.py), which runs the REAL enforcement predicate.
Ruling D1 makes the non-perturbation check a HARD TRAPDOOR: a §4 route that does
not pass the three-vector non-perturbation gate is DISABLED, and its gate-
enforcement assumption is flagged UNCOVERED (loud) and routed to caution (§5.2) —
never silently treated as covered, never fired under a status surrogate.

Equivalence (§5.1): the probe inherits the WORKER's auth/session context (the
ProbeExecutor carries the supplied worker token and cannot mint one — the channel
refuses issuance). A probe that cannot acquire worker context is DISQUALIFIED to
telemetry, never retried under a privileged key.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from sentinel_v2.probe_spec import (CadenceHint, Comparison, CostClass,
                                    EvidenceClass, FaultShape, Lens, LensOp,
                                    Probe, Provenance)
from sentinel_v2.probes import ProbeExecutor
from sentinel_v2.typing_engine import (Evaluation, Invariant, Verdict,
                                       evaluate_hard_invariant)

# The §4 shadow routes (registered world-side only on probe-channel worlds).
REPO_GATE_SHADOW = "/repo/gate_status"
DOCS_GATE_SHADOW = "/docs/gate_status"
ENFORCING_POINTER = "/enforcing"

@dataclass(frozen=True)
class NonPerturbationReport:
    counter_ok: bool        # vector 1: the injection-clock counter
    token_stream_ok: bool   # vector 2: the token stream
    sentinel_ok: bool       # vector 3: the validated_docs sentinel

    @property
    def ok(self) -> bool:
        return self.counter_ok and self.token_stream_ok and self.sentinel_ok

    def failed_vectors(self) -> tuple:
        return tuple(name for name, ok in (("counter", self.counter_ok),
                                           ("token_stream", self.token_stream_ok),
                                           ("sentinel", self.sentinel_ok)) if not ok)


def check_non_perturbation(world, probe_action: Callable[[], object], *,
                           auth_token: Optional[str] = None) -> NonPerturbationReport:
    """Run `probe_action` (the §4 side-channel read) and verify the three measured
    perturbation vectors (archaeology_v2 G7) are untouched. A perturbing action
    trips the trapdoor (ruling D1).

    D31: ALL THREE vectors are read counter-neutrally from the middleware-excluded
    /admin/state around the probe action, so the safety check itself advances NO
    injection-counting channel (the fence: the compile-time §4 read must not route
    through the worker/injection-counting channel). The §4 read routes over the
    read-only probe channel and so cannot perturb by construction; the admin reads
    confirm it. The sentinel vector (vector 3) is validated_docs: a §4 read that
    admitted anything to validated_docs would move it. (This replaces the prior
    canary POST, which was a COUNTING write — it would have shifted injection
    timing if run inside a comparative cell.)"""
    client = world.client

    def admin():
        return client.get("/admin/state").json()

    before = admin()
    probe_action()
    after = admin()
    counter_ok = after["counter"] == before["counter"]
    token_stream_ok = after["active_tokens"] == before["active_tokens"]
    sentinel_ok = after.get("validated_docs") == before.get("validated_docs")

    return NonPerturbationReport(counter_ok, token_stream_ok, sentinel_ok)


@dataclass(frozen=True)
class GateProbeResult:
    enabled: bool
    uncovered: bool
    reason: str
    probe: Optional[Probe] = None
    report: Optional[NonPerturbationReport] = None


def compile_gate_probe(world, *, shadow_path: str, provenance: Provenance,
                       auth_token: Optional[str],
                       probe_action: Optional[Callable[[], object]] = None
                       ) -> GateProbeResult:
    """Build the §4 gate probe behind the non-perturbation trapdoor (ruling D1).
    Pass-through ⇒ probe armed; trip ⇒ route DISABLED, assumption UNCOVERED →
    caution. `probe_action` defaults to the real side-channel read of the shadow."""
    action = probe_action or (
        lambda: ProbeExecutor(world.client, auth_token=auth_token).get(shadow_path))
    report = check_non_perturbation(world, action, auth_token=auth_token)
    if not report.ok:
        return GateProbeResult(
            enabled=False, uncovered=True, report=report,
            reason=f"§4 route {shadow_path} FAILED the non-perturbation trapdoor "
                   f"({', '.join(report.failed_vectors())}); route DISABLED, gate-"
                   f"enforcement assumption flagged UNCOVERED and routed to caution "
                   f"(§5.2) — never a status surrogate (ruling D1)")
    probe = Probe(
        method="GET", target=shadow_path,
        lens=Lens(op=LensOp.GATE_SHADOW, pointer=ENFORCING_POINTER),
        comparison=Comparison.HARD_INVARIANT, fault_shape=FaultShape.VALUE_CHANGED,
        evidence_class=EvidenceClass.STATUS_CODED, cost_class=CostClass.LIGHT,
        cadence_hint=CadenceHint.PRE_COMPLETION, provenance=provenance)
    return GateProbeResult(
        enabled=True, uncovered=False, probe=probe, report=report,
        reason=f"§4 route {shadow_path} passed the non-perturbation trapdoor; "
               "probe armed (no-write wrapper over the real enforcement predicate)")


def evaluate_gate_probe(probe: Probe, executor: ProbeExecutor, *,
                        requires_auth: bool) -> Evaluation:
    """Execute the §4 probe over the side channel and evaluate it as a hard
    invariant (enforcing must be True; fires on its own). Equivalence (§5.1): a
    probe lacking worker auth context (401 on an authed gate) is DISQUALIFIED to
    telemetry — never retried under a privileged key."""
    result = executor.get(probe.target)
    if requires_auth and result.status == 401:
        return Evaluation(
            Verdict.DISQUALIFIED, "hard_invariant",
            reason="§4 probe lacks worker auth/session context (401); DISQUALIFIED "
                   "to telemetry — never fired under a privileged key (§5.1)")
    return evaluate_hard_invariant(probe, result, Invariant(equals=True))
