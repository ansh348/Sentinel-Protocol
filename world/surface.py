"""Mechanical, blind task-context enrichment (deviations.md D6).

One identical rule for every plan, with no reference to injection specs
anywhere: a world service is "touched" iff its route prefix appears verbatim
in the task's goal or plan-step text. For every touched service the appendix
lists its routes and parameters derived verbatim from the world server's own
OpenAPI specification; if the document store is touched, the corpus index
(passage ids and titles) is appended from the world state's fixture table.

Used by the conductor for production runs and by the Phase 0 rich-context
recompile; the lean yaml task_context and the plan/assumption inputs stay
byte-identical, the frozen compile prompt is untouched.
"""
from __future__ import annotations

import functools

from world.state import PASSAGES, RunConfig

SERVICE_PREFIXES = ("/auth", "/inventory", "/pricing", "/shipping", "/docs",
                    "/repo")


@functools.lru_cache(maxsize=1)
def _openapi_paths() -> dict:
    from world.server import create_app
    import os
    import tempfile
    # throwaway app purely to read the generated spec; trace goes to a temp
    # file that is never consumed
    fd, trace_path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    app = create_app(RunConfig(run_id="surface", seed=0, system="surface",
                               task_id="surface", trace_path=trace_path))
    spec = app.openapi()
    app.state.ctx.trace.close()
    try:
        os.unlink(trace_path)
    except OSError:
        pass
    return spec["paths"]


def services_touched(task: dict) -> list[str]:
    text = task["goal"] + " " + " ".join(step["step"] for step in task["plan"])
    return [p for p in SERVICE_PREFIXES if p in text]


def derive_surface(task: dict) -> str:
    touched = services_touched(task)
    lines = ["World API surface for the services this plan touches (derived "
             "verbatim from the world server's OpenAPI specification):"]
    for path in sorted(_openapi_paths()):
        if not any(path.startswith(prefix) for prefix in touched):
            continue
        for method, op in sorted(_openapi_paths()[path].items()):
            params = ", ".join(
                f"{p['name']} ({p['in']}{', required' if p.get('required') else ''})"
                for p in op.get("parameters", []))
            lines.append(f"- {method.upper()} {path}"
                         + (f" [params: {params}]" if params else ""))
    if "/docs" in touched:
        lines.append("Document corpus index (id: title): "
                     + "; ".join(f"{p['id']}: {p['title']}" for p in PASSAGES))
    return "\n".join(lines)


def enriched_context(task: dict) -> str:
    return task["task_context"].strip() + "\n\n" + derive_surface(task)
