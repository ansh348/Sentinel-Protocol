"""Declarative fault primitives for the tau-bench fault-injection harness.

A fault is a controlled edit to the injection seam
    Env.step(action) -> tools_map[action.name].invoke(data=self.data, **action.kwargs)
(see docs/taubench_scoping_memo.md). Four primitives:

  read_transform  -- proxy a named tool; transform its returned observation string.
                     NEVER touches env.data.
  surface_removal -- remove a named tool from tools_map AND its schema from tools_info,
                     so the capability disappears from the agent's view, not just dispatch.
  error_injection -- a named tool returns a configured error string instead of executing.
  list_truncation -- a read_transform specialization: truncate list-valued fields in an
                     observation to their first element(s).

A fault fires when the tool-call counter reaches `trigger_n` (NO default baked in) and is
sticky for the rest of the episode. Every FaultConfig is JSON-serializable.

ZERO LLM: nothing here calls a model. Faults only rewrite tools_map / tools_info.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Callable, List, Optional

READ_TRANSFORM = "read_transform"
SURFACE_REMOVAL = "surface_removal"
ERROR_INJECTION = "error_injection"
LIST_TRUNCATION = "list_truncation"

FAULT_KINDS = frozenset({READ_TRANSFORM, SURFACE_REMOVAL, ERROR_INJECTION, LIST_TRUNCATION})


def _proxy_tool(orig: Any, invoke_fn: Callable[[Any, Any, dict], str]):
    """Build a duck-typed tool class (static invoke/get_info) that replaces `orig` in
    tools_map. Dispatch only needs the two static methods, so it need not subclass Tool,
    but it mirrors the tau-bench Tool contract exactly. `get_info` is inherited from the
    original for read_transform/error_injection/list_truncation (schema unchanged)."""

    class _Proxy:
        __wrapped_tool__ = orig

        @staticmethod
        def invoke(data=None, **kwargs) -> str:
            return invoke_fn(orig, data, kwargs)

        @staticmethod
        def get_info() -> dict:
            return orig.get_info()

    _Proxy.__name__ = f"Faulted_{getattr(orig, '__name__', 'tool')}"
    _Proxy.__qualname__ = _Proxy.__name__
    return _Proxy


def _string_swap_invoke(find: str, replace: str) -> Callable[[Any, Any, dict], str]:
    def _inv(orig: Any, data: Any, kwargs: dict) -> str:
        obs = orig.invoke(data=data, **kwargs)
        return obs.replace(find, replace) if isinstance(obs, str) else obs
    return _inv


def _truncate_lists(obs: str, fields: Optional[List[str]], keep: int) -> str:
    """Truncate list-valued fields of a JSON observation to their first `keep` elements.
    If `fields` is None, truncate every top-level list-valued field (and a bare top-level
    list). Non-JSON observations are returned unchanged (observations are JSON strings)."""
    try:
        parsed = json.loads(obs)
    except (json.JSONDecodeError, TypeError, ValueError):
        return obs
    if isinstance(parsed, dict):
        targets = fields if fields is not None else [
            k for k, v in parsed.items() if isinstance(v, list)
        ]
        for k in targets:
            v = parsed.get(k)
            if isinstance(v, list):
                parsed[k] = v[:keep]
    elif isinstance(parsed, list) and fields is None:
        parsed = parsed[:keep]
    return json.dumps(parsed)


def _truncate_invoke(fields: Optional[List[str]], keep: int) -> Callable[[Any, Any, dict], str]:
    def _inv(orig: Any, data: Any, kwargs: dict) -> str:
        obs = orig.invoke(data=data, **kwargs)
        return _truncate_lists(obs, fields, keep) if isinstance(obs, str) else obs
    return _inv


def _error_invoke(message: str) -> Callable[[Any, Any, dict], str]:
    def _inv(orig: Any, data: Any, kwargs: dict) -> str:
        return message
    return _inv


@dataclass
class FaultConfig:
    """One declarative fault. JSON-serializable. `trigger_n` has no default (STEP 2)."""

    id: str
    kind: str
    target_tool: str
    trigger_n: int  # fires when the tool-call counter REACHES this value; NO DEFAULT
    # kind-specific parameters (validated per-kind in __post_init__):
    error_message: Optional[str] = None          # error_injection
    find: Optional[str] = None                    # read_transform (substring find/replace)
    replace: Optional[str] = None                 # read_transform
    truncate_fields: Optional[List[str]] = None   # list_truncation (None => all list fields)
    keep: int = 1                                 # list_truncation (first N elements)
    note: str = ""

    def __post_init__(self) -> None:
        if self.kind not in FAULT_KINDS:
            raise ValueError(f"unknown fault kind: {self.kind!r} (want one of {sorted(FAULT_KINDS)})")
        if not isinstance(self.trigger_n, int) or self.trigger_n < 1:
            raise ValueError(f"trigger_n must be a positive int (fire-on-reach); got {self.trigger_n!r}")
        if self.kind == ERROR_INJECTION and not self.error_message:
            raise ValueError(f"fault {self.id}: error_injection requires error_message")
        if self.kind == READ_TRANSFORM and (self.find is None or self.replace is None):
            raise ValueError(f"fault {self.id}: read_transform requires find and replace")
        if self.kind == LIST_TRUNCATION and (not isinstance(self.keep, int) or self.keep < 0):
            raise ValueError(f"fault {self.id}: list_truncation keep must be a non-negative int")

    # ---- serialization ----
    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, d: dict) -> "FaultConfig":
        return cls(**{k: v for k, v in d.items() if not k.startswith("_")})

    @classmethod
    def from_json_file(cls, path: str) -> "FaultConfig":
        with open(path, "r", encoding="utf-8") as fh:
            return cls.from_dict(json.load(fh))

    # ---- behavior ----
    @property
    def is_read_type(self) -> bool:
        """True for data-neutral read faults (safe to re-invoke the pristine tool for the
        'pre-transform' trace field)."""
        return self.kind in (READ_TRANSFORM, LIST_TRUNCATION)

    def build_proxy(self, orig: Any):
        """Return the replacement tool class for tools_map (None for surface_removal)."""
        if self.kind == SURFACE_REMOVAL:
            return None
        if self.kind == READ_TRANSFORM:
            return _proxy_tool(orig, _string_swap_invoke(self.find, self.replace))
        if self.kind == LIST_TRUNCATION:
            return _proxy_tool(orig, _truncate_invoke(self.truncate_fields, self.keep))
        if self.kind == ERROR_INJECTION:
            return _proxy_tool(orig, _error_invoke(self.error_message))
        raise AssertionError(self.kind)  # unreachable (validated in __post_init__)

    def apply(self, tools_map: dict, tools_info: list, pristine_map: dict) -> None:
        """Arm this fault by mutating tools_map / tools_info in place. Always rebuilds from
        the PRISTINE tool, so (re-)application from any state is stable."""
        name = self.target_tool
        if name not in pristine_map:
            raise KeyError(f"fault {self.id}: unknown target tool {name!r}")
        if self.kind == SURFACE_REMOVAL:
            tools_map.pop(name, None)
            tools_info[:] = [
                s for s in tools_info if s.get("function", {}).get("name") != name
            ]
        else:
            tools_map[name] = self.build_proxy(pristine_map[name])
            # schema is unchanged for read_transform / error_injection / list_truncation
