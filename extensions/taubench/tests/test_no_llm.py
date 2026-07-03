"""test_no_llm: the litellm stub raises if anything calls completion, and a full harness
episode triggers zero completion calls. Together with the guard being installed suite-wide
(any stray call raises and fails its test), a green suite proves the zero-LLM invariant.
"""
from __future__ import annotations

import litellm
import pytest

from extensions.taubench.faulted_env import FaultedEnv


def test_completion_is_blocked(llm_guard):
    before = llm_guard["attempts"]
    with pytest.raises(Exception):
        litellm.completion(model="none", messages=[{"role": "user", "content": "hi"}])
    assert llm_guard["attempts"] == before + 1, "the guard should have recorded the attempt"


def test_harness_episode_makes_no_llm_call(llm_guard):
    before = llm_guard["attempts"]

    env = FaultedEnv(faults=[], task_index=0)
    env.reset(0)
    terminate = set(env.inner.terminate_tools)
    for a in env.inner.task.actions:
        if a.name not in terminate:
            env.step(a)
    env.calculate_reward()

    env.cost_meter.assert_zero_llm_cost()
    assert env.cost_meter.n_tool_calls > 0, "sanity: the episode did make tool calls"
    assert llm_guard["attempts"] == before, "the harness must trigger no LLM completion"
