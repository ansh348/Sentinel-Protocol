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
              limit: Optional[int] = None) -> dict:
    rev = state.config.world_rev
    if rev < 2:
        return {key: full}
    if rev == 2:
        size = (page_size if page_size is not None
                else state.default_page_size(path))
        return {key: _window(full, page, size), "total_count": len(full)}
    # rev >= 3: the bump renames the pagination parameter
    bumped = (state.bumped_page_size is not None
              and state._in_family(path, state.bump_family))
    explicit = limit if bumped else page_size
    size = explicit if explicit is not None else state.default_page_size(path)
    return {key: _window(full, page, size), TOTAL_COUNT_KEY: len(full)}
