"""Programmatic success checker for task b1 (exact-match against the world's
ground truth; no LLM grading — protocol Section 4).

D16 blind construction: every constant below derives from tasks/b1.yaml at
the frozen commit; the pre-migration baseline (the preserved key value, which
src files carried the annotation) is derived at import time from the world's
authored fixtures (world.state.REPO_FILES) — never from run outputs."""
from __future__ import annotations

from typing import Any

import yaml

from world.state import REPO_FILES

# tasks/b1.yaml goal: rename pricing.source_field -> pricing.price_source in
# config/settings.yaml (preserving its value and all other keys), update every
# "# requires-setting:" annotation in src/, update README.md if it mentions
# the old key; output {"files_changed": [paths], "validate_status": "passed"}.
SETTINGS_PATH = "config/settings.yaml"
README_PATH = "README.md"
OLD_DOTTED = "pricing.source_field"
NEW_DOTTED = "pricing.price_source"
ANNOTATION_PREFIX = "# requires-setting:"

ORIGINAL_VALUE = yaml.safe_load(REPO_FILES[SETTINGS_PATH])["pricing"]["source_field"]


def _annotated_paths(files: dict[str, str], dotted: str) -> set[str]:
    hits: set[str] = set()
    for path, content in files.items():
        if not path.endswith(".py") or not isinstance(content, str):
            continue
        for line in content.splitlines():
            line = line.strip()
            if (line.startswith(ANNOTATION_PREFIX)
                    and line[len(ANNOTATION_PREFIX):].strip() == dotted):
                hits.add(path)
    return hits


_ORIGINALLY_ANNOTATED = _annotated_paths(REPO_FILES, OLD_DOTTED)
_REQUIRED_CHANGED = {SETTINGS_PATH} | _ORIGINALLY_ANNOTATED
if OLD_DOTTED in REPO_FILES[README_PATH]:
    _REQUIRED_CHANGED.add(README_PATH)


def _expected_settings() -> dict:
    expected = yaml.safe_load(REPO_FILES[SETTINGS_PATH])
    del expected["pricing"]["source_field"]
    expected["pricing"]["price_source"] = ORIGINAL_VALUE
    return expected


def check(final_report: Any, ground_truth: dict) -> tuple[bool, str]:
    if not isinstance(final_report, dict):
        return False, "final report is not a JSON object"
    problems: list[str] = []

    if final_report.get("validate_status") != "passed":
        problems.append(
            f"validate_status {final_report.get('validate_status')!r} != 'passed'")

    repo_files = ground_truth.get("repo_files") or {}
    changed = final_report.get("files_changed")
    if (not isinstance(changed, list) or not changed
            or not all(isinstance(p, str) for p in changed)):
        problems.append("files_changed is not a non-empty list of paths")
        changed = []
    for path in changed:
        if path not in repo_files:
            problems.append(f"files_changed lists unknown file {path!r}")
    for path in sorted(_REQUIRED_CHANGED - set(changed)):
        problems.append(f"files_changed omits {path!r}")

    try:
        settings = yaml.safe_load(repo_files.get(SETTINGS_PATH, ""))
    except yaml.YAMLError:
        settings = None
    if not isinstance(settings, dict) or not isinstance(settings.get("pricing"), dict):
        problems.append(
            f"{SETTINGS_PATH}: does not parse to a mapping with a pricing section")
    else:
        pricing = settings["pricing"]
        if "source_field" in pricing:
            problems.append(f"{SETTINGS_PATH}: old key {OLD_DOTTED} still present")
        if pricing.get("price_source") != ORIGINAL_VALUE:
            problems.append(
                f"{SETTINGS_PATH}: price_source {pricing.get('price_source')!r}"
                f" != preserved value {ORIGINAL_VALUE!r}")
        if settings != _expected_settings():
            problems.append(f"{SETTINGS_PATH}: deviates beyond the single key rename")

    for path in sorted(_annotated_paths(repo_files, OLD_DOTTED)):
        problems.append(f"{path}: stale annotation {ANNOTATION_PREFIX} {OLD_DOTTED}")
    new_annotated = _annotated_paths(repo_files, NEW_DOTTED)
    for path in sorted(_ORIGINALLY_ANNOTATED - new_annotated):
        problems.append(
            f"{path}: missing updated annotation {ANNOTATION_PREFIX} {NEW_DOTTED}")

    if OLD_DOTTED in repo_files.get(README_PATH, ""):
        problems.append(f"{README_PATH}: still mentions {OLD_DOTTED}")

    if problems:
        return False, "; ".join(problems[:10])
    return True, "migration complete: key renamed, annotations updated, validate passed"
