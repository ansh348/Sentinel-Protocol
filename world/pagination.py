"""Rev-gated list/search pagination (benchmark/holdouts/DEPENDENCY_VERSION.md).

Rev 1 — the frozen Phase 1 world: whole collections, original payload
shapes, page params ignored; banked-trace replay is byte-identical.

Rev 2 — FROZEN at the DV spec-rev-1 semantics (the 2026-06-12 rev-1-spec
qualification runs replay against it): total_count in the body, page_size
honored before and after the bump.

Rev 3 — DV spec rev 2 (author ruling 2026-06-12): list bodies carry no
totals or pagination hints; the full collection size travels under the
reserved "_total_count" key, which the world middleware pops into an
X-Total-Count response header (race-free: the value rides the response
itself, never shared state). v1.x honors `page_size` and ignores `limit`;
the v2.0 bump silently renames the parameter — `page_size` ignored,
`limit` honored — and `page` stays functional throughout, which is what
keeps REINTERPRET + REDO recovery always possible by construction.
FROZEN at these semantics (the spec-rev-2 re-qualification runs replay
against it).

Rev 4 — DV spec rev 3 (author ruling #2, 2026-06-12): the rename target
hardens `limit` -> `page_limit`, closing the habit-typed-parameter escape
(re-qualification s906: a worker spontaneously sent `limit=200`).
Post-bump the family honors only `page_limit`; `page_size` AND `limit`
are silently ignored. Pre-bump v1.x behavior is unchanged (page_size
honored; page_limit/limit ignored). The manifest documents the new
parameter, so REINTERPRET stays one call.
"""
from __future__ import annotations

from typing import Optional

from world.state import MAX_PAGE_SIZE, WorldState

# Popped by the middleware into the X-Total-Count header; never serialized
# into a worker-visible body.
TOTAL_COUNT_KEY = "_total_count"


def _window(full: list, page: Optional[int], size: int) -> list:
    size = max(1, min(int(size), MAX_PAGE_SIZE))
    current = max(1, int(page if page is not None else 1))
    return full[(current - 1) * size: current * size]


def paginated(state: WorldState, path: str, key: str, full: list,
              page: Optional[int], page_size: Optional[int],
              limit: Optional[int] = None,
              page_limit: Optional[int] = None) -> dict:
    rev = state.config.world_rev
    if rev < 2:
        return {key: full}
    if rev == 2:
        size = (page_size if page_size is not None
                else state.default_page_size(path))
        return {key: _window(full, page, size), "total_count": len(full)}
    # rev >= 3: the bump renames the pagination parameter; the rename
    # target is rev-dependent (rev 3: limit — frozen; rev >= 4: page_limit)
    bumped = (state.bumped_page_size is not None
              and state._in_family(path, state.bump_family))
    if bumped:
        explicit = page_limit if rev >= 4 else limit
    else:
        explicit = page_size  # v1.x: the renamed params are unknown -> ignored
    size = explicit if explicit is not None else state.default_page_size(path)
    return {key: _window(full, page, size), TOTAL_COUNT_KEY: len(full)}
