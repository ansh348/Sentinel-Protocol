"""M6 amendment 2: completeness comes from the committed manifest, never
inferred from existing runs; gates.py refuses on an incomplete matrix."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from analysis.gates import (cell_run_dir, check_complete, generate_manifest,
                            kill_gate_table)


def test_manifest_covers_every_planned_cell():
    cells = generate_manifest()
    # 4 tasks x (1 clean + their injections: 3+2+2+2=9) = 13 variants,
    # x 5 systems x 3 seeds
    assert len(cells) == 13 * 5 * 3
    keys = {(c["task"], c["system"], c["injection"], c["seed"]) for c in cells}
    assert len(keys) == len(cells), "cells must be unique"
    assert ("a1", "S5", "endpoint_404", 1) in keys
    assert ("d1", "S3", None, 3) in keys


def test_gates_refuse_on_incomplete_matrix(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps([
        {"task": "a1", "system": "S1", "injection": "endpoint_404", "seed": 1},
        {"task": "a1", "system": "S5", "injection": "endpoint_404", "seed": 1},
    ]), encoding="utf-8")
    runs_root = tmp_path / "runs"
    done = runs_root / "a1-S1-endpoint_404-s1"
    done.mkdir(parents=True)
    (done / "trace.jsonl").write_text("", encoding="utf-8")

    found, missing = check_complete(runs_root, manifest)
    assert len(found) == 1 and len(missing) == 1
    assert missing[0][0]["system"] == "S5"
    with pytest.raises(SystemExit, match="REFUSING.*incomplete"):
        kill_gate_table(runs_root, manifest)


def test_gates_refuse_without_manifest(tmp_path):
    with pytest.raises(SystemExit, match="no committed matrix manifest"):
        check_complete(tmp_path, tmp_path / "absent.json")


def test_cell_run_dir_prefers_latest_suffix(tmp_path):
    cell = {"task": "a1", "system": "S5", "injection": "endpoint_404", "seed": 1}
    for name in ("a1-S5-endpoint_404-s1", "a1-S5-endpoint_404-s1-2"):
        d = tmp_path / name
        d.mkdir()
        (d / "trace.jsonl").write_text("", encoding="utf-8")
    assert cell_run_dir(tmp_path, cell).name == "a1-S5-endpoint_404-s1-2"
