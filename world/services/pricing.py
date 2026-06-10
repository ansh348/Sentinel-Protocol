"""Mock pricing service (aggregation archetype).

The schema_drift(target=pricing) injection renames unit_price -> price_cents and
changes units from dollars to integer cents, per protocol Section 3.3.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from world.services.auth import require_token
from world.state import WorldState

router = APIRouter(prefix="/pricing", tags=["pricing"])


def _quote_payload(state: WorldState, sku: str) -> dict:
    price = state.prices.get(sku)
    if price is None:
        raise HTTPException(status_code=404, detail={"error": "unknown_sku", "sku": sku})
    if state.pricing_drift:
        return {"sku": sku, "price_cents": int(round(price * 100)), "currency": "USD"}
    return {"sku": sku, "unit_price": price, "currency": "USD"}


@router.get("/quote/{sku}")
def quote(sku: str, request: Request) -> dict:
    require_token(request)
    return _quote_payload(request.app.state.ctx.state, sku)


@router.get("/quotes")
def quote_by_query(sku: str, request: Request) -> dict:
    """Alternative pricing surface (query-param form), present from the start
    and listed in the OpenAPI spec. Exists so endpoint_404 on /pricing/quote/*
    is plan-invalidating but task-recoverable: the deprecation body points at
    the spec, and a replanning orchestrator can route workers here."""
    require_token(request)
    return _quote_payload(request.app.state.ctx.state, sku)
