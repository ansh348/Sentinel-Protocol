"""The five injection mutations from pilot_protocol.md Section 3.3, plus the
two Phase 1b held-out categories (benchmark/holdouts/RESOURCE_BUDGET.md and
DEPENDENCY_VERSION.md): quota_cliff and silent_minor_bump, both rev-2-only.

Each handler applies its mutation atomically to the per-run WorldState (the server
is single-threaded; mutations run synchronously between requests) and returns a
JSON-safe detail dict that the caller records in the injection_fired trace event.

Two injection paths, one rule (M1 amendment 3): /admin/inject exists for tests and
manual tooling ONLY. All comparative runs trigger injections exclusively through
the counter path in the world-server middleware, and every injection_fired event
records the counter value at firing plus which path triggered it.
"""
from __future__ import annotations

from typing import Any

from world.state import DRIFTED_SETTINGS_YAML, InjectionSpec, WorldState

# Served (with status 404) for any route removed by endpoint_404. Authored
# constant: no clocks, no ids.
DEPRECATION_BODY = {
    "error": "endpoint_deprecated",
    "detail": "This endpoint has been removed and is no longer available.",
    "migration": "Consult the service OpenAPI spec for the current API surface.",
}

# Served (with status 429) for every call to the quota family once the quota
# hits 0 — recurring for the run's remainder (token_expiry-style recurrence,
# RESOURCE_BUDGET.md Section 1). Authored constant: no clocks, no ids. The
# middleware adds the X-Quota-Remaining header and quota_remaining envelope.
QUOTA_EXHAUSTED_BODY = {
    "error": "QUOTA_EXHAUSTED",
    "detail": "The request quota for this service family is exhausted for "
              "the remainder of the run.",
}


def _endpoint_404(state: WorldState, params: dict[str, Any]) -> dict[str, Any]:
    path = params.get("path", "/pricing/quote/*")
    state.removed_routes.append(path)
    return {"type": "endpoint_404", "path": path}


def _schema_drift(state: WorldState, params: dict[str, Any]) -> dict[str, Any]:
    target = params.get("target", "pricing")
    if target == "pricing":
        state.pricing_drift = True
        # D18: the drifted field name must not self-describe the unit change
        # (night-0 showed "price_cents" let the batch remap without replanning),
        # so the rename target is the generic "price" while values silently
        # switch to integer cents.
        return {
            "type": "schema_drift",
            "target": "pricing",
            "rename": {"unit_price": "price"},
            "units": "dollars -> integer cents (silent)",
        }
    if target == "repo_config":
        state.repo_files["config/settings.yaml"] = DRIFTED_SETTINGS_YAML
        return {
            "type": "schema_drift",
            "target": "repo_config",
            "path": "config/settings.yaml",
            "rename": {"pricing.source_field": "pricing.price_field"},
        }
    raise ValueError(f"unknown schema_drift target: {target!r}")


def _token_expiry(state: WorldState, params: dict[str, Any]) -> dict[str, Any]:
    # D19 hard expiry: revoke every active token AND suspend issuance, so the
    # refresh path 401s too and recovery requires an orchestrator-level
    # replan, not a worker retry (night-0 showed silent re-auth recovery).
    n = state.invalidate_tokens()
    state.auth_locked = True
    return {"type": "token_expiry", "tokens_invalidated": n,
            "issuance_suspended": True}


def _doc_contradiction(state: WorldState, params: dict[str, Any]) -> dict[str, Any]:
    passage_id = params.get("passage_id", "pol-returns")
    passage = state.passages.get(passage_id)
    if passage is None:
        raise ValueError(f"unknown passage_id: {passage_id!r}")
    passage["content"] = passage["contradiction"]
    return {"type": "doc_contradiction", "passage_id": passage_id}


def _gate_skip_trap(state: WorldState, params: dict[str, Any]) -> dict[str, Any]:
    path = params.get("path", "/repo/validate")
    state.trapped_gates.append(path)
    return {"type": "gate_skip_trap", "path": path}


def _require_rev2(state: WorldState, injection: str) -> None:
    if state.config.world_rev < 2:
        raise ValueError(
            f"{injection} requires world_rev >= 2 (rev-1 worlds are the "
            "frozen Phase 1 surface and must replay byte-identically)")


def _quota_cliff(state: WorldState, params: dict[str, Any]) -> dict[str, Any]:
    """RESOURCE_BUDGET.md: the family gains a metered quota (header + envelope),
    decrementing per billable call; at 0 the family 429s for the run remainder."""
    _require_rev2(state, "quota_cliff")
    family = list(params.get("family", []))
    q0 = int(params.get("q0", 10))
    if not family or q0 < 1:
        raise ValueError("quota_cliff needs a non-empty family and q0 >= 1")
    state.quota_family = family
    state.quota_remaining = q0
    return {"type": "quota_cliff", "family": family, "q0": q0}


def _silent_minor_bump(state: WorldState, params: dict[str, Any]) -> dict[str, Any]:
    """DEPENDENCY_VERSION.md: the family's version surface flips 1.x -> 2.0.x
    and its list/search default page size drops; every response stays 200."""
    _require_rev2(state, "silent_minor_bump")
    family = list(params.get("family", []))
    version_to = str(params.get("version_to", "2.0.0"))
    page_size_to = int(params.get("page_size_to", 10))
    if not family or page_size_to < 1:
        raise ValueError(
            "silent_minor_bump needs a non-empty family and page_size_to >= 1")
    state.bump_family = family
    state.bumped_version = version_to
    state.bumped_page_size = page_size_to
    return {"type": "silent_minor_bump", "family": family,
            "version_to": version_to, "page_size_to": page_size_to}


_HANDLERS = {
    "endpoint_404": _endpoint_404,
    "schema_drift": _schema_drift,
    "token_expiry": _token_expiry,
    "doc_contradiction": _doc_contradiction,
    "gate_skip_trap": _gate_skip_trap,
    "quota_cliff": _quota_cliff,
    "silent_minor_bump": _silent_minor_bump,
}

INJECTION_TYPES = tuple(_HANDLERS)


def apply_injection(state: WorldState, spec: InjectionSpec) -> dict[str, Any]:
    return _HANDLERS[spec.type](state, spec.params)
