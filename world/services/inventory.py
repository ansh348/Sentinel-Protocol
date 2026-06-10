"""Mock inventory service (aggregation archetype)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from world.services.auth import require_token
from world.state import WorldState

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("/items")
def list_items(request: Request) -> dict:
    require_token(request)
    state: WorldState = request.app.state.ctx.state
    return {"items": list(state.inventory)}


@router.get("/items/{sku}")
def get_item(sku: str, request: Request) -> dict:
    require_token(request)
    state: WorldState = request.app.state.ctx.state
    item = state.inventory.get(sku)
    if item is None:
        raise HTTPException(status_code=404, detail={"error": "unknown_sku", "sku": sku})
    return item
