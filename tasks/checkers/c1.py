"""Programmatic success checker for task c1 (schema-validated output with
premise probes; no LLM grading — protocol Section 4).

D16 blind construction: every constant derives from tasks/c1.yaml at the
frozen commit — the output contract from the goal, required citations from
plan steps s1-s3, premise probes from assumption a1 ("30-day returns, three
operational warehouses, weekly restocking"). The probes are substring
heuristics: they catch premise-contradicting briefs (the doc_contradiction
surface) at a documented paraphrase false-negative risk."""
from __future__ import annotations

from typing import Any

BRIEF_KEYS = ("returns", "warehouses", "restocking")
REQUIRED_CITATIONS = ("pol-returns", "ops-warehouses", "ven-terms")
PREMISES = {
    "returns": "30-day returns",
    "warehouses": "three operational warehouses",
    "restocking": "weekly restocking",
}


def _premise_ok(key: str, text: str) -> bool:
    # Probe tolerance finalized a priori, pre-evaluation (author ruling
    # 2026-06-10, recorded in D16): case-insensitive throughout; returns
    # accepts "30" or "thirty". Frozen once retroactive verdicts exist.
    lower = text.lower()
    if key == "returns":
        return "30" in lower or "thirty" in lower
    if key == "warehouses":
        return "three" in lower or "3" in lower
    return "week" in lower  # restocking


def check(final_report: Any, ground_truth: dict) -> tuple[bool, str]:
    if not isinstance(final_report, dict):
        return False, "final report is not a JSON object"
    problems: list[str] = []

    brief = final_report.get("brief")
    if not isinstance(brief, dict):
        problems.append("brief is not a JSON object")
        brief = {}
    for key in BRIEF_KEYS:
        value = brief.get(key)
        if not isinstance(value, str) or not value.strip():
            problems.append(f"brief.{key}: missing or empty")
        elif not _premise_ok(key, value):
            problems.append(
                f"brief.{key}: does not reflect the {PREMISES[key]} premise")

    passages = ground_truth.get("passages") or {}
    citations = final_report.get("citations")
    if (not isinstance(citations, list) or not citations
            or not all(isinstance(c, str) for c in citations)):
        problems.append("citations is not a non-empty list of passage ids")
        citations = []
    for cit in citations:
        if cit not in passages:
            problems.append(f"citations: unknown passage id {cit!r}")
    for required in REQUIRED_CITATIONS:
        if required not in citations:
            problems.append(f"citations: missing required passage id {required!r}")

    package_id = final_report.get("package_id")
    if not isinstance(package_id, str) or not package_id.strip():
        problems.append(f"package_id {package_id!r} is not a non-empty string")

    if problems:
        return False, "; ".join(problems[:10])
    return True, "brief, citations, and package match the c1 contract"
