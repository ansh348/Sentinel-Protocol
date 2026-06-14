"""Dependency-graph audit + two-build replay discriminator
(decisions/cadence_semantics.md §19, §17; D29), ESCROW-SIDE under the D25 quarantine.
DETERMINISTIC, category-blind.

For a completed run the audit (1) reconstructs the output-dependency graph from raw
tool calls and asserts every dependency surface is in the registry, counting any
absentee as a measured silent miss (the §14 residual); (2) asserts every load-bearing
assumption has exactly one terminal ledger state; (3) checks coverage-purchased against
overhead for cost honesty; (4) runs the §17 two-build replay discriminator. It never
feeds compiler iteration and never computes a held-out denominator in-line (D25).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional, Sequence

from sentinel_v2.cadence.budget import clean_overhead_ok
from sentinel_v2.cadence.ledger import CoverageLedger


def two_build_replay_discriminator(run_fn: Callable[[Any], Any],
                                   choices: Sequence[Any] = (0, 1)) -> bool:
    """Run `run_fn(hidden_choice)` under two builds that differ ONLY in a hidden
    internal choice (not a frozen knob) and confirm identical outcomes. If outcomes
    differ, a knob is missing from the §17 table (the freeze is incomplete). Returns
    True iff every build produced an identical outcome."""
    outcomes = [run_fn(c) for c in choices]
    first = outcomes[0]
    return all(o == first for o in outcomes[1:])


@dataclass
class AuditReport:
    silent_misses: list[str] = field(default_factory=list)   # dependency surfaces absent from the registry
    open_assumptions: list[str] = field(default_factory=list)
    all_terminal: bool = True
    coverage_purchased: Optional[float] = None
    overhead_ok: Optional[bool] = None
    discriminator_identical: Optional[bool] = None

    @property
    def passed(self) -> bool:
        """The audit passes iff every assumption is terminal, the discriminator (when
        run) was identical, and the overhead gate (when checked) held. Silent misses are
        REPORTED (the §14 residual), not a pass/fail in themselves."""
        ok = self.all_terminal
        if self.discriminator_identical is not None:
            ok = ok and self.discriminator_identical
        if self.overhead_ok is not None:
            ok = ok and self.overhead_ok
        return ok


def dependency_graph_audit(
        *, registry: Iterable[str], dependency_surfaces: Iterable[str],
        ledger: CoverageLedger,
        coverage_purchased: Optional[float] = None,
        clean_treatment_usd: Optional[float] = None,
        clean_batch_usd: Optional[float] = None,
        discriminator: Optional[Callable[[Any], Any]] = None) -> AuditReport:
    """Run the §19 audit. `dependency_surfaces` is the output-dependency graph
    reconstructed from raw tool calls; any surface absent from `registry` is a measured
    silent miss (§14 residual). `discriminator`, when supplied, is a run_fn for the
    two-build replay check."""
    reg = set(registry)
    report = AuditReport()
    report.silent_misses = sorted({s for s in dependency_surfaces if s not in reg})
    report.open_assumptions = [e.assumption_id for e in ledger.open_entries()]
    report.all_terminal = not report.open_assumptions
    report.coverage_purchased = coverage_purchased
    if clean_treatment_usd is not None and clean_batch_usd is not None:
        report.overhead_ok = clean_overhead_ok(clean_treatment_usd, clean_batch_usd)
    if discriminator is not None:
        report.discriminator_identical = two_build_replay_discriminator(discriminator)
    return report
