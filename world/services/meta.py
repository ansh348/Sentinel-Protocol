"""Platform manifest: the re-readable version surface (rev 2 only;
DEPENDENCY_VERSION.md Section 1).

Registered only on world_rev >= 2 apps, so rev-1 OpenAPI specs, D13 path
samples, and banked-trace replays are untouched. Unauthenticated (like /repo)
so the surface is cheaply re-readable; countable like any world route, so
reading it costs a tool call — correct monitoring economics.
"""
from __future__ import annotations

from fastapi import APIRouter, Request

from world.state import WorldState

router = APIRouter(tags=["meta"])

SERVICES = ("auth", "inventory", "pricing", "shipping", "docs", "repo")


@router.get("/manifest")
def manifest(request: Request) -> dict:
    state: WorldState = request.app.state.ctx.state
    return {
        "platform": "tripwire-world",
        "services": {
            svc: {
                "version": state.service_version(f"/{svc}"),
                "default_page_size": state.default_page_size(f"/{svc}"),
            }
            for svc in SERVICES
        },
    }
