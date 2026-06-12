"""Mock shipping service (aggregation archetype)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Request

from world.pagination import paginated
from world.services.auth import require_token
from world.state import DESTINATIONS, WorldState

router = APIRouter(prefix="/shipping", tags=["shipping"])


@router.get("/destinations")
def list_destinations(request: Request, page: Optional[int] = None,
                      page_size: Optional[int] = None,
                      limit: Optional[int] = None) -> dict:
    require_token(request)
    state: WorldState = request.app.state.ctx.state
    return paginated(state, "/shipping/destinations", "destinations",
                     list(DESTINATIONS), page, page_size, limit)


@router.get("/rates/{sku}")
def get_rate(sku: str, dest: str, request: Request) -> dict:
    require_token(request)
    state: WorldState = request.app.state.ctx.state
    entry = state.shipping.get((sku, dest))
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "unknown_sku_or_destination", "sku": sku, "dest": dest},
        )
    return {"sku": sku, "dest": dest, **entry}
