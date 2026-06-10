"""claude -p subprocess wrapper. M2 ships the single-turn slice (sentinel compile
and judge); M3 adds multi-turn worker sessions and --resume orchestrator turns.

Invocation contract (BUILD_BRIEF Section 5, as amended by deviations.md D1):
CLI 2.1.170's --bare mode only supports API-key auth, which conflicts with the
locked Path A decision (subscription billing, no API keys anywhere). Per the
author-approved deviation, every session replicates bare-mode controls
explicitly while authenticating with a long-lived subscription OAuth token:

- isolated home directory (USERPROFILE + HOME point at a per-call scratch dir):
  no user hooks, settings, plugins, memory, CLAUDE.md auto-discovery, or
  credential-store reads
- scratch home AND cwd live OUTSIDE the user profile tree: CLAUDE.md discovery
  walks cwd ancestors, so any cwd under C:\\Users\\<user> picks up
  ~\\.claude\\CLAUDE.md regardless of the env-var isolation (found empirically
  by the canary test, 2026-06-10; guarded by _assert_outside_user_tree)
- inherited CLAUDE*/CLAUDECODE env vars stripped from the child environment
- --system-prompt (full replacement of the default prompt, fully rendered)
- --settings pinned to a minimal generated settings file
- --strict-mcp-config with no --mcp-config (no MCP servers)
- --tools "" for no-tools sessions / --allowedTools pinning for workers
- pinned full model strings, --output-format json, --max-turns caps

The OAuth token is read from the environment or the operator-managed token file
and injected ONLY into the child process environment: never argv, never the
repo, never traces (trace.py refuses to serialize sk-ant credentials).
"""
from __future__ import annotations

import functools
import json
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import psutil

TOKEN_ENV = "CLAUDE_CODE_OAUTH_TOKEN"
TOKEN_FILE = Path.home() / ".claude" / "tripwire_oauth_token"
CLAUDE_BIN_ENV = "TRIPWIRE_CLAUDE_BIN"  # test/queue override: argv prefix, ;-separated
SCRATCH_ENV = "TRIPWIRE_SCRATCH"        # override for the scratch root

HARD_TIMEOUT_S = 360  # BUILD_BRIEF Section 5: every subprocess wrapped in timeout 360

ORCHESTRATOR_MODEL = "claude-sonnet-4-6"
COMPILE_MODEL = "claude-sonnet-4-6"
WORKER_MODEL = "claude-haiku-4-5-20251001"
JUDGE_MODEL = "claude-haiku-4-5-20251001"

# List prices (USD per million tokens) for the cost reconstruction required by
# BUILD_BRIEF Section 5 when total_cost_usd is absent or zero. Cache writes are
# 1.25x input (5m TTL) / 2x input (1h TTL); cache reads 0.1x input.
LIST_PRICES_USD_PER_MTOK: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00, "cache_read": 0.30,
                          "cache_write_5m": 3.75, "cache_write_1h": 6.00},
    "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00, "cache_read": 0.10,
                                  "cache_write_5m": 1.25, "cache_write_1h": 2.50},
}


def default_scratch_root() -> Path:
    """Where per-call isolated homes are created. MUST be outside the user
    profile tree (see _assert_outside_user_tree); the system temp dir is NOT
    safe because it lives under the user profile on Windows."""
    override = os.environ.get(SCRATCH_ENV)
    if override:
        return Path(override)
    if os.name == "nt":
        return Path("C:/temp/tripwire-scratch")
    return Path("/tmp/tripwire-scratch")


def _assert_outside_user_tree(path: Path, what: str) -> None:
    """Claude Code discovers CLAUDE.md by walking cwd ancestors, and the real
    user home contains ~/.claude/CLAUDE.md — so a session home or cwd anywhere
    under the user profile silently re-leaks user context into the session,
    defeating deviations.md D1 control #1. Proven by the canary test."""
    user_home = Path.home().resolve()
    if path.resolve().is_relative_to(user_home):
        raise ValueError(
            f"{what}={path} is inside the user profile tree ({user_home}); "
            "CLAUDE.md ancestor discovery would leak user context into the "
            "session. Use a location under default_scratch_root() instead.")


def load_oauth_token() -> Optional[str]:
    token = os.environ.get(TOKEN_ENV, "").strip()
    if token:
        return token
    if TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if token:
            return token
    return None


def resolve_claude_argv() -> list[str]:
    override = os.environ.get(CLAUDE_BIN_ENV)
    if override:
        return override.split(";")
    binary = shutil.which("claude")
    if not binary:
        raise RuntimeError("claude CLI not found on PATH")
    return [binary]


@functools.lru_cache(maxsize=1)
def get_cli_version() -> str:
    out = subprocess.run(resolve_claude_argv() + ["--version"],
                         capture_output=True, text=True, timeout=60)
    return out.stdout.strip()


def reconstruct_cost_usd(usage: Optional[dict], model: str) -> Optional[float]:
    """Token-based USD reconstruction at list prices (recorded alongside the
    reported number for every invocation, per BUILD_BRIEF Section 5)."""
    if not usage:
        return None
    prices = LIST_PRICES_USD_PER_MTOK.get(model)
    if prices is None:
        return None
    cache = usage.get("cache_creation") or {}
    write_5m = cache.get("ephemeral_5m_input_tokens")
    write_1h = cache.get("ephemeral_1h_input_tokens", 0)
    if write_5m is None:  # older payloads: only the aggregate is present
        write_5m = usage.get("cache_creation_input_tokens", 0)
        write_1h = 0
    cost = (
        usage.get("input_tokens", 0) * prices["input"]
        + usage.get("output_tokens", 0) * prices["output"]
        + usage.get("cache_read_input_tokens", 0) * prices["cache_read"]
        + write_5m * prices["cache_write_5m"]
        + write_1h * prices["cache_write_1h"]
    ) / 1_000_000
    return round(cost, 6)


@dataclass
class SessionResult:
    model: str
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    duration_s: float
    payload: Optional[dict] = None
    # derived from payload
    result_text: Optional[str] = None
    session_id: Optional[str] = None
    num_turns: Optional[int] = None
    is_error: bool = False
    usage: Optional[dict] = None
    model_usage: Optional[dict] = None
    total_cost_usd_reported: Optional[float] = None
    cost_usd_reconstructed: Optional[float] = None

    @property
    def cost_usd(self) -> float:
        if self.total_cost_usd_reported:
            return self.total_cost_usd_reported
        return self.cost_usd_reconstructed or 0.0

    def trace_usage(self) -> dict:
        """The 5-field usage object required on LLM-call trace events."""
        usage = self.usage or {}
        return {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "cost_usd": self.cost_usd,
            "model": self.model,
            "session_id": self.session_id,
        }

    def trace_payload(self) -> dict:
        """Per-invocation accounting written into trace event payloads:
        exit code, stderr, both cost numbers, turns, timing."""
        return {
            "exit_code": self.exit_code,
            "stderr": self.stderr[-2000:],
            "timed_out": self.timed_out,
            "duration_s": round(self.duration_s, 3),
            "num_turns": self.num_turns,
            "is_error": self.is_error,
            "total_cost_usd_reported": self.total_cost_usd_reported,
            "cost_usd_reconstructed": self.cost_usd_reconstructed,
        }


def _child_env(isolated_home: Path, token: Optional[str]) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items()
           if k != "CLAUDECODE" and not k.startswith("CLAUDE_")}
    env["USERPROFILE"] = str(isolated_home)
    env["HOME"] = str(isolated_home)
    if token:
        env[TOKEN_ENV] = token
    return env


def _kill_process_tree(pid: int) -> None:
    """Kill the subprocess AND all its descendants. claude.exe on Windows spawns
    node children that a plain Popen.kill() orphans, leaving sessions running
    past the hard timeout (parked author note (a); psutil pre-approved for this)."""
    try:
        parent = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return
    procs = parent.children(recursive=True) + [parent]
    for proc in procs:
        try:
            proc.kill()
        except psutil.NoSuchProcess:
            pass
    psutil.wait_procs(procs, timeout=10)


def run_claude(*, model: str, system_prompt: str, max_turns: int,
               prompt: Optional[str] = None, stdin_text: Optional[str] = None,
               no_tools: bool = False, allowed_tools: Optional[str] = None,
               resume: Optional[str] = None, isolated_home: Optional[Path] = None,
               cwd: Optional[Path] = None, timeout_s: int = HARD_TIMEOUT_S,
               claude_argv: Optional[list[str]] = None,
               token: Optional[str] = None) -> SessionResult:
    """One headless claude -p invocation under the deviations.md D1 controls.

    The user prompt goes via stdin (stdin_text) for compile/judge — matching the
    protocol Section 3.6 `cat plan.md | claude -p` shape — or as the positional
    argument (prompt) for workers."""
    token = token if token is not None else load_oauth_token()
    argv_prefix = claude_argv if claude_argv is not None else resolve_claude_argv()

    own_home = isolated_home is None
    if own_home:
        root = default_scratch_root()
        root.mkdir(parents=True, exist_ok=True)
        home = Path(tempfile.mkdtemp(prefix="tw_home_", dir=root))
    else:
        home = Path(isolated_home)
        home.mkdir(parents=True, exist_ok=True)
    _assert_outside_user_tree(home, "isolated_home")
    effective_cwd = Path(cwd) if cwd is not None else home
    _assert_outside_user_tree(effective_cwd, "cwd")
    settings_path = home / "tw_settings.json"
    settings_path.write_text("{}", encoding="utf-8")

    argv = list(argv_prefix) + ["-p"]
    if prompt is not None:
        argv.append(prompt)
    argv += [
        "--model", model,
        "--system-prompt", system_prompt,
        "--output-format", "json",
        "--max-turns", str(max_turns),
        "--settings", str(settings_path),
        "--strict-mcp-config",
    ]
    if no_tools:
        argv += ["--tools", ""]
    if allowed_tools:
        argv += ["--allowedTools", allowed_tools]
    if resume:
        argv += ["--resume", resume]

    started = time.monotonic()
    timed_out = False
    proc = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=_child_env(home, token), cwd=str(effective_cwd),
        text=True, encoding="utf-8", errors="replace",
    )
    try:
        stdout, stderr = proc.communicate(input=stdin_text or "", timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_process_tree(proc.pid)
        stdout, stderr = proc.communicate()
    duration = time.monotonic() - started

    result = SessionResult(model=model, exit_code=proc.returncode,
                           stdout=stdout or "", stderr=stderr or "",
                           timed_out=timed_out, duration_s=duration)
    try:
        payload = json.loads(stdout) if stdout and stdout.strip() else None
    except ValueError:
        payload = None
    if isinstance(payload, dict):
        result.payload = payload
        raw_result = payload.get("result")
        result.result_text = raw_result if isinstance(raw_result, str) else None
        result.session_id = payload.get("session_id")
        result.num_turns = payload.get("num_turns")
        result.is_error = bool(payload.get("is_error", False))
        result.usage = payload.get("usage")
        result.model_usage = payload.get("modelUsage")
        result.total_cost_usd_reported = payload.get("total_cost_usd")
        result.cost_usd_reconstructed = reconstruct_cost_usd(result.usage, model)

    if own_home:
        shutil.rmtree(home, ignore_errors=True)
    return result
