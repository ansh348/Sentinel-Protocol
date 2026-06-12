# Matrix-close checklist — execution record (2026-06-12)

Per RUNBOOK "When the matrix closes", deliberately deferred until after the
Phase 1 decision memo (decisions/decision_memo_phase1.md, commit e808862).

| item | status | detail |
|---|---|---|
| Closing CLI version recorded | **DONE** | 2.1.170 (Claude Code) — matches the matrix pin wire-to-wire; the queue.sqlite meta pin is released with the matrix as of this record. |
| `TRIPWIRE_CLAUDE_BIN` unset | **DONE (nothing to unset)** | Verified absent from both User and Machine persistent environments; it was only ever a per-shell export per RUNBOOK, and no supervisor shell is running. |
| Re-enable CLI auto-update (remove `DISABLE_AUTOUPDATER` from the env block of `~/.claude/settings.json`) | **DONE (2026-06-12, operator-authorized)** | Initially refused by the operator's permission layer as unrequested; executed on the operator's explicit instruction. Env block removed; auto-update live again. |
| Remove the matrix-pinned npm install | **DONE (2026-06-12, operator-authorized)** | `npm uninstall -g @anthropic-ai/claude-code` removed 2 packages; daily CLI resolves to the native install (`~/.local/bin/claude.exe`), which was then updated 2.1.172 → **2.1.175** via `claude update`. |

All checklist items complete. The matrix is fully closed: pin released at
2.1.170 (the wire-to-wire matrix version), post-close daily CLI now 2.1.175.
