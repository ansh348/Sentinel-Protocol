# Overnight execution runbook (protocol Section 8.1, Windows host)

## Before the first night

1. **Keep-awake** (parked author note b): the supervisor holds
   `SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)` while jobs
   run, which prevents sleep but NOT a lid-close/hibernate policy. Set once:
   ```
   powercfg /change standby-timeout-ac 0
   powercfg /change hibernate-timeout-ac 0
   ```
   (Laptop: also set the lid-close action to "Do nothing" while plugged in.)
2. **Token freshness**: the subscription OAuth setup-token must be valid in
   `~/.claude/tripwire_oauth_token` (or `CLAUDE_CODE_OAUTH_TOKEN`). Verify
   with `make test` (the live canary fails loudly on bad auth).
3. **CLI version pin**: the queue records `claude --version` on first run and
   HALTS if it changes mid-matrix. Do not update Claude Code mid-matrix.
4. **Shared-budget rule** (protocol 8.1): schedule heavy nights right after
   the weekly subscription reset; keep daytime Claude Code usage light on
   those days.

## Night 0

```
make night0     # enqueue manipulation checks (S1 x injected pairs, seed 1)
                # + clean S1 calibration runs
make queue      # start the supervisor (leave the terminal open; machine awake)
```

n_inject on night-0 manipulation checks is provisional (8) until the clean
medians fix it at 50% of the batch median tool-call count (protocol 5.2).

## Morning

```
make ops        # operations ONLY: completions, throttles, failures,
                # malformed traces. Gate metrics are computed exactly once,
                # when the planned matrix completes (no peeking).
```

## Interruptions

- Supervisor killed (crash, reboot, Ctrl-C, kill -9): just run `make queue`
  again. Stale running jobs are reset to pending at startup; nothing is lost
  or duplicated.
- Throttled window: jobs marked throttled back off exponentially (capped at
  30 minutes) and requeue automatically. The queue never dies; it waits.
- HALT on CLI version change: the matrix must finish on one version; if the
  CLI updated itself, pin/reinstall the recorded version
  (`npm install -g @anthropic-ai/claude-code@<pinned>`) AND disable
  auto-update for the matrix duration (`"env": {"DISABLE_AUTOUPDATER": "1"}`
  in `~/.claude/settings.json`) before resuming. Fired live 2026-06-10
  (2.1.170 -> 2.1.172 auto-update; guard halted before claiming any job).

## When the matrix closes

- Re-enable CLI auto-update: remove `DISABLE_AUTOUPDATER` from the env block
  of `~/.claude/settings.json`, then update Claude Code freely. The version
  pin in `runs/queue.sqlite` meta is released with the matrix; record the
  closing CLI version in the wrap-up notes.
