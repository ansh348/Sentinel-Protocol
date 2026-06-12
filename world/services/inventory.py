"""Mock inventory service (aggregation archetype)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Request

from world.pagination import paginated
from world.services.auth import require_token
from world.state import WorldState

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("/items")
def list_items(request: Request, page: Optional[int] = None,
               page_size: Optional[int] = None,
               limit: Optional[int] = None,
               page_limit: Optional[int] = None) -> dict:
    require_token(request)
    state: WorldState = request.app.state.ctx.state
    return paginated(state, "/inventory/items", "items",
                     list(state.inventory), page, page_size, limit,
                     page_limit)


@router.get("/items/{sku}")
def get_item(sku: str, request: Request) -> dict:
    require_token(request)
    state: WorldState = request.app.state.ctx.state
    item = state.inventory.get(sku)
    if item is None:
        raise HTTPException(status_code=404, detail={"error": "unknown_sku", "sku": sku})
    return item
