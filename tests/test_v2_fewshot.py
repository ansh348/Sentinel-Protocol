"""C1 acceptance: the frozen few-shot example set (deviations.md D27).
One example per change-shape, drawn ONLY from the five seen categories, every
surface groundable, and NO held-out reference anywhere (Rule Zero).
"""
from __future__ import annotations

import json
from pathlib import Path

from sentinel_v2.pattern_liveness import path_samples_for_rev
from world.server import classify_url_pattern

REPO_ROOT = Path(__file__).resolve().parent.parent
FEWSHOT = REPO_ROOT / "prompts" / "v2_compile_fewshot.json"

# the six general change-shapes, exactly (substrate FaultShape order)
SIX_SHAPES = ["vanished", "status-moved", "structure-changed",
              "value-moved", "order-scrambled", "relationship-broke"]

# held-out identifiers that must never appear (the two held-out categories +
# their rev-2 surface tokens). Rule Zero: the few-shot is seen-only.
HELD_OUT_TOKENS = [
    "quota_cliff", "silent_minor_bump", "resource_budget", "dependency_version",
    "/manifest", "x-api-version", "x-quota", "x-total-count", "page_limit",
    "page_size", "total_count", "quota_remaining", "bumped_version", "version_to",
]


def _load() -> dict:
    return json.loads(FEWSHOT.read_text(encoding="utf-8"))


def test_one_example_per_change_shape():
    examples = _load()["examples"]
    shapes = [e["change_shape"] for e in examples]
    assert shapes == SIX_SHAPES                      # all six, in order, exactly once
    assert len(set(shapes)) == 6


def test_every_surface_grounds_against_seen_world():
    samples = path_samples_for_rev(4)                # the 1b world rev
    for e in _load()["examples"]:
        surface = e["assumption"]["surface"]
        assert classify_url_pattern(surface, samples) is not None, \
            f"few-shot surface {surface!r} does not ground"


def test_value_moved_pins_a_pointer_others_do_not():
    """Teaches the pointer rule: pin a field ONLY for a value-on-a-stable-shape
    dependency (value-moved); otherwise watch the surface."""
    for e in _load()["examples"]:
        a = e["assumption"]
        if e["change_shape"] == "value-moved":
            assert a.get("pointer"), "value-moved must pin the field where the value lives"
        else:
            assert "pointer" not in a, \
                f"{e['change_shape']} should watch the surface, not pin a field"


def test_no_held_out_reference_anywhere():
    raw = FEWSHOT.read_text(encoding="utf-8").lower()
    leaks = [tok for tok in HELD_OUT_TOKENS if tok in raw]
    assert leaks == [], f"few-shot leaks held-out tokens (Rule Zero): {leaks}"


def test_no_failure_category_label_in_examples():
    """Category-blind: the five seen category labels must not appear either."""
    raw = FEWSHOT.read_text(encoding="utf-8")
    for label in ("API_SURFACE", "SCHEMA_DRIFT", "PERMISSION_AUTH",
                  "RETRIEVAL_INTEGRITY", "TOOL_CONTRACT"):
        assert label not in raw, f"category label {label} leaked into the few-shot"


def test_every_assumption_has_the_soft_fields():
    for e in _load()["examples"]:
        a = e["assumption"]
        assert a["plan_step"] and a["world_fact"] and a["surface"]
        assert a["recovery_hint"]
        # soft output carries NO lens/firing/probe fields
        assert not ({"lens", "comparison", "fault_shape", "method", "evidence_class",
                     "cadence_hint", "on_trigger"} & set(a))
