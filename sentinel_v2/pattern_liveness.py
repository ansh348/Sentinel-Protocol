"""Compile-time pattern-liveness sweep — the #7-class instrument fix.

Provenance: archaeology_v2.md §A.3/G2 (the dead-pattern CLASS: 84 armed
url_patterns that could never match any world path under the live dialect,
61 host-qualified, 19 on covering tripwires, across 8 cells — the
a1+token_expiry/s1 miss is the one place the class changed an outcome);
sentinel_protocol_v6_1.md §11.9 amendment #7 ("every compiled pattern must
demonstrably match its own surface's canonical traffic before arming");
decision memo §5(d)-(e) (instrument-class, regression-evidenced,
deviation-logged — deviations.md D24); prereg_1b.md §3 build requirement
(D13 pattern-liveness samples become rev-aware).

The sweep is deterministic and zero-LLM: classification reuses the D5
arm-time classifier verbatim (world.server.classify_url_pattern) against
rev-aware D13 path samples. A dead pattern fails compilation LOUDLY — the
whole set is rejected with every dead pattern listed, never a silent drop.
"""
from __future__ import annotations

import functools
from typing import Iterable, Optional

from world.server import classify_url_pattern, get_path_samples


@functools.lru_cache(maxsize=16)
def path_samples_for_rev(world_rev: int, n_regions: Optional[int] = None) -> tuple[str, ...]:
    """D13 samples, rev-aware (D24). Rev 1 returns world.server's derived
    sample VERBATIM (byte-identical Phase 1 behavior — the banked-replay
    foundation). Rev >= 2 derives the same way from a rev-N world's own
    OpenAPI spec and fixture collections, mechanically and with no
    hand-listing: routes from the spec, parameterized segments instantiated
    from the fixture keys they range over."""
    if world_rev <= 1:
        return get_path_samples()

    import os
    import tempfile

    from world.server import create_app
    from world.state import PASSAGES, REPO_FILES_V2, SKUS, RunConfig

    fd, trace_path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    # n_regions (additive, default None = byte-identical): when set, the sample-app
    # builds N region shards and the {region_id} family is instantiated from them, so the
    # benchmark_1c /regions surfaces become VISIBLE to grounding. None -> the regions
    # router is not registered and the {region_id} branch is dormant, so the derived
    # sample set is byte-identical for every existing task (visibility-only).
    app = create_app(RunConfig(run_id="liveness-samples", seed=0,
                               system="surface", task_id="surface",
                               trace_path=trace_path, world_rev=world_rev,
                               n_regions=n_regions))
    spec_paths = app.openapi()["paths"]
    region_ids = list(getattr(app.state.ctx.state, "region_order", []))
    app.state.ctx.trace.close()
    try:
        os.unlink(trace_path)
    except OSError:
        pass

    samples: set[str] = set()
    for path in spec_paths:
        if "{" not in path:
            samples.add(path)
            continue
        if "{sku}" in path:
            samples.update(path.replace("{sku}", sku) for sku in SKUS)
        if "{passage_id}" in path:
            samples.update(path.replace("{passage_id}", p["id"])
                           for p in PASSAGES)
        if "{path}" in path:
            samples.update(path.replace("{path}", f) for f in REPO_FILES_V2)
        if "{region_id}" in path:        # benchmark_1c width-scaled family (dormant unless n_regions)
            samples.update(path.replace("{region_id}", rid) for rid in region_ids)
    return tuple(sorted(samples))


def liveness_report(patterns: Iterable[tuple[str, str]], *,
                    world_rev: int = 1,
                    samples: Optional[tuple[str, ...]] = None) -> list[dict]:
    """Classify every (owner_id, url_pattern) pair against the rev's canonical
    samples. mode is 'glob' / 'regex' / 'dead' — identical semantics to the D5
    arm-time record, so the sweep and the matcher can never disagree."""
    if samples is None:
        samples = path_samples_for_rev(world_rev)
    return [{"id": owner, "pattern": pattern,
             "mode": classify_url_pattern(pattern, samples) or "dead"}
            for owner, pattern in patterns]


class DeadPatternError(ValueError):
    """Raised at compile time when any pattern in a set is dead. Carries the
    complete dead list (class fix, not singleton: one loud failure names
    every defect)."""

    def __init__(self, dead: list[dict], world_rev: int) -> None:
        self.dead = dead
        lines = "\n".join(f"  - {d['id']}: {d['pattern']!r}" for d in dead)
        super().__init__(
            f"pattern-liveness sweep FAILED (world_rev {world_rev}): "
            f"{len(dead)} compiled url_pattern(s) can never match any world "
            f"path under the live dialect (D5) and must not arm:\n{lines}")


def assert_patterns_live(tripwire_set, *, world_rev: int = 1) -> list[dict]:
    """The compile-time gate (v6.1 §11.9 amendment #7): every compiled
    url_pattern must be demonstrably live against the rev's canonical
    traffic BEFORE arming. Returns the full liveness report on success;
    raises DeadPatternError listing every dead pattern otherwise."""
    pairs = [(tw.id, tw.signal.url_pattern) for tw in tripwire_set.tripwires
             if tw.signal.url_pattern]
    report = liveness_report(pairs, world_rev=world_rev)
    dead = [r for r in report if r["mode"] == "dead"]
    if dead:
        raise DeadPatternError(dead, world_rev)
    return report
