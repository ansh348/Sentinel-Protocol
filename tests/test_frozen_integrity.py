"""Guards on the FROZEN pre-registered materials: byte hashes pinned in the
FROZEN commit must hold on every test run, and the DSL must stay semantically
intact (importable, validating, rejecting)."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from fake_claude import VALID_TRIPWIRE_SET
from sentinel.dsl import Tripwire, TripwireSet

REPO_ROOT = Path(__file__).resolve().parent.parent

# sha256 of the frozen files as extracted from the canonical brief
# (commit c06bd25). Any drift here is tampering with pre-registered materials.
FROZEN_SHA256 = {
    "sentinel/dsl.py":
        "20f9251fb5f02ef2755ab18d7c13544548fbc2a121c8fd5652ddf794f4a40145",
    "prompts/sentinel_compile.md":
        "7d64e3f3f2a8342d2d4a4f4676b69ba6b351eef3819943f974002447b76460ae",
    "prompts/sentinel_judge.md":
        "f5de03051d332ad50bbe7df2afccc9839086a6481ff346f9a5e8e001d44b02a9",
    "prompts/worker.md":
        "c5a7f5dbc959bc65c704fba968aa43a385024644f33703f5ebf916817207c357",
}


def test_frozen_files_unmodified():
    for rel_path, expected in FROZEN_SHA256.items():
        actual = hashlib.sha256((REPO_ROOT / rel_path).read_bytes()).hexdigest()
        assert actual == expected, (
            f"FROZEN file {rel_path} has been modified (sha256 {actual}); "
            "pre-registered materials must not change")


def test_dsl_accepts_valid_set():
    parsed = TripwireSet.model_validate(VALID_TRIPWIRE_SET)
    assert parsed.tripwires[0].severity.value == "CRITICAL"


def test_dsl_rejects_bad_weights():
    bad = {**VALID_TRIPWIRE_SET["tripwires"][0],
           "category_weights": {"API_SURFACE": 0.5}}
    with pytest.raises(ValidationError, match="sum to 1.0"):
        Tripwire.model_validate(bad)


def test_dsl_requires_subplan_for_local_scope():
    bad = {**VALID_TRIPWIRE_SET["tripwires"][0], "scope": "local"}
    with pytest.raises(ValidationError, match="subplan_id"):
        Tripwire.model_validate(bad)


def test_dsl_requires_at_least_one_signal_predicate():
    bad = {**VALID_TRIPWIRE_SET["tripwires"][0],
           "signal": {"type": "http_response", "url_pattern": "/x/*"}}
    with pytest.raises(ValidationError, match="at least one predicate"):
        Tripwire.model_validate(bad)
