"""Live re-observation source + harvest-equivalence gate
(decisions/cadence_semantics.md §5, §8; D29). DETERMINISTIC, category-blind.

The LIVE source carries headers (resolving the trace-only limitation of D28's
`TraceReObservations`) and satisfies corroboration's `ReObservationSource` Protocol
and `PRE_COMPLETION_SWEEP_DEPENDENCY`. A worker's own read refreshes COVERAGE only if
the six-condition equivalence gate holds; anything less is telemetry, never coverage.
A worker request-side error (a 4xx from a malformed worker call) belongs to the
request, not the surface, so it is never coverage and never becomes a surface
observation — it can never trip the D28 status fast path.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from sentinel_v2.probe_spec import Lens, LensOp
from sentinel_v2.probes import ProbeResult, read_field, read_header

_READ_METHODS = frozenset({"GET", "HEAD"})
_MISS = object()
# Canonical request-malformation status codes (about HTTP request semantics, not any
# failure category): a 4xx here is the worker's request, not a surface state change.
_REQUEST_MALFORMATION_CODES = frozenset({400, 405, 422})


@dataclass(frozen=True)
class WorkerRead:
    """One worker call, captured for the harvest watch. `result` is the raw response
    (carries headers); `auth_principal` is the worker's principal class; `cache_state`
    is one of fresh / revalidated / stale; `malformed` marks a worker-side bad call."""
    surface_id: str
    method: str
    auth_principal: str
    cache_state: str
    raw_captured_pre_transform: bool
    result: ProbeResult
    malformed: bool = False


@dataclass(frozen=True)
class HarvestVerdict:
    ok: bool
    reason: str = ""


def is_request_side_error(read: WorkerRead) -> bool:
    """A 4xx that belongs to the REQUEST, not the surface (D29 §8). Never coverage,
    never a surface observation, never the status fast path."""
    if read.malformed:
        return True
    if read.method.upper() not in _READ_METHODS:
        return True            # a write's 4xx is the worker's request, not a surface read
    status = read.result.status
    return status is not None and status in _REQUEST_MALFORMATION_CODES


def monitored_region_present(result: ProbeResult, lens: Lens) -> bool:
    """Condition 2: the response actually contains the monitored field/value/order/
    structure/relation/status the assumption checks. A paginated or partial subset
    that excludes the monitored region fails here."""
    op = lens.op
    if op is LensOp.STATUS_READ:
        return result.status is not None
    if op is LensOp.HEADER_READ:
        return read_header(result, lens.header_name) is not None
    if op in (LensOp.FIELD_READ, LensOp.ORDERED_SUBARRAY, LensOp.RELATION):
        return read_field(result, lens.pointer, default=_MISS) is not _MISS
    if op in (LensOp.SCHEMA_FINGERPRINT, LensOp.CONTENT_HASH, LensOp.GATE_SHADOW):
        if lens.pointer:
            return read_field(result, lens.pointer, default=_MISS) is not _MISS
        return result.body is not None
    return result.body is not None


def harvest_equivalence(read: WorkerRead, *, expected_surface: str, lens: Lens,
                        expected_principal: str) -> HarvestVerdict:
    """The six-condition predicate (§8). All must hold for the read to refresh
    coverage: same surface identity; same projection/lens (monitored region present);
    same auth/principal class; cache-fresh or origin-revalidated; side-effect-free
    (a read); raw response captured before the worker transforms it."""
    if read.surface_id != expected_surface:
        return HarvestVerdict(False, "different surface identity")
    if read.method.upper() not in _READ_METHODS:
        return HarvestVerdict(False, "not side-effect-free (a write, not a read)")
    if read.auth_principal != expected_principal:
        return HarvestVerdict(False, "different auth/principal class")
    if read.cache_state not in ("fresh", "revalidated"):
        return HarvestVerdict(False, "stale cached read (not cache-fresh or revalidated)")
    if not read.raw_captured_pre_transform:
        return HarvestVerdict(False, "response not captured before worker transform")
    if not monitored_region_present(read.result, lens):
        return HarvestVerdict(False, "monitored region absent (partial/paginated subset)")
    return HarvestVerdict(True, "harvest-equivalent: credited as coverage")


class LiveReObservationSource:
    """A header-carrying `ReObservationSource` (corroboration Protocol; satisfies
    PRE_COMPLETION_SWEEP_DEPENDENCY). Coverage observations come from harvested worker
    reads that clear the gate and from dedicated probes via the live executor; both
    carry headers. `observations(target)` returns only the COVERAGE stream, in order —
    so request-side errors and non-equivalent reads (telemetry) can never trip the
    D28 status fast path."""

    def __init__(self, executor: Any = None) -> None:
        self._coverage: dict[str, list[ProbeResult]] = {}
        self._telemetry: dict[str, list[ProbeResult]] = {}
        self._executor = executor   # a ProbeExecutor (live, carries headers) or None

    def harvest(self, read: WorkerRead, *, lens: Lens,
                expected_principal: str) -> HarvestVerdict:
        """Credit a worker's own read as coverage iff it clears the gate; otherwise
        record it as telemetry, never coverage. Request-side errors are pure telemetry."""
        if is_request_side_error(read):
            self._telemetry.setdefault(read.surface_id, []).append(read.result)
            return HarvestVerdict(
                False, "worker request-side error: belongs to the request, not the "
                       "surface — never coverage, never the status fast path")
        verdict = harvest_equivalence(read, expected_surface=read.surface_id,
                                      lens=lens, expected_principal=expected_principal)
        bucket = self._coverage if verdict.ok else self._telemetry
        bucket.setdefault(read.surface_id, []).append(read.result)
        return verdict

    def probe(self, target: str, *, params: Any = None,
              headers: Any = None) -> Optional[ProbeResult]:
        """A dedicated re-fetch via the live executor — origin-fresh, the worker's
        auth, carries headers. Coverage by construction. Returns None with no executor."""
        if self._executor is None:
            return None
        result = self._executor.get(target, params=params, headers=headers)
        self._coverage.setdefault(target, []).append(result)
        return result

    def observations(self, target: str) -> list[ProbeResult]:
        return list(self._coverage.get(target, []))

    def telemetry(self, target: str) -> list[ProbeResult]:
        return list(self._telemetry.get(target, []))
