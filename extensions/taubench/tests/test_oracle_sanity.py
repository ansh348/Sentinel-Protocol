"""test_oracle_sanity: every retail test task with a nonempty ground-truth action list is
hash-consistent under episode-vs-oracle replay.

The "episode" faithfully replays the ground-truth actions; the "oracle" mirrors
Env.calculate_reward exactly (reload clean data, replay task.actions excluding terminate
tools). A consistent oracle => the two data hashes match. Expected 113 of 115 test tasks;
the 2 zero-action tasks are skipped and asserted to exist. Zero LLM.
"""
from __future__ import annotations

from extensions.taubench.faulted_env import FaultedEnv


def _nonrespond(actions):
    return [a for a in actions if a.name != "respond"]


def test_oracle_sanity():
    env = FaultedEnv(faults=[], task_index=0)
    tasks = env.inner.tasks
    terminate = set(env.inner.terminate_tools)

    assert len(tasks) == 115, "retail test split should have 115 tasks"

    # The 2 zero-action tasks are skipped and asserted to exist.
    empty = [i for i, t in enumerate(tasks) if len(_nonrespond(t.actions)) == 0]
    assert len(empty) == 2, f"expected exactly 2 zero-action tasks, found {empty}"

    # NullUser safety: ground-truth actions contain no `respond` (else the reward oracle's
    # internal replay would recurse via done=True). Lock the invariant.
    assert all(a.name != "respond" for t in tasks for a in t.actions), (
        "a ground-truth action list contains a respond action (NullUser recursion risk)"
    )

    consistent = 0
    for i, t in enumerate(tasks):
        if i in empty:
            continue
        # episode: faithful ground-truth replay
        env.reset(i)
        for a in t.actions:
            if a.name not in terminate:
                env.inner.step(a)
        episode_hash = env.inner.get_data_hash()

        # oracle: exact mirror of Env.calculate_reward's replay
        env.inner.data = env.inner.data_load_func()
        for a in t.actions:
            if a.name not in terminate:
                env.inner.step(a)
        oracle_hash = env.inner.get_data_hash()

        assert episode_hash == oracle_hash, f"task {i}: episode/oracle hash mismatch"
        consistent += 1

    assert consistent == 113, f"expected 113 hash-consistent tasks, got {consistent}"
