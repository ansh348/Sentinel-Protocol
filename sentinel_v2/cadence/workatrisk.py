"""Work-at-risk (frozen dial 1; decisions/cadence_semantics.md §3, D29).

Forward-looking, computed from the plan DAG, CATEGORY-BLIND — every factor is plan
geometry, never a failure category. Deterministic, $0 LLM.

    work_at_risk = remaining_dependent_work        (normalized fraction in (0,1])
                 × irreversibility                 (1.0 commit/side-effect, else 0.3)
                 × P(no_later_natural_observation) (1.0 single-visit, else 0.2)
                 × actionability                   (1.0 replan can still avoid, else 0.0)

The first factor is NORMALIZED (D29 fold): downstream-dependent remaining steps and
branches divided by total remaining steps and branches at evaluation time. As a raw
count it crossed the 0.8 blocking threshold on short plans; normalized, the product
lands in [0,1] and the 0.5 / 0.8 thresholds are meaningful. The ordering of surfaces
is unchanged: single-visit and commit-bearing surfaces rise; naturally re-observed
(re-touched) reads sink.
"""
from __future__ import annotations

from dataclasses import dataclass

from sentinel_v2.probe_spec import FaultShape

# Frozen thresholds (D29 §17). Strict ">" per the doc ("above 0.5", "above 0.8").
HIGH_RISK_THRESHOLD = 0.5      # paired-observation reserve (§2, §12)
BLOCKING_THRESHOLD = 0.8       # an uncovered miss routes to UNCOVERED_BLOCKING (§4)

# The two frozen multiplicative constants (D29 §3, §17).
IRREVERSIBILITY_COMMIT = 1.0
IRREVERSIBILITY_NONE = 0.3
P_NO_LATER_SINGLE_VISIT = 1.0
P_NO_LATER_RETOUCHED = 0.2


@dataclass(frozen=True)
class PlanAssumption:
    """The plan-DAG facts work-at-risk needs — all category-blind geometry.

    `downstream_steps` / `total_remaining_steps` are counted over the not-yet-executed
    plan steps and branches; sunk (already executed) work is excluded from both, and
    is reported as waste elsewhere, never here."""
    assumption_id: str
    surface_id: str
    required_shape: FaultShape
    downstream_steps: int          # downstream-dependent remaining steps/branches
    total_remaining_steps: int     # total remaining steps/branches at evaluation time
    downstream_commits: bool       # any downstream step writes/commits/has side effects
    single_visit: bool             # the plan touches the surface exactly once
    actionable: bool = True        # a replan can still avoid the dependent work


def remaining_dependent_work(pa: PlanAssumption) -> float:
    """The normalized first factor, a fraction in [0,1] (D29 §3). 0 only when no
    downstream dependent work remains (the assumption is effectively consumed)."""
    if pa.total_remaining_steps <= 0:
        return 0.0
    frac = pa.downstream_steps / pa.total_remaining_steps
    return min(1.0, max(0.0, frac))


def work_at_risk(pa: PlanAssumption) -> float:
    """The frozen four-factor product, in [0,1]."""
    irreversibility = (IRREVERSIBILITY_COMMIT if pa.downstream_commits
                       else IRREVERSIBILITY_NONE)
    p_no_later = (P_NO_LATER_SINGLE_VISIT if pa.single_visit
                  else P_NO_LATER_RETOUCHED)
    actionability = 1.0 if pa.actionable else 0.0
    return remaining_dependent_work(pa) * irreversibility * p_no_later * actionability


def is_high_risk(pa: PlanAssumption) -> bool:
    """High work-at-risk: earns the paired-observation reserve (§2, §12)."""
    return work_at_risk(pa) > HIGH_RISK_THRESHOLD


def is_blocking_risk(pa: PlanAssumption) -> bool:
    """Blocking: an uncovered miss routes to UNCOVERED_BLOCKING rather than caution."""
    return work_at_risk(pa) > BLOCKING_THRESHOLD
