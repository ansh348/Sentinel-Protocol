"""Probe scheduler INTERFACE with cadence as a pluggable policy.

Night-shift boundary, stated in ink: the event-gated, work-at-risk-weighted
cadence with a guaranteed pre-completion sweep (v6.1 §11.9 amendment #1) is
a JUDGMENT layer and is deliberately NOT designed here. This module fixes
only the seam it will plug into: a CadencePolicy decides `due`, a
ProbeScheduler consults it, and the only policy that exists tonight is the
no-op placeholder, which never sweeps. The naive fixed-k cadence is
withdrawn by the v6.1 amendment (G15: up to 2,322 probe calls vs 107 worker
calls; cadence starvation on short runs) and is intentionally not provided
even as a convenience.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Mapping, Optional


class CadencePolicy(ABC):
    """Decides whether a probe sweep is due, given a context snapshot the
    scheduler assembles (counters, events, plan state — semantics to be
    fixed with the author). Implementations must be deterministic."""

    @abstractmethod
    def due(self, context: Mapping[str, Any]) -> bool:
        ...


class NoOpCadence(CadencePolicy):
    """The placeholder policy: never sweeps. Exists so the scheduler seam
    is testable tonight without smuggling in cadence semantics."""

    def due(self, context: Mapping[str, Any]) -> bool:
        return False


class ProbeScheduler:
    """Consults the policy; runs the sweep callable only when due. Carries
    no cadence state of its own — whatever state a real policy needs lives
    in the policy, where the morning design session can see it whole."""

    def __init__(self, policy: CadencePolicy) -> None:
        self.policy = policy

    def maybe_sweep(self, context: Mapping[str, Any],
                    sweep: Callable[[], Any]) -> Optional[Any]:
        if not self.policy.due(context):
            return None
        return sweep()
