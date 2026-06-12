"""Sealed-escrow loader for the Phase 1b matrix launch.

Reads escrow/holdout_escrow.json and escrow/matrix_escrow.json at launch,
verifies each against its PUBLIC SHA-256 custody pin before parsing, and
yields per-cell launch values for programmatic consumption only.

BINDING custody rules (prereg_1b.md §3 build requirement;
decisions/holdout_escrow_record.md + decisions/matrix_escrow_record.md):

- The loader NEVER prints, logs, or stringifies drawn values. SealedCell's
  repr/str expose run identity (task, injection, slot/category) and redact
  everything drawn; this module contains no print or logging call at all.
- Tests NEVER read the real escrow files — synthetic fixtures only
  (tests/test_escrow_loader.py builds its own).
- D23: the six dropped b1 original-injected cells' draws go UNCONSUMED —
  skipped here, never surfaced (deviations.md D23 item 3).
- AUTHOR-3 (prereg_1b ruling): the matrix consumes only the qualified
  holdout pairs; every other superset cell stays sealed in place and is
  never returned.

Design blindness (Rule Zero): the loader carries no knowledge of what any
drawn parameter MEANS. Every cell field outside the fixed identity keys is
treated as an opaque injection-param override and passed verbatim to the
world's injection spec — no category-specific handling anywhere.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent

# Default locations + public custody pins (decisions/*_escrow_record.md).
HOLDOUT_ESCROW_PATH = REPO_ROOT / "escrow" / "holdout_escrow.json"
MATRIX_ESCROW_PATH = REPO_ROOT / "escrow" / "matrix_escrow.json"
HOLDOUT_ESCROW_SHA256 = (
    "df1dcd8bd1cad04f815576cc1d6876807e95bbf25ffc959ada40ff0fa2bb3c88")
MATRIX_ESCROW_SHA256 = (
    "2a9aed0a386df2f0fe5fa2122b2d85114f699eea8d6b2085df786cbeb6204e0e")

# D23 (deviations.md): the b1 original-injected pairs exit the 1b matrix;
# their sealed draws are skipped, unconsumed, without unsealing anything.
D23_SKIPPED_PAIRS = frozenset({("b1", "schema_drift"),
                               ("b1", "gate_skip_trap")})

# prereg_1b AUTHOR-3 ruling: the matrix consumes the qualified primary-host
# holdout pairs only; unqualified superset combinations stay sealed.
CONSUMED_HOLDOUT_PAIRS = frozenset({("a1", "quota_cliff"),
                                    ("b1", "silent_minor_bump")})

_MATRIX_INJECTED_IDENTITY = frozenset({"task", "injection", "slot",
                                       "seed", "n_inject"})
_MATRIX_CLEAN_IDENTITY = frozenset({"task", "slot", "seed"})
_HOLDOUT_IDENTITY = frozenset({"category", "injection", "task",
                               "seed", "n_inject"})


class EscrowIntegrityError(RuntimeError):
    """The escrow file does not match its public custody pin. Loud stop:
    nothing is parsed, nothing launches."""


@dataclass
class SealedCell:
    """One launch cell. Identity is public (it is in the launch manifest by
    shape); every drawn value is sealed behind launch_kwargs() and excluded
    from repr/str so no log line, error message, or debugger default-print
    can leak it."""

    kind: str                       # "matrix-injected" | "matrix-clean" | "holdout"
    task: str
    injection: Optional[str]        # None for clean cells
    slot: Optional[int]             # matrix cells only
    category: Optional[str]         # holdout cells only
    _seed: int = field(repr=False)
    _n_inject: Optional[int] = field(repr=False)
    _params: dict[str, Any] = field(repr=False)

    def __repr__(self) -> str:  # values sealed by construction
        ident = f"{self.task}+{self.injection or 'clean'}"
        if self.slot is not None:
            ident += f"/slot{self.slot}"
        if self.category:
            ident += f" [{self.category}]"
        return f"SealedCell({self.kind}: {ident}, <values sealed>)"

    __str__ = __repr__

    def launch_kwargs(self) -> dict[str, Any]:
        """Programmatic consumption ONLY (the conductor); never serialized
        into logs or manifests."""
        return {"task": self.task, "injection": self.injection,
                "seed": self._seed, "n_inject": self._n_inject,
                "injection_params": dict(self._params) or None}


def _verify_and_parse(path: Path, expected_sha256: str) -> dict:
    raw = Path(path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256:
        # The digests are public custody pins; no drawn value rides this error.
        raise EscrowIntegrityError(
            f"escrow file {Path(path).name} does not match its public "
            f"custody pin (got {digest}, pinned {expected_sha256}); refusing "
            "to launch — verify custody before proceeding")
    return json.loads(raw.decode("utf-8"))


def load_matrix_cells(path: Path = MATRIX_ESCROW_PATH,
                      expected_sha256: str = MATRIX_ESCROW_SHA256,
                      ) -> tuple[list[SealedCell], int]:
    """All consumable matrix cells (injected + clean) and the count of
    sealed draws skipped per D23 (returned for manifest accounting; the
    skipped cells themselves are never surfaced)."""
    payload = _verify_and_parse(path, expected_sha256)
    cells: list[SealedCell] = []
    skipped = 0
    for row in payload["injected_cells"]:
        if (row["task"], row["injection"]) in D23_SKIPPED_PAIRS:
            skipped += 1
            continue
        params = {k: v for k, v in row.items()
                  if k not in _MATRIX_INJECTED_IDENTITY}
        cells.append(SealedCell(kind="matrix-injected", task=row["task"],
                                injection=row["injection"], slot=row["slot"],
                                category=None, _seed=row["seed"],
                                _n_inject=row["n_inject"], _params=params))
    for row in payload["clean_cells"]:
        params = {k: v for k, v in row.items()
                  if k not in _MATRIX_CLEAN_IDENTITY}
        cells.append(SealedCell(kind="matrix-clean", task=row["task"],
                                injection=None, slot=row["slot"],
                                category=None, _seed=row["seed"],
                                _n_inject=None, _params=params))
    return cells, skipped


def load_holdout_cells(path: Path = HOLDOUT_ESCROW_PATH,
                       expected_sha256: str = HOLDOUT_ESCROW_SHA256,
                       ) -> list[SealedCell]:
    """The consumed holdout cells only (AUTHOR-3). Every other superset
    cell stays sealed: not returned, not counted, not named."""
    payload = _verify_and_parse(path, expected_sha256)
    cells: list[SealedCell] = []
    for row in payload["cells"]:
        if (row["task"], row["injection"]) not in CONSUMED_HOLDOUT_PAIRS:
            continue
        params = {k: v for k, v in row.items() if k not in _HOLDOUT_IDENTITY}
        cells.append(SealedCell(kind="holdout", task=row["task"],
                                injection=row["injection"], slot=None,
                                category=row["category"], _seed=row["seed"],
                                _n_inject=row["n_inject"], _params=params))
    return cells
