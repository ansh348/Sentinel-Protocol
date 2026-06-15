"""D31 write-surface footprint policy (deviations.md D31; probe_compiler_design §3.2).

A surface a worker is planned to WRITE legitimately changes — a frozen arm-time
baseline would fire on the plan's own intended work (the b1+clean false positive).
The old policy left the whole surface PASSIVE (silently un-monitored). D31 replaces
that with FOOTPRINT scoping:

  - OFF-FOOTPRINT (everything outside the declared mutation region) is monitored
    against the D30 arm-time baseline exactly like any other surface -> a change
    there is DRIFT.
  - IN-FOOTPRINT: where the plan declares the expected transition precisely enough
    to verify (a checkable expected post-state), verify it -> a deviation is DRIFT;
    otherwise route to UNCOVERED_CAUTION (loud, scored by C7), NEVER silent-passive
    and NEVER a raw re-baseline.

The primary predicate for a write surface is "consistent with the authorized
footprint transition"; D28 persistence is secondary and runs only after this — a
legitimate permanent write never self-corroborates as drift.

C0 (analysis/d31_corpus_check.py) established the seen corpus is single-epoch, so a
footprint is a flat region here; the ordered write-epoch sequence and the
cross-worker committed-epoch read are named residuals (D31 item 5), as is the
precise extraction of an expected post-state from the plan (item 3 residual) — a
whole-surface footprint with no expected post-state is the honest minimum and routes
to UNCOVERED_CAUTION.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from world.server import _MISSING, _pointer_lookup


class FootprintVerdict(str, Enum):
    CLEAN = "clean"                         # consistent with the authorized footprint
    DRIFT = "drift"                         # off-footprint change OR in-footprint deviation
    UNCOVERED_CAUTION = "uncovered_caution"  # in-footprint, not precisely verifiable


@dataclass(frozen=True)
class WriteFootprint:
    """The region a planned write is authorized to mutate. `fields` empty => the
    whole surface is the footprint (a PUT rewrites the file); `expected` None => the
    transition is not precisely specifiable from the plan (the item-3 residual)."""
    surface: str
    fields: tuple = ()
    expected: Optional[dict] = None         # {pointer: expected post-value}


@dataclass(frozen=True)
class FootprintEvaluation:
    verdict: FootprintVerdict
    reason: str
    witness: Any = None


def _body(obs) -> Any:
    return obs.body if hasattr(obs, "body") else obs


def _flatten(node: Any, prefix: str = "") -> dict:
    out: dict = {}
    if isinstance(node, dict):
        for k, v in node.items():
            out.update(_flatten(v, f"{prefix}{k}."))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            out.update(_flatten(v, f"{prefix}{i}."))
    else:
        out[prefix.rstrip(".")] = node
    return out


def _in_footprint(path: str, fields) -> bool:
    return any(path == f or path.startswith(f + ".") for f in fields)


def evaluate_write_footprint(fp: WriteFootprint, baseline, observation
                             ) -> FootprintEvaluation:
    """The D31 write-surface primary predicate. Off-footprint drift and in-footprint
    deviation are DRIFT (interrupt-grade); an unverifiable footprint is
    UNCOVERED_CAUTION (loud); a verified transition is CLEAN."""
    obs = _body(observation)
    # off-footprint: everything outside the footprint must match the arm-time baseline
    if fp.fields and baseline is not None:
        base = _flatten(_body(baseline))
        cur = _flatten(obs)
        b_off = {k: v for k, v in base.items() if not _in_footprint(k, fp.fields)}
        c_off = {k: v for k, v in cur.items() if not _in_footprint(k, fp.fields)}
        if b_off != c_off:
            changed = sorted({k for k in set(b_off) | set(c_off)
                              if b_off.get(k) != c_off.get(k)})
            return FootprintEvaluation(
                FootprintVerdict.DRIFT,
                "off-footprint change on a write surface (outside the authorized "
                "footprint)", witness=changed[:5])
    # in-footprint: verify against the authorized transition if specifiable
    if fp.expected is not None:
        for ptr, want in fp.expected.items():
            got = _pointer_lookup(obs, ptr)
            if got is _MISSING or got != want:
                shown = "MISSING" if got is _MISSING else repr(got)
                return FootprintEvaluation(
                    FootprintVerdict.DRIFT,
                    f"footprint field {ptr} deviates from the authorized transition "
                    f"(expected {want!r}, got {shown})", witness=ptr)
        return FootprintEvaluation(
            FootprintVerdict.CLEAN,
            "footprint transition matches the authorized post-state")
    # not precisely verifiable -> loud, scored by C7, never silently clean
    return FootprintEvaluation(
        FootprintVerdict.UNCOVERED_CAUTION,
        "write footprint not precisely verifiable (no checkable expected post-state); "
        "certified for the footprint and invariants, uncertified inside it (D31 item 3)")
