"""Mock pricing service (aggregation archetype).

The schema_drift(target=pricing) injection renames unit_price -> price_cents and
changes units from dollars to integer cents, per protocol Section 3.3.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from world.services.auth import require_token
from world.state import WorldState

router = APIRouter(prefix="/pricing", tags=["pricing"])


@router.get("/quote/{sku}")
def quote(sku: str, request: Request) -> dict:
    require_token(request)
    state: WorldState = request.app.state.ctx.state
    price = state.prices.get(sku)
    if price is None:
        raise HTTPException(status_code=404, detail={"error": "unknown_sku", "sku": sku})
    if state.pricing_drift:
        return {"sku": sku, "price_cents": int(round(price * 100)), "currency": "USD"}
    return {"sku": sku, "unit_price": price, "currency": "USD"}
