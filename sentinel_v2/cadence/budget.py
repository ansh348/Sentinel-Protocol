"""Budget allocator (frozen dial 2; decisions/cadence_semantics.md §4, §3; D29).
DETERMINISTIC, category-blind.

The gate is the KG3 clean-overhead denominator, pinned VERBATIM (analysis/gates.py):
US dollars on total_cost_usd, `(clean_treatment_median - clean_batch_median) /
clean_batch_median <= 0.12`. A probe re-observation is deterministic and costs ~$0, so
on dollars the cap is slack and the uncovered valve rarely fires; the dollar lever is
the flag/replan rate, held down by D28 persistence + corroboration suppressing spurious
flags. The paid-probe-per-run-length COUNT is reported as a submetric — the tighter,
real-suite-facing view.

Three-way priority inside the cap (§4): coverage (admission lower bound, first claim),
then live-wobble confirmation (capped at 40% of the post-coverage remainder, risk-
ordered), then speculative (the rest). The uncovered valve flags the LOWEST-work-at-risk
surfaces rather than breaching the cap (blocking above the §3 threshold, else caution).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence

from sentinel_v2.cadence.ledger import CoverageLedger, TerminalState
from sentinel_v2.cadence.workatrisk import BLOCKING_THRESHOLD

# KG3, frozen (decisions/cadence_semantics.md §4 / §17). Dollars on total_cost_usd.
KG3_OVERHEAD_CAP = 0.12
# Confirmation reserve cap, frozen (§4 split, dial 2).
CONFIRMATION_RESERVE_FRACTION = 0.40


def clean_overhead(clean_treatment_usd: float, clean_batch_usd: float) -> float:
    """The KG3 clean-overhead, verbatim: (clean5 - clean1) / clean1 (US dollars)."""
    if clean_batch_usd <= 0:
        return float("inf")
    return (clean_treatment_usd - clean_batch_usd) / clean_batch_usd


def clean_overhead_ok(clean_treatment_usd: float, clean_batch_usd: float, *,
                      cap: float = KG3_OVERHEAD_CAP) -> bool:
    """The frozen gate: clean-run probe overhead under 12% on dollars."""
    return clean_overhead(clean_treatment_usd, clean_batch_usd) <= cap


@dataclass(frozen=True)
class CoverageItem:
    """One coverage claim (an admission-lower-bound observation)."""
    assumption_id: str
    work_at_risk: float
    cost: float                       # in budget units (dollars, or count for the submetric view)


@dataclass(frozen=True)
class ConfirmationItem:
    """One live-wobble confirmation claim (a persistence re-look)."""
    surface_id: str
    work_at_risk: float
    cost: float


@dataclass
class BudgetPlan:
    cap: float
    coverage_reserved: float = 0.0
    confirmation_cap: float = 0.0
    confirmation_reserved: float = 0.0
    speculation_reserved: float = 0.0
    uncovered: list[str] = field(default_factory=list)     # assumption_ids the valve flagged
    paid_probe_count: int = 0
    run_length: int = 0

    @property
    def paid_probe_per_run_length(self) -> float:
        """The reported submetric (§4): paid probe calls ÷ the run's own tool-call
        length — the count dimension, tighter than the dollar gate."""
        return self.paid_probe_count / self.run_length if self.run_length > 0 else float("inf")


def allocate(cap: float, coverage_items: Sequence[CoverageItem], *,
             confirmation_items: Sequence[ConfirmationItem] = (),
             run_length: int = 0, paid_probe_count: int = 0,
             ledger: Optional[CoverageLedger] = None) -> BudgetPlan:
    """Allocate the cap by the frozen three-way priority. Coverage is the first claim;
    if it alone exceeds the cap, the uncovered valve drops the LOWEST-work-at-risk
    coverage surfaces (marking them UNCOVERED in the ledger if one is supplied —
    blocking above the §3 threshold, else caution) until the rest fit. Of the
    post-coverage remainder, confirmation is capped at 40% (risk-ordered), speculation
    takes the rest. Confirmation can never breach because it is capped within the
    remainder; the valve is therefore a coverage-side mechanism (§4)."""
    plan = BudgetPlan(cap=cap, run_length=run_length, paid_probe_count=paid_probe_count)

    # 1. Coverage, first claim. Valve drops lowest-work-at-risk first if over the cap.
    kept = sorted(coverage_items, key=lambda c: c.work_at_risk, reverse=True)  # keep highest-risk
    spend = 0.0
    for item in kept:
        if spend + item.cost <= cap:
            spend += item.cost
        else:
            plan.uncovered.append(item.assumption_id)
            if ledger is not None:
                state = (TerminalState.UNCOVERED_BLOCKING
                         if item.work_at_risk > BLOCKING_THRESHOLD
                         else TerminalState.UNCOVERED_CAUTION)
                ledger.mark(item.assumption_id, state)
    plan.coverage_reserved = spend

    # 2. Confirmation: capped at 40% of the post-coverage remainder, risk-ordered.
    remainder = max(0.0, cap - plan.coverage_reserved)
    plan.confirmation_cap = CONFIRMATION_RESERVE_FRACTION * remainder
    conf_spend = 0.0
    for item in sorted(confirmation_items, key=lambda c: c.work_at_risk, reverse=True):
        if conf_spend + item.cost <= plan.confirmation_cap:
            conf_spend += item.cost
    plan.confirmation_reserved = conf_spend

    # 3. Speculative: the rest.
    plan.speculation_reserved = remainder - plan.confirmation_reserved
    return plan
