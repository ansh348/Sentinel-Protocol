#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_capture_pathA.py <compile|worker> <proxy_port>  --  FEASIBILITY helper

Runs the Claude Code CLI (Path A) for one call site, routed through the logging
proxy via ANTHROPIC_BASE_URL + ANTHROPIC_API_KEY, so the proxy captures the EXACT
request the CLI constructs.  Mirrors the argv that conductor/sessions.run_claude
builds for that call site.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from analysis.benchmark_1c_apikey_equivalence import load_api_key  # noqa: E402

mode = sys.argv[1]
PORT = int(sys.argv[2])
key, _ = load_api_key()
assert key, "no ANTHROPIC_API_KEY"

claude = os.environ.get("CAP_CLAUDE_BIN") or shutil.which("claude") or "claude"  # CAP_CLAUDE_BIN: pin a specific version's binary
scratch = Path(os.environ.get("TRIPWIRE_SCRATCH") or ("C:/temp/tripwire-scratch" if os.name == "nt" else "/tmp/tw-cap"))
scratch.mkdir(parents=True, exist_ok=True)
home = Path(tempfile.mkdtemp(prefix="cap_", dir=scratch))
(home / "tw_settings.json").write_text("{}", encoding="utf-8")

env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE" and not k.startswith("CLAUDE_")}
env["USERPROFILE"] = str(home)
env["HOME"] = str(home)
env["ANTHROPIC_BASE_URL"] = f"http://127.0.0.1:{PORT}"
env["ANTHROPIC_API_KEY"] = key  # forces API-key auth; OAuth token stripped above

if mode == "compile":
    sysprompt = (ROOT / "prompts" / "v2_compile.md").read_text(encoding="utf-8")
    plan = '{"goal":"fetch region demand ledgers and reconcile","steps":[{"id":"s1","subtask":"GET /regions/R-0001/evidence"}]}'
    argv = [claude, "-p", "--model", "claude-sonnet-4-6", "--system-prompt", sysprompt,
            "--output-format", "json", "--max-turns", "1", "--settings", str(home / "tw_settings.json"),
            "--strict-mcp-config", "--tools", ""]
    stdin_text = plan
elif mode == "worker":
    sysprompt = (ROOT / "prompts" / "worker.md").read_text(encoding="utf-8")
    argv = [claude, "-p", "GET /regions/R-0001/evidence and report the demand value",
            "--model", "claude-haiku-4-5-20251001", "--system-prompt", sysprompt,
            "--output-format", "json", "--max-turns", "14", "--settings", str(home / "tw_settings.json"),
            "--strict-mcp-config", "--allowedTools", "Bash(curl http://localhost:9/*)"]
    stdin_text = ""
else:
    raise SystemExit("mode must be compile|worker")

try:
    p = subprocess.run(argv, input=stdin_text, env=env, cwd=str(home),
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
    print(f"[pathA {mode}] exit={p.returncode} stdout_len={len(p.stdout)} stderr_tail={p.stderr[-200:]!r}")
except subprocess.TimeoutExpired:
    print(f"[pathA {mode}] TIMEOUT (request likely still captured by proxy)")
finally:
    shutil.rmtree(home, ignore_errors=True)
