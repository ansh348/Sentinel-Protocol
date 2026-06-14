"""N1 acceptance: sentinel_v2 scaffolding exists, is flagged off by default,
and changes no behavior anywhere while the flag is off."""
from __future__ import annotations

import pytest

from sentinel_v2 import arms, flags


def test_flag_default_off(monkeypatch):
    monkeypatch.delenv(flags.ENV_VAR, raising=False)
    assert flags.v2_enabled() is False


def test_flag_explicit_on(monkeypatch):
    monkeypatch.setenv(flags.ENV_VAR, "1")
    assert flags.v2_enabled() is True


def test_arm_designations_per_p3():
    assert arms.PRIMARY_ARM == arms.TWO_TIER
    assert arms.REBUILT_JUDGE in arms.EXPLORATORY_ARMS
    assert arms.PRIMARY_ARM not in arms.EXPLORATORY_ARMS


def test_resolve_v2_arm_refuses_with_flag_off(monkeypatch):
    monkeypatch.delenv(flags.ENV_VAR, raising=False)
    with pytest.raises(RuntimeError, match="flagged off"):
        arms.resolve_arm(arms.TWO_TIER)


def test_resolve_arm_returns_specs_when_wired(monkeypatch):
    """Arms are now WIRED (this task): resolve returns an ArmSpec, not a stub raise."""
    monkeypatch.setenv(flags.ENV_VAR, "1")
    assert arms.resolve_arm(arms.TWO_TIER).role == "primary"
    assert arms.resolve_arm(arms.REBUILT_JUDGE).role == "exploratory"
    # baselines resolve regardless of the v2 flag
    monkeypatch.delenv(flags.ENV_VAR, raising=False)
    assert arms.resolve_arm("S1").kind == "baseline"
    with pytest.raises(KeyError):
        arms.resolve_arm("S5")            # not a 1b matrix arm


def test_v2_arms_are_not_v1_conductor_systems():
    """The v2 arms are registered in the ARM registry with their own runner; they are
    deliberately NOT v1 SystemConfigs, so they never run through the v1 tripwire/judge
    loop (decision #5 holds: configuration, but the v2 detection path is its own)."""
    from conductor.systems import SYSTEMS
    assert arms.TWO_TIER not in SYSTEMS and arms.REBUILT_JUDGE not in SYSTEMS
    assert arms.TWO_TIER in arms.ARMS and arms.REBUILT_JUDGE in arms.ARMS
