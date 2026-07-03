"""test_armed_false_pass: reproduce Landmine 1 and show the disarm hook fixes it.

With a surface_removal fault (remove the write tool the task depends on) still armed through
reward computation, a blind baseline -- one that performed the reads but never did the write
-- hash-matches the corrupted oracle and FALSE-PASSES. With the disarm hook active, the same
baseline correctly FAILS. Both directions are asserted. Zero LLM.

Anchor: retail test task 66 has outputs=[] (so reward.info carries r_actions) and a single
write, cancel_pending_order(#W3361211); its other actions are reads.
"""
from __future__ import annotations

from pathlib import Path

from extensions.taubench.faults import FaultConfig
from extensions.taubench.faulted_env import FaultedEnv

FAULTS_DIR = Path(__file__).resolve().parents[1] / "faults"
TASK = 66
WRITE = "cancel_pending_order"


def _blind_episode(env):
    """Perform every ground-truth action EXCEPT the write (the blind baseline), driving the
    tool-call counter so the fault arms, but leaving env.data at the clean/initial state."""
    for a in env.inner.task.actions:
        if a.name == WRITE:
            continue
        env.step(a)


def test_armed_false_pass_reproduces_and_disarm_fixes():
    f2 = FaultConfig.from_json_file(str(FAULTS_DIR / "F2_surface_removal_cancel.json"))
    assert f2.kind == "surface_removal" and f2.target_tool == WRITE

    # --- Direction 1: armed through reward -> FALSE PASS (the landmine) ---------------
    env = FaultedEnv(faults=[f2], task_index=TASK)
    env.reset(TASK)
    _blind_episode(env)
    assert env.armed is True
    assert WRITE not in env.inner.tools_map, "fault should have removed the write tool"

    res = env.raw_calculate_reward_unsafe()  # RAW oracle, fault still armed
    assert bool(res.info.r_actions) is True, (
        "landmine not reproduced: blind baseline should false-pass while the removal is armed"
    )

    # --- Direction 2: disarm hook -> CORRECT FAIL ------------------------------------
    env2 = FaultedEnv(faults=[f2], task_index=TASK)
    env2.reset(TASK)
    _blind_episode(env2)
    assert WRITE not in env2.inner.tools_map  # armed during the episode

    res2 = env2.calculate_reward()  # guarded path: disarms, restores the write tool
    assert env2.armed is False
    assert WRITE in env2.inner.tools_map, "disarm must restore the removed tool"
    assert bool(res2.info.r_actions) is False, (
        "disarmed oracle should correctly fail the blind baseline (write not performed)"
    )
