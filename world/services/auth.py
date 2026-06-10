"""Mock auth service: issues expirable bearer tokens.

Token strings are seed-derived (see WorldState.issue_token); expiry is a state
flag flipped by the token_expiry injection, never a clock.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from world.state import WorldState

router = APIRouter(prefix="/auth", tags=["auth"])


def require_token(request: Request) -> str:
    """Shared auth guard used by the inventory, pricing, shipping, and docs
    services. Raises 401 once the token_expiry injection has revoked the token."""
    state: WorldState = request.app.state.ctx.state
    header = request.headers.get("authorization", "")
    token = header[len("Bearer "):].strip() if header.startswith("Bearer ") else ""
    if not token or not state.token_valid(token):
        raise HTTPException(
            status_code=401,
            detail={
                "error": "invalid_token",
                "reason": "missing, unknown, or expired bearer token",
            },
        )
    return token


@router.post("/token")
def issue_token(request: Request) -> dict:
    state: WorldState = request.app.state.ctx.state
    token = state.issue_token()
    return {"token": token, "token_type": "bearer", "expires_in": 3600}


@router.get("/validate")
def validate_token(request: Request) -> dict:
    require_token(request)
    return {"valid": True}
