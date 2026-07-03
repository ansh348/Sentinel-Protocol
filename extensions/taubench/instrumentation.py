"""Instrumentation for the tau-bench fault-injection harness.

Four pieces (see docs/taubench_scoping_memo.md, section 8):
  - TraceWriter    : append-only JSONL episode trace (kept in memory for tests too).
  - CostMeter      : the harness's independent, sole cost authority (Landmine 2).
  - probe(...)     : read-only probe side channel (whitelisted read tools; refuses writes).
  - opening_reading: snapshot (tool, kwargs) observations before the first agent action.

ZERO LLM: nothing here calls a model.
"""
from __future__ import annotations

import json
import os
from typing import List, Optional, Tuple

# Retail read-only tools -- the probe whitelist. Write tools are refused by name.
READ_TOOLS = frozenset({
    "get_user_details", "get_order_details", "get_product_details",
    "list_all_product_types", "calculate", "find_user_id_by_email",
    "find_user_id_by_name_zip", "think",
})
WRITE_TOOLS = frozenset({
    "cancel_pending_order", "exchange_delivered_order_items",
    "modify_pending_order_address", "modify_pending_order_items",
    "modify_pending_order_payment", "modify_user_address",
    "return_delivered_order_items",
})


class TraceWriter:
    """Append-only JSONL trace. Records are kept in memory (for assertions in tests) and,
    when a path is given, each record is also flushed to disk as one JSON line."""

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path
        self.records: List[dict] = []
        if path:
            parent = os.path.dirname(os.path.abspath(path))
            os.makedirs(parent, exist_ok=True)
            open(path, "w", encoding="utf-8").close()

    def write(self, record: dict) -> None:
        self.records.append(record)
        if self.path:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, default=str) + "\n")

    def events(self, name: str) -> List[dict]:
        return [r for r in self.records if r.get("event") == name]


class CostMeter:
    """The tau-bench harness's independent, SOLE cost authority.

    LANDMINE (verified): tau-bench's user simulator tracks cost by ASSIGNMENT, not
    accumulation. In tau_bench/envs/user.py, three user classes -- LLMUserSimulationEnv,
    ReactUserSimulationEnv, and VerifyUserSimulationEnv -- each contain the line

        self.total_cost = res._hidden_params["response_cost"]

    (an assignment, three occurrences). So user.get_total_cost(), surfaced as
    EnvInfo.user_cost on the terminal step, reports only the LAST call's cost, not the
    episode sum. NEVER read tau-bench's cost fields for measurement. This meter reads
    per-call cost/tokens straight off the litellm response instead.

    strict=True (default, for the deterministic test suite): recording an LLM call RAISES,
    enforcing the zero-LLM invariant. strict=False (live runs): records per-call cost and
    token counts for BOTH the agent and the user simulator, split by role. Cost comes from
    res._hidden_params["response_cost"]; tokens from res.usage.{prompt,completion}_tokens.
    """

    _ROLES = ("agent", "user")

    def __init__(self, strict: bool = True) -> None:
        self.strict = strict
        self.n_tool_calls = 0
        self.tool_calls: List[str] = []
        self.calls: List[dict] = []  # per-LLM-call records (role/cost/tokens/model)
        self.n_llm_calls = 0
        self.cost_by_role = {r: 0.0 for r in self._ROLES}
        self.tokens_by_role = {r: {"prompt": 0, "completion": 0} for r in self._ROLES}
        self.max_call_cost = 0.0

    def record_tool_call(self, name: str) -> None:
        self.n_tool_calls += 1
        self.tool_calls.append(name)

    def record_llm_call(self, role: str, cost: float, prompt_tokens: int = 0,
                        completion_tokens: int = 0, model: Optional[str] = None) -> dict:
        if self.strict:
            raise AssertionError(
                "CostMeter is strict (zero-LLM invariant): record_llm_call is not allowed. "
                "Use CostMeter(strict=False) for live runs."
            )
        role = role if role in self._ROLES else "agent"
        cost = float(cost or 0.0)
        rec = {"role": role, "cost": cost, "prompt_tokens": int(prompt_tokens or 0),
               "completion_tokens": int(completion_tokens or 0), "model": model}
        self.calls.append(rec)
        self.n_llm_calls += 1
        self.cost_by_role[role] += cost
        self.tokens_by_role[role]["prompt"] += rec["prompt_tokens"]
        self.tokens_by_role[role]["completion"] += rec["completion_tokens"]
        self.max_call_cost = max(self.max_call_cost, cost)
        return rec

    @property
    def llm_cost(self) -> float:
        return self.cost_by_role["agent"] + self.cost_by_role["user"]

    @property
    def agent_cost(self) -> float:
        return self.cost_by_role["agent"]

    @property
    def user_cost(self) -> float:
        return self.cost_by_role["user"]

    def snapshot(self) -> dict:
        return {
            "n_llm_calls": self.n_llm_calls,
            "agent_cost": round(self.agent_cost, 6),
            "user_cost": round(self.user_cost, 6),
            "llm_cost": round(self.llm_cost, 6),
            "tokens_by_role": {r: dict(t) for r, t in self.tokens_by_role.items()},
        }

    def assert_zero_llm_cost(self) -> None:
        assert self.n_llm_calls == 0 and self.llm_cost == 0.0, (
            f"expected zero LLM spend, got {self.n_llm_calls} calls / {self.llm_cost} cost"
        )


def probe(env, tool_name: str, *, probe_sees_faults: bool = True, **kwargs) -> str:
    """Invoke a whitelisted read-only tool directly against env.data, bypassing the episode
    tool-call counter and (optionally) the armed fault logic.

    probe_sees_faults=True (default): read through the live (possibly faulted) tools_map,
    because a live probe should read the faulted world. False: read through the pristine
    tool. Write tools are refused by name. Logged to env.probe_trace (a separate stream).
    """
    if tool_name in WRITE_TOOLS:
        raise PermissionError(f"probe refuses write tool {tool_name!r}")
    if tool_name not in READ_TOOLS:
        raise PermissionError(f"probe tool {tool_name!r} is not in the read whitelist")
    if probe_sees_faults:
        tool = env.inner.tools_map.get(tool_name) or env._pristine_map[tool_name]
    else:
        tool = env._pristine_map[tool_name]
    obs = tool.invoke(data=env.inner.data, **kwargs)
    env.probe_trace.write({
        "event": "probe", "tool": tool_name, "kwargs": kwargs,
        "probe_sees_faults": probe_sees_faults, "counter": env.counter,
        "armed": env.armed, "observation": obs,
    })
    return obs


def opening_reading(env, reads: List[Tuple[str, dict]]) -> List[dict]:
    """Snapshot a list of (tool, kwargs) observations before the first agent action, using
    the pristine (clean) tools, and store them in the main trace. Write tools are refused."""
    snapshots: List[dict] = []
    for tool_name, kwargs in reads:
        if tool_name in WRITE_TOOLS:
            raise PermissionError(f"opening_reading refuses write tool {tool_name!r}")
        if tool_name not in READ_TOOLS:
            raise PermissionError(f"opening_reading tool {tool_name!r} not in read whitelist")
        obs = env._pristine_map[tool_name].invoke(data=env.inner.data, **kwargs)
        snapshots.append({"tool": tool_name, "kwargs": kwargs, "observation": obs})
    env.trace.write({"event": "opening_reading", "counter": env.counter, "reads": snapshots})
    return snapshots
