"""FaultedEnv: a composition wrapper around tau-bench's MockRetailDomainEnv that arms
declarative faults at the tool-dispatch seam and GUARANTEES the reward oracle runs clean.

See docs/taubench_scoping_memo.md. The load-bearing invariant (Landmine 1):

    ARMED is set at episode start and is GUARANTEED cleared before any calculate_reward
    execution; reward-replay steps are structurally incapable of passing through fault logic.

Mechanism:
  * Faults are applied ONLY inside FaultedEnv.step(). The inner env's reward oracle replays
    ground-truth actions through the INNER env's own step (base Env.step), which this wrapper
    does not shadow -- so fault-arming code is never on the oracle path.
  * The only residual leak is the persistent tools_map/tools_info mutation. The wrapper
    wraps the inner env's bound calculate_reward so that EVERY caller (including tau-bench's
    own step() on done=True) first disarms -- restores pristine tools_map/tools_info and
    clears `armed` -- then asserts the pristine state before delegating.

ZERO LLM: the inner env is built with a non-LLM user strategy and its user is replaced with
NullUser; no model call is ever made.
"""
from __future__ import annotations

import time
from typing import List, Optional, Tuple

from extensions.taubench.faults import FaultConfig
from extensions.taubench.instrumentation import (
    READ_TOOLS,
    CostMeter,
    TraceWriter,
    opening_reading,
    probe,
)
from extensions.taubench.nulluser import NullUser

RESPOND = "respond"


def _probe_path(trace_path: Optional[str]) -> Optional[str]:
    if not trace_path:
        return None
    if trace_path.endswith(".jsonl"):
        return trace_path[: -len(".jsonl")] + ".probe.jsonl"
    return trace_path + ".probe.jsonl"


class FaultedEnv:
    """Composition wrapper; the underlying MockRetailDomainEnv is left structurally
    unmodified (we only mutate its tools_map/tools_info/user and wrap its bound
    calculate_reward on the instance)."""

    def __init__(
        self,
        faults: Optional[List[FaultConfig]] = None,
        *,
        task_index: int = 0,
        task_split: str = "test",
        trace_path: Optional[str] = None,
        probe_sees_faults: bool = True,
    ) -> None:
        # Import here so the module is importable without tau_bench and so the litellm
        # guard in conftest is installed before tau_bench.envs.user is imported.
        from tau_bench.envs.retail.env import MockRetailDomainEnv

        # user_strategy="human" builds a HumanUserSimulationEnv with NO model call at
        # construction (the LLM strategy calls completion() in __init__). We then swap in
        # NullUser so reset()/step() never call input() or a model.
        self.inner = MockRetailDomainEnv(
            user_strategy="human", task_index=task_index, task_split=task_split
        )
        self.inner.user = NullUser()

        self.faults: List[FaultConfig] = list(faults or [])
        self.probe_sees_faults = probe_sees_faults

        # Pristine snapshots for restore / oracle safety.
        self._pristine_map = dict(self.inner.tools_map)
        self._pristine_info = [dict(s) for s in self.inner.tools_info]

        self.counter = 0
        self.armed = False
        self._fired: set = set()
        self._in_reward = False
        self._t0: Optional[float] = None

        self.cost_meter = CostMeter()
        self.trace = TraceWriter(trace_path)
        self.probe_trace = TraceWriter(_probe_path(trace_path))

        # Wrap the inner env's bound calculate_reward. Base Env.step() calls
        # self.calculate_reward() on done=True; assigning an instance attribute shadows the
        # class method, so that path also disarms. _orig_calculate_reward keeps the raw
        # base method for the self-tests that reproduce the landmine.
        self._orig_calculate_reward = self.inner.calculate_reward
        self.inner.calculate_reward = self._guarded_calculate_reward

    # ------------------------------------------------------------------ lifecycle
    def reset(self, task_index: Optional[int] = None) -> str:
        idx = self.inner.task_index if task_index is None else task_index
        self.inner.reset(idx)  # reload clean data + set task (NullUser.reset, no model)
        self.inner.tools_map = dict(self._pristine_map)
        self.inner.tools_info = [dict(s) for s in self._pristine_info]
        self.counter = 0
        self.armed = True
        self._fired = set()
        self._t0 = time.monotonic()
        h = self.inner.get_data_hash()
        self.trace.write({
            "event": "reset", "task_index": idx, "data_hash": h, "armed": self.armed,
        })
        return h

    # -------------------------------------------------------------- fault firing
    def _maybe_fire(self) -> List[str]:
        fired_now: List[str] = []
        for f in self.faults:
            if f.id not in self._fired and self.counter >= f.trigger_n:
                f.apply(self.inner.tools_map, self.inner.tools_info, self._pristine_map)
                self._fired.add(f.id)
                fired_now.append(f.id)
                self.trace.write({
                    "event": "fault_fire", "fault": f.id, "kind": f.kind,
                    "target": f.target_tool, "counter": self.counter,
                    "trigger_n": f.trigger_n,
                })
        return fired_now

    def _active_read_fault(self, tool_name: str) -> Optional[FaultConfig]:
        for f in self.faults:
            if f.id in self._fired and f.target_tool == tool_name and f.is_read_type:
                return f
        return None

    # ---------------------------------------------------------------------- step
    def step(self, action):
        is_tool = action.name != RESPOND
        fired_now: List[str] = []
        if is_tool:
            self.counter += 1
            self.cost_meter.record_tool_call(action.name)
            fired_now = self._maybe_fire()  # sticky: fires when counter REACHES trigger_n

        resp = self.inner.step(action)  # dispatches through (possibly faulted) tools_map
        post_obs = resp.observation

        # The "pre-transform" observation is meaningful only for data-neutral read faults on
        # read-only tools; re-invoking a write tool for logging would double-apply it.
        read_fault = self._active_read_fault(action.name) if is_tool else None
        if read_fault is not None and action.name in READ_TOOLS:
            try:
                pre_obs = self._pristine_map[action.name].invoke(
                    data=self.inner.data, **action.kwargs
                )
            except Exception as exc:  # pragma: no cover - defensive
                pre_obs = f"<pre-invoke error: {exc}>"
        else:
            pre_obs = post_obs

        self.trace.write({
            "event": "action", "name": action.name, "kwargs": action.kwargs,
            "counter": self.counter, "armed": self.armed,
            "pre_obs": pre_obs, "post_obs": post_obs, "faults_fired": fired_now,
            "data_hash": self.inner.get_data_hash(),
            "wall_ms": self._wall_ms(),
        })
        return resp

    # ------------------------------------------------------------ disarm / reward
    def _disarm(self, reason: str = "") -> None:
        self.inner.tools_map = dict(self._pristine_map)
        self.inner.tools_info = [dict(s) for s in self._pristine_info]
        self.armed = False
        self._fired = set()
        self.trace.write({"event": "disarm", "reason": reason, "armed": self.armed})

    def _guarded_calculate_reward(self):
        # STRUCTURAL invariant (Landmine 1): disarm before ANY oracle replay, then assert.
        self._disarm(reason="calculate_reward")
        assert self.armed is False, "armed must be cleared before reward"
        assert self.inner.tools_map == self._pristine_map, "tools_map must be pristine at reward"
        assert self.inner.tools_info == self._pristine_info, "tools_info must be pristine at reward"
        self._in_reward = True
        try:
            res = self._orig_calculate_reward()
        finally:
            self._in_reward = False
        self.trace.write({
            "event": "done", "reward": res.reward,
            "data_hash": self.inner.get_data_hash(), "wall_ms": self._wall_ms(),
        })
        return res

    def calculate_reward(self):
        """Production reward path: always disarms first (via the wrapped inner method)."""
        return self.inner.calculate_reward()

    def raw_calculate_reward_unsafe(self):
        """Reproduce Landmine 1: run the RAW oracle WITHOUT disarming. This exists ONLY for
        the self-tests that demonstrate the false pass; it is never on a measurement path."""
        return self._orig_calculate_reward()

    def assert_disarm_guarantee(self) -> None:
        """The guard that must hold before the raw oracle may run: no fault may be armed.
        Trips (AssertionError) if called while a fault is armed -- used by
        test_disarm_guarantee to prove the guarantee is real, not decorative."""
        assert not (self.armed and self._fired), (
            "disarm guarantee violated: calculate_reward reachable with a fault armed "
            f"(armed={self.armed}, fired={sorted(self._fired)})"
        )

    # ------------------------------------------------------------ probe / helpers
    def probe(self, tool_name: str, *, probe_sees_faults: Optional[bool] = None, **kwargs) -> str:
        sees = self.probe_sees_faults if probe_sees_faults is None else probe_sees_faults
        return probe(self, tool_name, probe_sees_faults=sees, **kwargs)

    def opening_reading(self, reads: List[Tuple[str, dict]]) -> List[dict]:
        return opening_reading(self, reads)

    def data_hash(self) -> str:
        return self.inner.get_data_hash()

    def _wall_ms(self) -> Optional[float]:
        return round((time.monotonic() - self._t0) * 1000, 3) if self._t0 is not None else None
