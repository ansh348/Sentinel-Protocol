# Matrix-close checklist — execution record (2026-06-12)

Per RUNBOOK "When the matrix closes", deliberately deferred until after the
Phase 1 decision memo (decisions/decision_memo_phase1.md, commit e808862).

| item | status | detail |
|---|---|---|
| Closing CLI version recorded | **DONE** | 2.1.170 (Claude Code) — matches the matrix pin wire-to-wire; the queue.sqlite meta pin is released with the matrix as of this record. |
| `TRIPWIRE_CLAUDE_BIN` unset | **DONE (nothing to unset)** | Verified absent from both User and Machine persistent environments; it was only ever a per-shell export per RUNBOOK, and no supervisor shell is running. |
| Re-enable CLI auto-update (remove `DISABLE_AUTOUPDATER` from the env block of `~/.claude/settings.json`) | **PENDING — MANUAL** | The operator's permission layer (correctly) refused the assistant write access to its own settings file. Operator action: delete the `"env": {"DISABLE_AUTOUPDATER": "1"}` block from `~/.claude/settings.json`, then update freely. |
| Remove the matrix-pinned npm install | **PENDING — MANUAL** | Same permission boundary (global toolchain change). Operator action: `npm uninstall -g @anthropic-ai/claude-code` — the daily CLI then resolves back to the native install (`~\.local\bin\claude.exe`). |

Both pending items are operator-side environment changes with no bearing on
the banked matrix, the verdict, or any committed artifact. Once executed, the
matrix is fully closed.
