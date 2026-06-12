"""Rev-2 list/search pagination (DEPENDENCY_VERSION.md Sections 1 and 5).

Rev-1 worlds return whole collections under the original payload shape,
byte-identical to Phase 1 — explicit page params are ignored there and the
total_count envelope is never added, so banked-trace replay is untouched.

Rev-2 worlds always carry total_count (the full collection size) next to the
list key; the effective default page size is the 1.x constant (100) until
silent_minor_bump flips the designated family, after which page one silently
carries a strict subset. Explicit pagination is honored at all times (capped
at MAX_PAGE_SIZE), which is what makes REINTERPRET + REDO recovery always
possible by construction.
"""
from __future__ import annotations

from typing import Optional

from world.state import MAX_PAGE_SIZE, WorldState


def paginated(state: WorldState, path: str, key: str, full: list,
              page: Optional[int], page_size: Optional[int]) -> dict:
    if state.config.world_rev < 2:
        return {key: full}
    size = page_size if page_size is not None else state.default_page_size(path)
    size = max(1, min(int(size), MAX_PAGE_SIZE))
    current = max(1, int(page if page is not None else 1))
    window = full[(current - 1) * size: current * size]
    return {key: window, "total_count": len(full)}
