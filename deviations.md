# Methodology Deviations Log

Pre-registration discipline requires that any departure from the frozen
protocol/brief be recorded here with evidence, before data collection.
`make freeze` must reference this file from `prereg.md`.

---

## D1 — `--bare` replaced by an equivalent-controls invocation

**Date:** 2026-06-10 (before any Phase 0/1 data collection)
**CLI:** Claude Code 2.1.170
**Affects:** BUILD_BRIEF Section 5 ("Always: `--bare` ...") for every `claude -p`
invocation. Author-approved (Option 1) after empirical demonstration that the
constraint is unsatisfiable under the locked Path A decisions.

### Why

BUILD_BRIEF Section 5 requires `--bare` on every invocation; locked decision #1
requires subscription billing with "no API keys anywhere". In CLI 2.1.170 these
are mutually exclusive: `--bare` documents that "Anthropic auth is strictly
ANTHROPIC_API_KEY or apiKeyHelper via --settings (OAuth and keychain are never
read)". Empirical matrix (all probes 2026-06-10, this machine):

| Mode | Auth source | Result |
|---|---|---|
| normal | OAuth credential store (auto-refresh) | works |
| normal | `CLAUDE_CODE_OAUTH_TOKEN` setup-token, isolated home | works |
| `--bare` | credential store / OAuth env token | "Not logged in" |
| `--bare` | `apiKeyHelper` returning the OAuth setup-token | "Invalid API key" (helper output is sent with API-key semantics) |
| `CLAUDE_CODE_SIMPLE=1` (bare's own mechanism) | OAuth env token | "Not logged in" |

The alternative — `ANTHROPIC_API_KEY` under `--bare` — is Path B billing for
the full matrix and violates locked decision #1, so it was rejected.

### Replacement controls (what `conductor/sessions.py` does instead)

The intent of `--bare` is "no environment-dependent context". Each invocation
replicates that explicitly, in normal mode:

1. **Isolated home**: `USERPROFILE` and `HOME` point at a per-call scratch
   directory, so user hooks, settings, plugins, memory, `CLAUDE.md`
   auto-discovery, and the credential store are never read.
2. **Env stripping**: all inherited `CLAUDE*`/`CLAUDECODE` variables are
   removed from the child environment.
3. **`--system-prompt`**: full replacement of the default prompt, fully
   rendered (unchanged from the brief).
4. **`--settings`**: pinned to a generated minimal settings file (`{}`).
5. **`--strict-mcp-config`** with no `--mcp-config`: no MCP servers.
6. **`--tools ""`** for compile/judge/orchestrator (no tools at all);
   `--allowedTools` pinning for workers (unchanged from the brief).
7. **cwd** set to the isolated home, so no project-level `.claude/` or
   `CLAUDE.md` discovery applies.
8. **Scratch homes and cwd live OUTSIDE the user profile tree** (default
   `C:\temp\tripwire-scratch`, override `TRIPWIRE_SCRATCH`), enforced by a
   hard guard in `sessions.py`. Found by the canary test on first run
   (2026-06-10): `CLAUDE.md` discovery walks **cwd ancestors**, so a session
   whose cwd sits anywhere under `C:\Users\<user>` — including the system temp
   directory — picks up `~\.claude\CLAUDE.md` even with `USERPROFILE`/`HOME`
   fully isolated. Probe matrix: home+cwd under user temp → leaked; home+cwd
   outside the user tree → clean; home under user temp but cwd outside →
   clean (the leak is cwd-borne, not env-borne).

Auth is a long-lived subscription OAuth setup-token supplied via
`CLAUDE_CODE_OAUTH_TOKEN` in the child environment only (never argv, never the
repo, never traces — `trace.py` refuses to serialize `sk-ant` material).

### Verification

`tests/test_canary_isolation.py` runs on every `make test`: it plants a marker
`CLAUDE.md` and a marker `SessionStart` hook in the real user config, runs a
sandboxed pong under the recipe above, and asserts both canaries are invisible
(no canary token in the reply; the hook's sentinel file is never created), and
that the resulting trace contains no credential material.

### Residual differences vs `--bare` (accepted)

- LSP/plugin-sync/attribution/background-prefetch code paths are skipped by
  `--bare` outright; under the replacement they run against an empty isolated
  home, which makes them no-ops rather than disabled. No context can enter the
  prompt from an empty home, which is the property the control exists for.
- Enterprise managed settings (`C:\ProgramData\ClaudeCode\managed-settings.json`)
  would apply in normal mode if present. Not present on this machine; the
  canary test machine-checks the observable consequences regardless.

### Accounting note

The first authenticated probes confirmed `total_cost_usd` IS populated under
subscription billing (protocol §3.6 asked this to be verified on first run).
Token-based reconstruction at list prices is still recorded alongside the
reported number for every invocation, per BUILD_BRIEF Section 5.
