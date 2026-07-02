"""Mock regional-demand evidence service (benchmark_1c sharded-allocation task).

Serves N per-region demand-evidence shards. Each shard is a fixed-shape JSON
record; the single_shard_value_mutation injection changes exactly ONE region's
numeric demand value (toward the mean, §4) while HTTP status, schema, field names,
response length, and provenance_id stay invariant. World-side only (no treatment
code). Active only when the run's RunConfig sets n_regions (default off)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from world.state import WorldState

router = APIRouter(prefix="/regions", tags=["regions"])


@router.get("")
def list_regions(request: Request) -> dict:
    """GET /regions — the manifest of region ids and their evidence URLs (NOTHING
    else: no demand values, no total, no checksum — §1/§3.1)."""
    state: WorldState = request.app.state.ctx.state
    return {"regions": [{"region_id": rid, "url": f"/regions/{rid}/evidence"}
                        for rid in state.region_order]}


@router.get("/{region_id}/evidence")
def region_evidence(region_id: str, request: Request) -> dict:
    """GET /regions/{id}/evidence — one immutable demand-evidence record. The
    mutated shard serves d'_j; every other shard is byte-identical to clean."""
    state: WorldState = request.app.state.ctx.state
    if region_id not in state.regions:
        raise HTTPException(status_code=404, detail="unknown region")
    demand = state.regions[region_id]
    mut = state.regions_mutation
    if mut and mut.get("region_id") == region_id:
        demand = int(mut["d_prime"])              # single-shard value mutation (§4)
    # Fixed-shape record; demand is 4-digit fixed-width [1000,9999] by construction,
    # so the numeric value never leaks its change by length (§4).
    return {
        "region_id": region_id,
        "normalized_verified_demand": int(demand),
        "provenance_id": state.region_provs[region_id],
        "reporting_period": "FY-QC",
        "status": "VERIFIED",
    }
