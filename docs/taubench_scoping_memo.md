# tau-bench fault-injection scoping memo

**Status:** research note (scoping). **Provenance:** authored from the tau-bench port
scoping brief and verified line-by-line against tau-bench source pinned at commit
`59a200c6d575d595120f1cb70fea53cef0632f6b` (MIT). This file records the findings the
harness under `extensions/taubench/` encodes; it is *not* a frozen pre-registration and
defines no bars, thresholds, or verdict logic. All fault parameters below (F1–F5) are
**CANDIDATE** and **UNQUALIFIED** — placeholders for a later pre-registration window, not
frozen quantities.

**Scope discipline:** this scoping exercise and the harness it specifies make **zero LLM
calls**. Everything here is deterministic oracle-replay reasoning over ground-truth action
sequences. Anything that would require a model call is out of scope by construction.

---

## 1. Purpose

Assess whether the TripwireBench fault-injection pattern (arm a fault mid-episode, watch
whether a monitor notices, score against a pre-committed rubric) ports to
`tau-bench` (github.com/sierra-research/tau-bench) as a possible second testbed / extension
arm for the FSE paper. This memo establishes the injection **seam**, the **landmines** that
make a naive port produce false results, and the **native-reward** limits that force a
separate scoring layer.

The verdict of the scoping exercise: **the port is feasible**, the seam is clean, and three
landmines must be neutralized structurally before any measurement. The harness built from
this memo is infrastructure only — it deliberately contains no check-writer, no runs, no
bars (see §10).

## 2. The seam (verified)

Every tool call in tau-bench routes through a single choke point. In
`tau_bench/envs/base.py`, `Env.step(action)` dispatches:

```python
observation = self.tools_map[action.name].invoke(data=self.data, **action.kwargs)
```

Key structural facts:

- `self.data` is the **entire world state** — a plain `dict` loaded by `data_load_func()`
  (`retail/data/load_data`) and reloaded deterministically on every `reset()`.
- `self.tools_map` maps a tool name to a **`Tool` class** (not an instance);
  `Tool.invoke` and `Tool.get_info` are `@staticmethod`s. Read tools return a JSON string
  and never mutate `data`; write tools mutate `data` in place and return a confirmation
  string.
- `self.tools_info` is the parallel list of OpenAI-style function schemas
  (`[tool.get_info() for tool in tools]`), i.e. the tool surface the agent *sees*.
- `respond` actions bypass `tools_map` entirely (they go to the user simulator), so a
  tool-call counter must exclude them.

**Consequence for injection:** a fault is a controlled edit to `tools_map` / `tools_info`.
No tau-bench source needs modification — the wrapper mutates these two containers on the
live instance and restores them. This is the whole seam. Four primitives cover the useful
edits (§7).

## 3. Landmine 1 — the oracle-replay false pass (verified)

`Env.calculate_reward()` (`base.py`) does **not** score against a cached ground-truth hash.
It recomputes the ground truth live:

```python
data_hash = self.get_data_hash()          # hash of the episode's final data
self.data = self.data_load_func()          # reload clean data
for action in self.task.actions:           # replay the ground-truth actions...
    if action.name not in self.terminate_tools:
        self.step(action)                  # ...THROUGH self.step -> tools_map[...].invoke
gt_data_hash = self.get_data_hash()
r_actions = (data_hash == gt_data_hash)
```

The oracle replay goes through the **same `tools_map`** the episode used. Therefore **any
fault still armed at reward time corrupts the ground truth itself.**

Demonstrated failure: arm `surface_removal` on the write tool a task depends on, then let a
blind baseline (an agent that never performed the write) reach reward. The blind episode's
`data_hash` is the clean/initial hash. The oracle replay tries to re-apply the write, but
the tool is gone, so the write no-ops and `gt_data_hash` collapses to the *same* clean hash.
`data_hash == gt_data_hash` → **the blind baseline scores as correct.** A false pass, entirely
manufactured by an armed fault leaking into the scorer.

**Structural fix (the armed-flag invariant, §6):** the reward computation must be
*structurally incapable* of running through fault logic. The wrapper disarms — restores
pristine `tools_map`/`tools_info` and clears the `armed` flag — before `calculate_reward`
executes, by wrapping the inner env's bound `calculate_reward`. Because the internal oracle
replay calls the inner env's own `step` (never the wrapper's fault-arming `step`), and
because the persistent `tools_map` mutation is reverted first, no fault can reach the oracle.
This is asserted in the trace and unit-tested directly (`test_armed_false_pass`,
`test_disarm_guarantee`).

## 4. Landmine 2 — cost metering by assignment, not accumulation (verified)

The user simulator tracks cost with an **assignment**, not a running sum. In
`tau_bench/envs/user.py`, three user classes (`LLMUserSimulationEnv`,
`ReactUserSimulationEnv`, `VerifyUserSimulationEnv`) each contain:

```python
self.total_cost = res._hidden_params["response_cost"]   # overwrites, does not add
```

So `user.get_total_cost()` — surfaced as `EnvInfo.user_cost` on the terminal step — reports
only the **last** call's cost, not the episode total. **Never read tau-bench's cost fields
for measurement.** The harness carries an independent cost meter
(`extensions/taubench/instrumentation.py::CostMeter`) as the sole cost authority; this bug is
documented in that class's docstring so no later contributor re-imports the field.

## 5. Landmine 3 — native reward is diagnostic only (verified)

`transfer_to_human_agents` is registered as a **terminate tool**
(`MockRetailDomainEnv.__init__` sets `self.terminate_tools = ["transfer_to_human_agents"]`)
and performs no data mutation. The action check in `calculate_reward` excludes terminate
tools from the oracle replay, so a run that *correctly* escalates/stops instead of completing
the task will have an episode `data_hash` that does **not** match the completed-task
`gt_data_hash` → **native reward 0 by construction.**

This is exactly backwards from what a monitor benchmark wants: a *justified* stop (the monitor
correctly refused to proceed under a fault) is the success case, and native reward scores it
as failure. **Native reward is therefore a diagnostic signal only** (useful for oracle-sanity
and for detecting silent data divergence), never the verdict. Our own scoring layer —
detection, clean false-interrupt rate, overhead, and the justified-stop credit that native
reward cannot express — is defined at pre-registration time in the August window, not now.

## 6. The armed-flag invariant (design)

From §3 the load-bearing invariant:

> **ARMED is set at episode start and is GUARANTEED cleared before any `calculate_reward`
> execution. Reward-replay steps are structurally incapable of passing through fault logic.**

Implementation (see `extensions/taubench/faulted_env.py`):

1. At construction the wrapper snapshots the pristine `tools_map` and `tools_info`.
2. `reset()` restores pristine containers, zeroes the tool-call counter, and sets `armed=True`.
3. Faults are applied only inside the wrapper's `step()` (fault-arming code the inner env's
   oracle replay never calls).
4. The inner env's bound `calculate_reward` is wrapped so that **every** caller — including
   tau-bench's own `step()` on `done=True` — first triggers `_disarm()` (restore pristine
   containers, clear `armed`), then asserts `armed is False` and `tools_map == pristine`
   before delegating to the original.

The guarantee is tested both ways: the corruption is reproduced with the guard bypassed
(`test_armed_false_pass`, `test_disarm_guarantee`) and shown to vanish with the guard active.

## 7. Fault primitives (design)

Four declarative primitives, each a controlled edit to the seam of §2. All are
JSON-serializable (`FaultConfig` dataclass). A fault fires when the tool-call counter reaches
its `trigger_n` (no default baked in) and is **sticky** for the rest of the episode.

- **(a) `read_transform`** — proxy a named tool in `tools_map`; transform its returned
  observation string. **Never touches `env.data`.** Used for silent read corruption.
- **(b) `surface_removal`** — remove a named tool from `tools_map` **and** its schema from
  `tools_info`, so the capability disappears from the agent's *view*, not merely its dispatch.
- **(c) `error_injection`** — a named tool returns a configured error string (e.g.
  authorization-expired) instead of executing.
- **(d) `list_truncation`** — a `read_transform` specialization: truncate list-valued fields
  in an observation to their first element(s).

Only `read_transform`/`list_truncation` re-invoke the pristine tool for the "pre-transform"
trace field, and only when the target is a read-only tool, so instrumentation never
double-applies a write.

## 8. Instrumentation (design)

- **JSONL episode trace** — one record per action: name, kwargs, counter, `armed`, pre- and
  post-transform observation, fault-fire events, data hash at reset and at done, wall time.
- **Independent cost meter** — records call counts, asserts zero LLM spend, documents
  Landmine 2; the attach point for per-call token/cost records added later.
- **Probe side channel** — invokes a **whitelisted read-only** tool directly against
  `env.data`, bypassing the episode counter (and, when `probe_sees_faults=False`, the armed
  fault logic; default `True`, since a live probe should read the faulted world). Write tools
  are refused by name. Logged to a separate trace stream.
- **Opening-reading helper** — snapshots a list of `(tool, kwargs)` observations before the
  first agent action, stored in the trace.

## 9. Candidate faults (UNQUALIFIED)

Five candidate configs ship under `extensions/taubench/faults/` as worked examples. Each
carries a header comment marking it CANDIDATE / UNQUALIFIED / parameters-not-frozen. They
span all four primitives; targets are real retail tools.

- **F1 — read_transform (price swap).** `get_product_details`: swap a price value in the
  returned JSON. The agent reads a wrong price; the database is untouched (episode data hash
  equals the clean oracle hash). The canonical "silent read corruption."
- **F2 — surface_removal (write capability).** Remove `cancel_pending_order` from
  `tools_map`/`tools_info`. Also the Landmine-1 demonstrator: armed through reward, it
  manufactures a false pass; disarmed, the oracle is intact.
- **F3 — error_injection (write refusal).** `modify_pending_order_items` returns an
  authorization-expired error string instead of executing — a silent write refusal.
- **F4 — list_truncation (order/user detail lists).** See §9.5.
- **F5 — error_injection (read outage).** `get_order_details` returns a
  "record temporarily unavailable" error string — a read-side outage distinct from F3's
  write refusal.

### 9.5 F4 re-targeting

F4 was originally scoped as a product-listing truncation. It is **re-targeted to the
order/user detail lists**, which are the consequential list-valued surfaces for retail tasks:
`get_user_details` returns a user record whose `orders` field is a list of order ids, and
`get_order_details` returns an order whose `items` (and fulfillment) fields are lists.
Truncating these to their first element(s) models a monitor/tool that silently drops rows the
agent needs to reason correctly about which order/item to act on — a failure mode with direct
task consequences, unlike truncating a browse-only product catalog. `truncate_fields` names
the fields; `keep` sets how many elements survive. Parameters CANDIDATE / not frozen.

## 10. What this harness deliberately does not contain

No check-writer, no monitor, no pass/fail bars, no thresholds, no pre-registration text, no
qualification or comparative runs, and no verdict logic. Those are gated to the **August**
pre-registration window (kill date **September 5**). This harness is the deterministic,
zero-LLM substrate only: fault injection, the armed-flag invariant, instrumentation, and the
oracle-replay self-tests that prove the substrate is sound. The scoring layer (detection,
clean false-interrupt rate, overhead vs. cap, justified-stop credit) is defined then, against
frozen predictions, not now.
