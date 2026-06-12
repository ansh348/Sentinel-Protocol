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
    rev3 = state.config.world_rev >= 3

    def entry(svc: str) -> dict:
        e = {
            "version": state.service_version(f"/{svc}"),
            "default_page_size": state.default_page_size(f"/{svc}"),
        }
        if rev3:
            # DV spec rev 2: the manifest documents the pagination-parameter
            # rename (page_size -> limit on the bumped family). Rev-2 worlds
            # keep the original shape (the rev-1-spec qualification runs
            # replay against them).
            e["page_size_param"] = state.page_size_param(f"/{svc}")
        return e

    return {
        "platform": "tripwire-world",
        "services": {svc: entry(svc) for svc in SERVICES},
    }
