"""Offline tests for the claude -p subprocess wrapper (fake claude binary)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

from conductor.sessions import (TOKEN_ENV, _child_env, reconstruct_cost_usd,
                                run_claude)

FAKE = str(Path(__file__).parent / "fake_claude.py")
FAKE_ARGV = [sys.executable, FAKE]


def run_fake(monkeypatch, mode: str, **kwargs):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", mode)
    defaults = dict(model="claude-haiku-4-5-20251001", system_prompt="test",
                    stdin_text="input", max_turns=1, no_tools=True,
                    claude_argv=FAKE_ARGV, token="not-a-real-credential")
    defaults.update(kwargs)
    return run_claude(**defaults)


def test_ok_invocation_parses_payload(monkeypatch):
    result = run_fake(monkeypatch, "ok")
    assert result.exit_code == 0
    assert not result.timed_out and not result.is_error
    assert result.session_id == "fake-session-123"
    assert result.num_turns == 1
    assert result.total_cost_usd_reported == 0.01
    assert result.cost_usd == 0.01
    # reconstruction recorded alongside the reported number
    assert result.cost_usd_reconstructed == 0.002  # (1000*1 + 200*5) / 1e6
    usage = result.trace_usage()
    assert usage == {"input_tokens": 1000, "output_tokens": 200,
                     "cost_usd": 0.01, "model": "claude-haiku-4-5-20251001",
                     "session_id": "fake-session-123"}


def test_zero_reported_cost_falls_back_to_reconstruction(monkeypatch):
    result = run_fake(monkeypatch, "zero_cost")
    assert result.total_cost_usd_reported == 0.0
    assert result.cost_usd == result.cost_usd_reconstructed == 0.002


def test_reconstruction_prices_sonnet_and_cache():
    usage = {"input_tokens": 1_000_000, "output_tokens": 100_000,
             "cache_read_input_tokens": 500_000,
             "cache_creation": {"ephemeral_5m_input_tokens": 200_000,
                                "ephemeral_1h_input_tokens": 0}}
    cost = reconstruct_cost_usd(usage, "claude-sonnet-4-6")
    # 1M*3.00 + 0.1M*15.00 + 0.5M*0.30 + 0.2M*3.75 (per MTok)
    assert cost == 3.0 + 1.5 + 0.15 + 0.75
    assert reconstruct_cost_usd(usage, "unknown-model") is None


def test_timeout_kills_process_tree(monkeypatch):
    started = time.monotonic()
    result = run_fake(monkeypatch, "sleep", timeout_s=2)
    elapsed = time.monotonic() - started
    assert result.timed_out
    assert elapsed < 25, "tree-kill did not interrupt the sleeping child"


def test_throttle_surfaces_exit_and_stderr(monkeypatch):
    result = run_fake(monkeypatch, "throttle")
    assert result.exit_code == 1
    assert "rate limit" in result.stderr.lower()
    assert result.payload is None


def test_user_tree_homes_are_rejected(tmp_path, monkeypatch):
    """Regression guard for the cwd-ancestor CLAUDE.md leak: session homes and
    cwds inside the user profile tree must be refused outright."""
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "ok")
    import pytest
    with pytest.raises(ValueError, match="user profile tree"):
        run_fake(monkeypatch, "ok", isolated_home=tmp_path / "home")
    with pytest.raises(ValueError, match="user profile tree"):
        run_fake(monkeypatch, "ok", cwd=Path.home())


def test_child_env_isolation(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "parent-session")
    monkeypatch.setenv("PATH", "keepme")
    env = _child_env(tmp_path, "tok-value")
    assert "CLAUDECODE" not in env
    assert "CLAUDE_CODE_SESSION_ID" not in env
    assert env["PATH"] == "keepme"
    assert env[TOKEN_ENV] == "tok-value"
    assert env["USERPROFILE"] == str(tmp_path)
    assert env["HOME"] == str(tmp_path)
