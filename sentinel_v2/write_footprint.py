"""D31 write-surface footprint derivation — CATEGORY-BLIND, plan declarations only.

The planned write FOOTPRINT (probe_compiler_design §3.2; deviations.md D31) is the
set of surface patterns a worker is declared (by the plan) to mutate. It is read
ONLY from the plan steps — never from any failure category, never from any
injection. C0 (analysis/d31_corpus_check.py) established the seen corpus is
SINGLE-EPOCH (no surface written twice; none written-by-A read-by-B), so the
footprint here is a flat surface pattern set; the ordered write-epoch sequence and
the cross-worker committed-epoch read are named residuals (D31 item 5).

`planned_write_patterns` returns fnmatch patterns the attachment / detection seam
match a probe target against (sentinel_v2.attachment._written). A PUT/PATCH (or a
content POST) replaces the whole file/region, so a planned write maps to the
surface it targets — the read-then-write file in a "GET X … PUT it back" step, an
explicit `PUT /path`, or a file-glob token (e.g. src/*.py) named in a write step.
"""
from __future__ import annotations

import re

_VERB_PATH = re.compile(r"\b(GET|PUT|POST|PATCH|DELETE)\b\s+(/[^\s,;.)]+)", re.I)
_WRITE_VERB = re.compile(r"\b(PUT|PATCH)\b", re.I)         # bare write idioms
_FILE_TOKEN = re.compile(r"\b([\w/*]+\.(?:py|yaml|yml|md|json|txt))\b")
# Endpoints that are NOT written-then-read content surfaces (by HTTP role, not by
# category): auth issuance, enforcement gates, packaging.
_NON_CONTENT = ("/auth/token", "/repo/validate", "/docs/validate", "/docs/package")


def _is_content_write(method: str, path: str) -> bool:
    return (method.upper() in ("PUT", "POST", "PATCH")
            and not any(path.startswith(p) for p in _NON_CONTENT))


def _step_text(step) -> str:
    if isinstance(step, dict):
        return step.get("step", "") or ""
    return getattr(step, "step", None) or str(step)


def planned_write_patterns(plan_steps) -> tuple[str, ...]:
    """The fnmatch patterns of surfaces a worker is planned to WRITE, from the plan
    declarations alone. Deterministic; category-blind; injection-blind."""
    pats: set[str] = set()
    for step in plan_steps or ():
        text = _step_text(step)
        get_paths: list[str] = []
        for m, p in _VERB_PATH.findall(text):
            p = p.rstrip("/")
            if m.upper() == "GET":
                get_paths.append(p)
            elif _is_content_write(m, p):
                pats.add(p)
        if _WRITE_VERB.search(text):
            # read-then-write file ("GET X … PUT it back")
            for p in get_paths:
                if _FILE_TOKEN.search(p):
                    pats.add(p)
            # file-glob token named in the write step (e.g. src/*.py)
            for tok in _FILE_TOKEN.findall(text):
                if not any(tok in g for g in get_paths):
                    pats.add(tok if tok.startswith("/") else f"*{tok}")
    return tuple(sorted(pats))
