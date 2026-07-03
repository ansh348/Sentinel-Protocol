"""test_disarm_guarantee: calculate_reward can never execute with a fault armed.

Two directions: (1) while a fault is armed, the disarm-guarantee assertion trips if the raw
oracle is reachable -- proving the guard is real; (2) the production calculate_reward path
ALWAYS disarms first (armed cleared, tools restored to pristine, disarm logged before the
done event). Zero LLM.
"""
from __future__ import annotations

import pytest

from extensions.taubench.faults import FaultConfig
from extensions.taubench.faulted_env import FaultedEnv

TASK = 66
WRITE = "cancel_pending_order"


def test_disarm_guarantee():
    f2 = FaultConfig(id="rm_cancel", kind="surface_removal", target_tool=WRITE, trigger_n=1)
    env = FaultedEnv(faults=[f2], task_index=TASK)
    env.reset(TASK)

    # Drive one tool call so the fault arms (trigger_n=1).
    env.step(env.inner.task.actions[0])
    assert env.armed is True and env._fired, "fault should be armed after the first tool call"
    assert WRITE not in env.inner.tools_map

    # (1) The guarantee is real: the guard trips while a fault is armed.
    with pytest.raises(AssertionError):
        env.assert_disarm_guarantee()

    # (2) The production reward path disarms structurally before the oracle runs.
    res = env.calculate_reward()
    assert res is not None
    assert env.armed is False, "armed must be cleared by the disarm hook"
    assert env.inner.tools_map == env._pristine_map, "tools_map must be restored to pristine"
    assert env.inner.tools_info == env._pristine_info, "tools_info must be restored to pristine"
    assert WRITE in env.inner.tools_map, "removed tool must be back before reward"

    # Post-disarm the guard passes, and the trace shows disarm preceded the done event.
    env.assert_disarm_guarantee()
    events = [r["event"] for r in env.trace.records]
    assert "disarm" in events and "done" in events
    assert events.index("disarm") < events.index("done"), "disarm must precede reward's done"
