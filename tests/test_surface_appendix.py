"""B7 acceptance: the rev-aware surface appendix (the deferred D6 item).
Rev 1 byte-identical to the Phase-1 derivation; rev >= 2 reflects the rev-N
surface. Tested rev-1 vs rev-4.
"""
from __future__ import annotations

from sentinel_v2.surface_appendix import (concrete_paths_for_rev,
                                          openapi_paths_for_rev, surface_appendix)
from world.surface import _openapi_paths, derive_surface

REPO_DOCS_TASK = {
    "goal": "Migrate the /repo configuration and cross-check the /docs corpus",
    "plan": [{"step": "read /repo/files and run /repo validate"},
             {"step": "read /docs/passages for citations"}],
    "task_context": "lean context",
}
INVENTORY_TASK = {
    "goal": "Aggregate the /inventory catalog",
    "plan": [{"step": "list /inventory/items"}],
    "task_context": "lean context",
}


# -- rev 1 byte-identity -------------------------------------------------------

def test_rev1_appendix_byte_identical_to_phase1():
    assert surface_appendix(REPO_DOCS_TASK, world_rev=1) == \
        derive_surface(REPO_DOCS_TASK)


def test_openapi_paths_rev1_byte_identical_then_extends():
    assert openapi_paths_for_rev(1) == _openapi_paths()
    assert "/manifest" not in openapi_paths_for_rev(1)
    assert "/manifest" in openapi_paths_for_rev(4)   # rev-2+ platform route


# -- rev-aware concrete path targets (what the probes consume) ------------------

def test_concrete_paths_extend_at_rev4():
    rev1 = set(concrete_paths_for_rev(REPO_DOCS_TASK, 1))
    rev4 = set(concrete_paths_for_rev(REPO_DOCS_TASK, 4))
    assert rev1 <= rev4
    # the expanded rev-2+ fixture repo reaches the concrete targets mechanically
    assert "/repo/files/src/tax.py" not in rev1
    assert "/repo/files/src/tax.py" in rev4


def test_concrete_paths_restricted_to_touched_services():
    paths = concrete_paths_for_rev(INVENTORY_TASK, 2)
    assert paths and all(p.startswith("/inventory") for p in paths)
    assert "/inventory/items" in paths
    assert not any(p.startswith("/repo") or p.startswith("/docs") for p in paths)


# -- rev-4 appendix string reflects the richer surface -------------------------

def test_rev4_appendix_reflects_platform_and_extended_surface():
    app1 = surface_appendix(REPO_DOCS_TASK, world_rev=1)
    app4 = surface_appendix(REPO_DOCS_TASK, world_rev=4)
    assert "/manifest" not in app1 and "/manifest" in app4   # platform surface
    assert "src/tax.py" not in app1 and "src/tax.py" in app4  # rev-2+ fixture
    assert "rev 4" in app4


# -- byte-identity guard: §4 gate-shadow never leaks into the appendix ----------

def test_gate_shadow_routes_absent_from_appendix():
    assert "/repo/gate_status" not in openapi_paths_for_rev(4)
    assert "gate_status" not in surface_appendix(REPO_DOCS_TASK, world_rev=4)
