"""Cadence layer (v2): the frozen D29 semantics (decisions/cadence_semantics.md).

DETERMINISTIC, $0 LLM, category-blind. Everything here lives behind the v2 flag; the
flag-off path is byte-identical to Phase 1. Cadence SUPPLIES corroboration's confirming
re-look (the live, header-carrying ReObservationSource) but does NOT change D28's
decision logic.

Built checkpoint by checkpoint: C1 ledger + work-at-risk + admission; C2 live source +
harvest gate; C3 barriers + freshness + relations; C4 budget allocator; C5 wobble
throttle + probe-failure; C6 provisional promotion + replan GC; C7 UNCOVERED accounting.
"""
from __future__ import annotations

from sentinel_v2.cadence.throttle import (TRANSPORT_RETRY_BUDGET, OpenWobble,
                                          ProbeOutcome, WobbleThrottle,
                                          probe_with_retry, route_probe_outcome,
                                          route_terminal_time_singleton)
from sentinel_v2.cadence.budget import (CONFIRMATION_RESERVE_FRACTION,
                                        KG3_OVERHEAD_CAP, BudgetPlan,
                                        ConfirmationItem, CoverageItem, allocate,
                                        clean_overhead, clean_overhead_ok)
from sentinel_v2.cadence.barriers import (RELATION_UNDER_EMISSION_RESIDUAL,
                                          CoverageSpec, Observation, WorkerPlan,
                                          close_specs, fresh_observation,
                                          had_stale_observation,
                                          relation_consistent_snapshot,
                                          run_barrier_hierarchy)
from sentinel_v2.cadence.harvest import (HarvestVerdict, LiveReObservationSource,
                                         WorkerRead, harvest_equivalence,
                                         is_request_side_error,
                                         monitored_region_present)
from sentinel_v2.cadence.ledger import (NON_TERMINAL, AdmissionResult,
                                        CoverageLedger, FinalizationError,
                                        LedgerEntry, TerminalState, admit,
                                        min_coverage_lower_bound)
from sentinel_v2.cadence.workatrisk import (BLOCKING_THRESHOLD,
                                            HIGH_RISK_THRESHOLD, PlanAssumption,
                                            is_blocking_risk, is_high_risk,
                                            remaining_dependent_work,
                                            work_at_risk)

__all__ = [
    "PlanAssumption", "work_at_risk", "remaining_dependent_work",
    "is_high_risk", "is_blocking_risk", "HIGH_RISK_THRESHOLD", "BLOCKING_THRESHOLD",
    "TerminalState", "LedgerEntry", "CoverageLedger", "FinalizationError",
    "NON_TERMINAL", "AdmissionResult", "admit", "min_coverage_lower_bound",
    "WorkerRead", "HarvestVerdict", "harvest_equivalence", "is_request_side_error",
    "monitored_region_present", "LiveReObservationSource",
    "Observation", "CoverageSpec", "WorkerPlan", "close_specs",
    "fresh_observation", "had_stale_observation", "relation_consistent_snapshot",
    "run_barrier_hierarchy", "RELATION_UNDER_EMISSION_RESIDUAL",
    "KG3_OVERHEAD_CAP", "CONFIRMATION_RESERVE_FRACTION", "clean_overhead",
    "clean_overhead_ok", "CoverageItem", "ConfirmationItem", "BudgetPlan", "allocate",
    "WobbleThrottle", "OpenWobble", "route_terminal_time_singleton",
    "TRANSPORT_RETRY_BUDGET", "probe_with_retry", "route_probe_outcome", "ProbeOutcome",
]
