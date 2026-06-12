"""N3 acceptance: the sealed-escrow loader.

Tested ONLY against synthetic fixtures with fake values (standing rule: the
real escrow/*.json are NEVER read by tests). Verifies: hash gate, D23
skip-list, AUTHOR-3 consumption filter, generic param extraction, and the
no-leak guarantee (no drawn value reaches stdout, logging, repr, or str).
"""
from __future__ import annotations

import hashlib
import json
import logging

import pytest

from conductor.escrow_loader import (CONSUMED_HOLDOUT_PAIRS, D23_SKIPPED_PAIRS,
                                     EscrowIntegrityError, load_holdout_cells,
                                     load_matrix_cells)

# Distinctive fake values that must never leak into any output stream.
FAKE_SEED_BASE = 86420
FAKE_N_BASE = 39
FAKE_OPAQUE = 2357  # a drawn parameter the loader must treat as opaque

PAIRS = (("a1", "endpoint_404"), ("a1", "schema_drift"), ("a1", "token_expiry"),
         ("b1", "schema_drift"), ("b1", "gate_skip_trap"),
         ("c1", "doc_contradiction"), ("c1", "token_expiry"),
         ("d1", "gate_skip_trap"), ("d1", "endpoint_404"))


def _write(path, payload) -> str:
    raw = json.dumps(payload, indent=1, sort_keys=True).encode("utf-8")
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


@pytest.fixture
def matrix_fixture(tmp_path):
    i = 0
    injected = []
    for task, injection in PAIRS:
        for slot in (1, 2, 3):
            injected.append({"task": task, "injection": injection,
                             "slot": slot, "seed": FAKE_SEED_BASE + i,
                             "n_inject": FAKE_N_BASE + i})
            i += 1
    clean = [{"task": t, "slot": s, "seed": FAKE_SEED_BASE + 500 + j}
             for j, (t, s) in enumerate((t, s) for t in ("a1", "b1", "c1", "d1")
                                        for s in (1, 2, 3))]
    path = tmp_path / "matrix_fake.json"
    digest = _write(path, {"drawn": "test", "injected_cells": injected,
                           "clean_cells": clean})
    return path, digest


@pytest.fixture
def holdout_fixture(tmp_path):
    cells = []
    i = 0
    for task in ("a1", "b1", "c1", "d1"):
        for cat, inj in (("CAT_A", "quota_cliff"), ("CAT_B", "silent_minor_bump")):
            for _ in range(5):
                cells.append({"category": cat, "injection": inj, "task": task,
                              "seed": FAKE_SEED_BASE + 1000 + i,
                              "n_inject": FAKE_N_BASE + i,
                              "opaque_param": FAKE_OPAQUE + i,
                              "family": [f"/svc{i % 3}"]})
                i += 1
    path = tmp_path / "holdout_fake.json"
    digest = _write(path, {"drawn": "test", "cells": cells})
    return path, digest


def test_hash_gate_accepts_pinned_file(matrix_fixture):
    path, digest = matrix_fixture
    cells, skipped = load_matrix_cells(path, digest)
    assert cells and skipped == 6


def test_hash_gate_refuses_tampered_file(matrix_fixture):
    path, digest = matrix_fixture
    raw = path.read_bytes().replace(str(FAKE_SEED_BASE).encode(), b"11111")
    path.write_bytes(raw)
    with pytest.raises(EscrowIntegrityError, match="custody pin"):
        load_matrix_cells(path, digest)


def test_d23_skip_list_honored(matrix_fixture):
    path, digest = matrix_fixture
    cells, skipped = load_matrix_cells(path, digest)
    assert skipped == 6  # 2 pairs x 3 slots, unconsumed
    surfaced = {(c.task, c.injection) for c in cells if c.injection}
    assert surfaced.isdisjoint(D23_SKIPPED_PAIRS)
    assert len([c for c in cells if c.kind == "matrix-injected"]) == 21
    assert len([c for c in cells if c.kind == "matrix-clean"]) == 12


def test_holdout_consumption_filter(holdout_fixture):
    path, digest = holdout_fixture
    cells = load_holdout_cells(path, digest)
    assert len(cells) == 10  # 2 qualified pairs x 5 seeds; 30 stay sealed
    assert {(c.task, c.injection) for c in cells} == set(CONSUMED_HOLDOUT_PAIRS)


def test_generic_param_extraction(holdout_fixture):
    path, digest = holdout_fixture
    cell = load_holdout_cells(path, digest)[0]
    kwargs = cell.launch_kwargs()
    assert set(kwargs) == {"task", "injection", "seed", "n_inject",
                           "injection_params"}
    # non-identity fields pass through verbatim and opaquely
    assert "opaque_param" in kwargs["injection_params"]
    assert "family" in kwargs["injection_params"]
    assert "category" not in kwargs["injection_params"]


def test_no_value_leaks_to_any_stream(matrix_fixture, holdout_fixture,
                                      capsys, caplog):
    mpath, mdigest = matrix_fixture
    hpath, hdigest = holdout_fixture
    with caplog.at_level(logging.DEBUG):
        mcells, _ = load_matrix_cells(mpath, mdigest)
        hcells = load_holdout_cells(hpath, hdigest)
    rendered = (capsys.readouterr().out + capsys.readouterr().err
                + caplog.text
                + " ".join(repr(c) for c in mcells + hcells)
                + " ".join(str(c) for c in mcells + hcells))
    leaked = [v for v in range(FAKE_SEED_BASE, FAKE_SEED_BASE + 1100)
              if str(v) in rendered]
    leaked += [v for v in range(FAKE_OPAQUE, FAKE_OPAQUE + 50)
               if str(v) in rendered]
    assert not leaked, f"drawn values leaked: {leaked[:5]}"
    assert "<values sealed>" in repr(mcells[0])


def test_loader_module_contains_no_print_or_logging():
    import inspect

    import conductor.escrow_loader as mod
    src = inspect.getsource(mod)
    assert "print(" not in src
    assert "import logging" not in src
    assert "logging." not in src


def test_tampered_error_message_carries_no_values(matrix_fixture):
    path, digest = matrix_fixture
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(EscrowIntegrityError) as err:
        load_matrix_cells(path, digest)
    assert str(FAKE_SEED_BASE) not in str(err.value)


def test_conductor_injection_params_override(tmp_path):
    """The loader's apply path: per-cell params merge over the task yaml's
    defaults; the world_config.json the world consumes carries the merge."""
    from conductor.run_one import Conductor
    c = Conductor(task_path="tasks/a1.yaml", system_id="S1",
                  injection="endpoint_404", n_inject=3, seed=1,
                  runs_root=tmp_path,
                  injection_params={"path": "/inventory/items"})
    try:
        c.start_world()
        cfg = json.loads((c.run_dir / "world_config.json")
                         .read_text(encoding="utf-8"))
        assert cfg["injection"]["params"]["path"] == "/inventory/items"
        assert cfg["n_inject"] == 3
    finally:
        if c.world_proc:
            c.world_proc.kill()
        c.trace.close()


def test_conductor_without_override_is_unchanged(tmp_path):
    from conductor.run_one import Conductor
    c = Conductor(task_path="tasks/a1.yaml", system_id="S1",
                  injection="endpoint_404", n_inject=3, seed=1,
                  runs_root=tmp_path)
    try:
        c.start_world()
        cfg = json.loads((c.run_dir / "world_config.json")
                         .read_text(encoding="utf-8"))
        # the yaml default, byte-identical to every pre-1b run
        assert cfg["injection"]["params"]["path"] == "/pricing/quote/*"
    finally:
        if c.world_proc:
            c.world_proc.kill()
        c.trace.close()
