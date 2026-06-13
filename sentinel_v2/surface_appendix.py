"""Rev-aware surface appendix (B7; the deferred D6 item, prereg_1b §3).

The Phase-1 task-context enrichment (world/surface.py, D6) derives the surface a
plan touches from the world's OpenAPI spec — but only the rev-1 surface (it builds
a default rev-1 app). The v2 probe compiler must consume a REV-AWARE appendix, so a
rev-4 compile sees the rev-4 surface (the expanded fixture repo, the platform
/manifest route) rather than the rev-1 one.

Mirrors N2's path_samples_for_rev exactly: rev 1 is byte-identical to the Phase-1
derivation (delegates to world.surface); rev >= 2 derives mechanically from the
rev-N world's own OpenAPI + fixture collections — no hand-listing, no behavior
change to any Phase-1 path. probe_channel defaults off in every derivation, so the
§4 gate-shadow routes never enter the appendix (byte-identity preserved).

Rule Zero: the derivation is mechanical and ontology-general; it lists routes and
concrete paths, never category-specific probe types.
"""
from __future__ import annotations

import functools
import os
import tempfile

from sentinel_v2.pattern_liveness import path_samples_for_rev
from world.state import PASSAGES, RunConfig
from world.surface import SERVICE_PREFIXES, _openapi_paths, services_touched
from world.surface import derive_surface as _derive_surface_rev1


@functools.lru_cache(maxsize=8)
def openapi_paths_for_rev(world_rev: int) -> dict:
    """The rev-N world's OpenAPI paths. Rev 1 returns the Phase-1 spec VERBATIM
    (byte-identical); rev >= 2 builds a rev-N app and reads its spec."""
    if world_rev <= 1:
        return _openapi_paths()
    from world.server import create_app
    fd, trace_path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    app = create_app(RunConfig(run_id="surface-rev", seed=0, system="surface",
                               task_id="surface", trace_path=trace_path,
                               world_rev=world_rev))
    paths = dict(app.openapi()["paths"])
    app.state.ctx.trace.close()
    try:
        os.unlink(trace_path)
    except OSError:
        pass
    return paths


def concrete_paths_for_rev(task: dict, world_rev: int = 1) -> tuple:
    """The rev-aware CONCRETE path targets for the services this task touches —
    what the probes actually re-read. Rev 1 is the Phase-1 path space restricted
    to touched services; rev >= 2 extends mechanically (e.g. the expanded repo)."""
    touched = services_touched(task)
    samples = path_samples_for_rev(world_rev)
    return tuple(p for p in samples
                 if any(p.startswith(pref) for pref in touched))


def _params(op: dict) -> str:
    return ", ".join(
        f"{p['name']} ({p['in']}{', required' if p.get('required') else ''})"
        for p in op.get("parameters", []))


def surface_appendix(task: dict, *, world_rev: int = 1) -> str:
    """The rev-aware surface appendix the v2 compiler/probes consume. Rev 1 is
    byte-identical to world.surface.derive_surface; rev >= 2 reflects the rev-N
    surface (touched-service routes, platform routes, concrete paths, corpus)."""
    if world_rev <= 1:
        return _derive_surface_rev1(task)

    touched = services_touched(task)
    paths = openapi_paths_for_rev(world_rev)
    lines = [f"World API surface (rev {world_rev}) for the services this plan "
             "touches (derived verbatim from the rev-N world's OpenAPI specification):"]
    for path in sorted(paths):
        if not any(path.startswith(prefix) for prefix in touched):
            continue
        for method, op in sorted(paths[path].items()):
            params = _params(op)
            lines.append(f"- {method.upper()} {path}"
                         + (f" [params: {params}]" if params else ""))

    # platform routes present at this rev that sit outside every service prefix
    # (e.g. /manifest, rev-2+). Mechanical: anything in the spec under no prefix.
    platform = sorted(p for p in paths
                      if not any(p.startswith(prefix) for prefix in SERVICE_PREFIXES))
    if platform:
        lines.append("Platform surface (rev-added, no service prefix): "
                     + ", ".join(platform))

    concrete = concrete_paths_for_rev(task, world_rev)
    if concrete:
        lines.append(f"Concrete paths (rev {world_rev}): " + "; ".join(concrete))

    if "/docs" in touched:
        lines.append("Document corpus index (id: title): "
                     + "; ".join(f"{p['id']}: {p['title']}" for p in PASSAGES))
    return "\n".join(lines)
