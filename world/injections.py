"""The five injection mutations from pilot_protocol.md Section 3.3.

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


_HANDLERS = {
    "endpoint_404": _endpoint_404,
    "schema_drift": _schema_drift,
    "token_expiry": _token_expiry,
    "doc_contradiction": _doc_contradiction,
    "gate_skip_trap": _gate_skip_trap,
}

INJECTION_TYPES = tuple(_HANDLERS)


def apply_injection(state: WorldState, spec: InjectionSpec) -> dict[str, Any]:
    return _HANDLERS[spec.type](state, spec.params)
