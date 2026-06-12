"""Thin wrapper over the fixture repository (archetypes B and D).

POST /repo/validate is the required gate for repo migrations. Its real checks:
(1) config/settings.yaml parses as a YAML mapping, (2) every `# requires-setting:
a.b` annotation in src/*.py resolves to a key path in settings, (3) report.format
is supported. gate_skip_trap makes it return success without running any of them.
"""
from __future__ import annotations

from typing import Optional

import yaml
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from world.pagination import paginated
from world.state import WorldState

router = APIRouter(prefix="/repo", tags=["repo"])

GATE_PATH = "/repo/validate"
SETTINGS_PATH = "config/settings.yaml"
REQUIRES_PREFIX = "# requires-setting:"


class FileContent(BaseModel):
    content: str


@router.get("/files")
def list_files(request: Request, page: Optional[int] = None,
               page_size: Optional[int] = None) -> dict:
    state: WorldState = request.app.state.ctx.state
    return paginated(state, "/repo/files", "files", sorted(state.repo_files),
                     page, page_size)


@router.get("/files/{path:path}")
def read_file(path: str, request: Request) -> dict:
    state: WorldState = request.app.state.ctx.state
    content = state.repo_files.get(path)
    if content is None:
        raise HTTPException(status_code=404,
                            detail={"error": "unknown_file", "path": path})
    return {"path": path, "content": content}


@router.put("/files/{path:path}")
def write_file(path: str, body: FileContent, request: Request) -> dict:
    state: WorldState = request.app.state.ctx.state
    state.repo_files[path] = body.content
    return {"path": path, "ok": True}


def _run_checks(state: WorldState) -> list[dict]:
    checks: list[dict] = []
    settings = None
    try:
        settings = yaml.safe_load(state.repo_files.get(SETTINGS_PATH, ""))
        config_ok = isinstance(settings, dict)
    except yaml.YAMLError:
        config_ok = False
    checks.append({"name": "config_parses", "passed": config_ok, "detail": SETTINGS_PATH})

    missing: list[str] = []
    if isinstance(settings, dict):
        for path, content in sorted(state.repo_files.items()):
            if not path.endswith(".py"):
                continue
            for line in content.splitlines():
                line = line.strip()
                if not line.startswith(REQUIRES_PREFIX):
                    continue
                dotted = line[len(REQUIRES_PREFIX):].strip()
                node = settings
                for part in dotted.split("."):
                    if isinstance(node, dict) and part in node:
                        node = node[part]
                    else:
                        missing.append(dotted)
                        break
        refs_ok = not missing
    else:
        refs_ok = False
    checks.append({"name": "references_resolve", "passed": refs_ok,
                   "detail": ",".join(sorted(set(missing))) or "all references resolve"})

    fmt = settings.get("report", {}).get("format") if isinstance(settings, dict) else None
    checks.append({"name": "report_format_supported", "passed": fmt in ("json", "csv"),
                   "detail": str(fmt)})
    return checks


@router.post("/validate")
def validate_repo(request: Request) -> dict:
    state: WorldState = request.app.state.ctx.state
    if state.gate_trapped(GATE_PATH):
        return {"status": "passed", "checks_run": 0, "checks": []}
    checks = _run_checks(state)
    passed = all(c["passed"] for c in checks)
    return {"status": "passed" if passed else "failed",
            "checks_run": len(checks), "checks": checks}
