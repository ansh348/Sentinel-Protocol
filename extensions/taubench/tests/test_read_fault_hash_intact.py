"""test_read_fault_hash_intact: a price-swap read_transform leaves the episode data hash
equal to the clean oracle hash (read faults never touch env.data), while the observation the
agent sees is genuinely corrupted. Zero LLM.
"""
from __future__ import annotations

import json

from extensions.taubench.faults import FaultConfig
from extensions.taubench.faulted_env import FaultedEnv

TOOL = "get_product_details"
REPLACE = "13371337.00"  # sentinel; chosen NOT to contain the original price substring


def _first_task_calling(env, tool):
    for i, t in enumerate(env.inner.tasks):
        for a in t.actions:
            if a.name == tool:
                return i, a.kwargs.get("product_id")
    return None, None


def _clean_replay_hash(env, task_index):
    terminate = set(env.inner.terminate_tools)
    env.reset(task_index)
    for a in env.inner.task.actions:
        if a.name not in terminate:
            env.step(a)
    return env.inner.get_data_hash()


def test_read_fault_hash_intact():
    probe_env = FaultedEnv(faults=[], task_index=0)
    ti, pid = _first_task_calling(probe_env, TOOL)
    assert ti is not None and pid is not None, "need a task that calls get_product_details"

    # Derive a real price substring from the product this task queries.
    probe_env.reset(ti)
    clean_obs = probe_env._pristine_map[TOOL].invoke(data=probe_env.inner.data, product_id=pid)
    product = json.loads(clean_obs)
    price = next(iter(product["variants"].values()))["price"]
    find = str(price)
    assert find not in REPLACE  # sentinel must be distinguishable from the original

    # Clean oracle hash for a faithful ground-truth replay (no fault).
    clean_hash = _clean_replay_hash(FaultedEnv(faults=[], task_index=ti), ti)

    # Faulted run: price-swap read_transform on get_product_details.
    f1 = FaultConfig(id="price_swap", kind="read_transform", target_tool=TOOL,
                     trigger_n=1, find=find, replace=REPLACE)
    env = FaultedEnv(faults=[f1], task_index=ti)
    terminate = set(env.inner.terminate_tools)
    env.reset(ti)
    for a in env.inner.task.actions:
        if a.name not in terminate:
            env.step(a)
    faulted_hash = env.inner.get_data_hash()

    # 1) The data hash is unchanged: read_transform never mutates env.data.
    assert faulted_hash == clean_hash, "read_transform must not change env.data"

    # 2) The fault actually fired and the corruption is real (through the faulted path only).
    assert env.trace.events("fault_fire"), "F1 read_transform should have fired"
    faulted_view = env.probe(TOOL, product_id=pid, probe_sees_faults=True)
    clean_view = env.probe(TOOL, product_id=pid, probe_sees_faults=False)
    assert REPLACE in faulted_view and find not in faulted_view, "swap not applied on faulted read"
    assert REPLACE not in clean_view and find in clean_view, "clean read should be untouched"
