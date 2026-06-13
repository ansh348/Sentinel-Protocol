"""v2 §4 gate-shadow surface (probe_compiler_design_v0.4.md §4; build B5).

Read-only GET routes that execute each gate's REAL enforcement predicate in a
no-write 'shadow' mode, answering "would the gate enforce this now?" — never
reading a gate_enabled flag (a status surrogate). repo's shadow is unauthenticated
like POST /repo/validate; docs' shadow requires the worker's token like POST
/docs/validate, so the §4 probe must inherit worker auth context (§5.1
equivalence) to read it.

Registered ONLY on probe-channel worlds (create_app gates on config.probe_channel),
so banked / Phase-1 OpenAPI, D13 path samples, and replays stay byte-identical:
probe_channel defaults off, and every sample-derivation path builds the app with
it off, so these routes never enter the rev-1/rev-N path space.
"""
from __future__ import annotations

from fastapi import APIRouter, Request

from world.services import docs as docs_svc
from world.services import repo as repo_svc
from world.services.auth import require_token
from world.state import WorldState

router = APIRouter(tags=["gate_shadow"])


@router.get("/repo/gate_status")
def repo_gate_status(request: Request) -> dict:
    state: WorldState = request.app.state.ctx.state
    return repo_svc.enforcement_status(state)


@router.get("/docs/gate_status")
def docs_gate_status(request: Request) -> dict:
    require_token(request)  # equivalence: inherits the worker's auth/session view
    state: WorldState = request.app.state.ctx.state
    return docs_svc.gate_shadow_status(state)
