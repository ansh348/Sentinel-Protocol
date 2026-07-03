# tau-bench port notes

Infrastructure-only fault-injection harness for tau-bench's retail domain. Companion to the
scoping note at `docs/taubench_scoping_memo.md`. This file records the pinned dependency, the
load-bearing invariants, and the deliberate boundaries of what is built.

## Pinned dependency

- **Repo:** github.com/sierra-research/tau-bench
- **Commit (exact pin):** `59a200c6d575d595120f1cb70fea53cef0632f6b` (default branch `main`,
  dated 2026-03-18).
- **License:** **MIT** (`LICENSE` at the pinned tree; `spdx_id: MIT`). Compatible with use as
  a pinned dependency; not vendored or forked.
- **Install (in `requirements.txt`):**
  `tau_bench @ git+https://github.com/sierra-research/tau-bench.git@59a200c6d575d595120f1cb70fea53cef0632f6b`
- **Windows install caveat:** tau-bench's `setup.py` does `open("README.md").read()` with no
  encoding, so on Windows the build fails under the cp1252 default codec
  (`UnicodeDecodeError: 'charmap' ... byte 0x8f`). Install under Python UTF-8 mode:
  `PYTHONUTF8=1 pip install -r requirements.txt`. This is a build-time issue in the upstream
  `setup.py` only; nothing is patched or vendored.
- Installing pulls a heavy transitive tree (openai, anthropic, litellm, mistralai,
  google-generativeai, numpy, tiktoken, …). None of it is exercised at run time by this
  harness — the zero-LLM guard (below) blocks the only model entry point.

## The armed-flag invariant (load-bearing)

> ARMED is set at episode start and is GUARANTEED cleared before any `calculate_reward`
> execution; reward-replay steps are structurally incapable of passing through fault logic.

Why it matters (Landmine 1, verified): `Env.calculate_reward()` recomputes the ground truth
live — it reloads clean data and **replays `task.actions` through `self.step`** — so any fault
still armed at reward time corrupts the oracle. A `surface_removal` of a write tool, left
armed, makes a blind baseline (one that never did the write) hash-match the corrupted oracle
and **false-pass**. See `docs/taubench_scoping_memo.md` §3.

How it is guaranteed (`extensions/taubench/faulted_env.py`):
1. Pristine `tools_map`/`tools_info` are snapshotted at construction.
2. Faults are applied only inside the wrapper's `step()`; the oracle's internal replay uses
   the inner env's own `step` (base `Env.step`, never the wrapper), so fault-arming code is
   off the oracle path by construction.
3. The inner env's bound `calculate_reward` is wrapped so **every** caller (including
   tau-bench's own `step()` on `done=True`) first disarms — restores pristine containers,
   clears `armed` — then asserts the pristine state before delegating.

Unit-tested both ways: `test_armed_false_pass` (reproduce the false pass, then show the disarm
hook fixes it) and `test_disarm_guarantee` (the guard trips while armed; production reward
always disarms first).

## Scoring-layer decision

**Native tau-bench reward is diagnostic only; it is never the verdict.** `calculate_reward`
scores a database-state hash match. But `transfer_to_human_agents` is a terminate tool that
mutates nothing, so a *justified* stop — the monitor correctly refusing to proceed under a
fault, which is the success case for a monitor benchmark — scores **0 by construction**
(Landmine 3; `docs/taubench_scoping_memo.md` §5). Native reward is therefore used only for
oracle sanity and for detecting silent data divergence. The verdict metrics — detection,
clean false-interrupt rate, overhead vs. cap, and the justified-stop credit that native reward
cannot express — are defined at **pre-registration time** (the August window), against frozen
predictions, not here.

## Cost-metering bug (do not read tau-bench cost fields)

**Landmine 2 (verified):** tau-bench's user simulator tracks cost by **assignment, not
accumulation**. In `tau_bench/envs/user.py`, three user classes (`LLMUserSimulationEnv`,
`ReactUserSimulationEnv`, `VerifyUserSimulationEnv`) each do
`self.total_cost = res._hidden_params["response_cost"]` — so `user.get_total_cost()`, surfaced
as `EnvInfo.user_cost`, reports only the **last** call's cost, not the episode sum. Never read
tau-bench's cost fields for measurement. The harness's `CostMeter`
(`extensions/taubench/instrumentation.py`) is the sole cost authority and documents this in its
docstring; per-call token/cost records attach there later.

## What this harness deliberately does NOT contain (and why)

No check-writer, no monitor, no pass/fail bars or thresholds, no pre-registration text, and no
qualification or comparative runs — because those are gated to the **August** pre-registration
window (**kill date September 5**); this is the deterministic, zero-LLM substrate only (fault
injection, the armed-flag invariant, instrumentation, and oracle-replay self-tests).

## Zero-LLM guarantee

The harness makes no model calls. `MockRetailDomainEnv` is constructed with
`user_strategy="human"` (the default LLM strategy calls `litellm.completion()` in its
`__init__`) and its user is replaced with `NullUser`. The test suite installs a
`litellm.completion` stub that **raises** (`extensions/taubench/tests/conftest.py`), bound
before `tau_bench.envs.user` resolves its `from litellm import completion`, so any stray model
call fails loudly. `test_no_llm` asserts the guard is armed and that a full episode triggers
zero completions.

## Running the self-tests

```
PYTHONUTF8=1 python -m pytest extensions/taubench/tests -v      # or: make taubench
```

Expected: 6 passed (5 test files; `test_no_llm` has two). `test_oracle_sanity` replays all 113
nonempty retail test tasks through the real tau-bench tools (≈1 min).
