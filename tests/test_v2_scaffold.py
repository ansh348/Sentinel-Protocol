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


def test_resolve_arm_refuses_with_flag_off(monkeypatch):
    monkeypatch.delenv(flags.ENV_VAR, raising=False)
    with pytest.raises(RuntimeError, match="flagged off"):
        arms.resolve_arm(arms.TWO_TIER)


def test_resolve_arm_is_stub_with_flag_on(monkeypatch):
    monkeypatch.setenv(flags.ENV_VAR, "1")
    with pytest.raises(NotImplementedError, match="night-shift hard stop"):
        arms.resolve_arm(arms.TWO_TIER)
    with pytest.raises(NotImplementedError):
        arms.resolve_arm(arms.REBUILT_JUDGE)
    with pytest.raises(KeyError):
        arms.resolve_arm("S5")


def test_v2_arms_not_registered_in_systems():
    """No run can be launched against a v2 arm until the author wires it:
    the provisional ids must NOT appear in the conductor's system registry."""
    from conductor.systems import SYSTEMS
    assert arms.TWO_TIER not in SYSTEMS
    assert arms.REBUILT_JUDGE not in SYSTEMS
