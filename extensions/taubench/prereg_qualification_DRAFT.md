# tau-bench qualification — mini pre-registration (DRAFT)

**Status:** DRAFT v0.1, authored 2026-07-03. NOT RATIFIED. No episode governed by this
document may run before a separate, dated ratification commit (A7 pattern,
cf. checkpoint 7a3807fe).

## Scope & provenance

This draft defines the **qualification** phase for the tau-bench port: which fault–task pairs
are admissible into the August measurement window, how they are judged, and the spend /
iteration discipline around them. It governs no monitor arm and authorizes no run. It inherits
the qualification rule from TripwireBench and the landmine / invariant findings from
`docs/taubench_scoping_memo.md` and `extensions/taubench/PORT_NOTES.md`.

`[DECISION]` markers flag every choice reserved for the author. They remain **open until
ratification** — resolving them is what the ratification commit does.

## 1. Qualification rule (inherited from TripwireBench)

A fault–task pair **qualifies** iff:

- every **injected** episode **fails** the pinned plain baseline, and
- every matched **clean** (no-fault) episode **passes** the pinned plain baseline,

across **k = `[DECISION — suggest 3]`** trials each.

Scoring for qualification uses **tau-bench native reward**. This is valid here because the
plain baseline carries **no monitor**: native reward measures only whether the ground-truth
database state was reached, which is exactly the "did the fault break the task" signal that
qualification needs. (Native reward is **not** valid for monitor arms, where a justified stop
scores 0 by construction — see PORT_NOTES, "Scoring-layer decision.")

Intent: qualification establishes that a fault is *consequential and clean* — it reliably
breaks the task when injected and is invisible when absent — **before** any monitor is ever
measured against it.

## 2. Pinned plain baseline

- Agent strategy: tau-bench **tool_calling_agent** (`--agent-strategy tool-calling`).
- Agent sampling temperature: **0.0**.
- Agent model: **`[DECISION]`** (provider + model id).
- User simulator model: **`[DECISION]`** (provider + model id).
- User simulator strategy: **llm** (stock).
- User simulator temperature: **stock (unset)** — inherit tau-bench's default; do not pin.
- Environment: retail, `task_split = test`.
- `max_num_steps`: stock (30) unless a `[DECISION]` overrides.

The plain baseline is frozen at ratification and used **identically** for clean and injected
episodes; only the armed fault differs between the two arms of a cell.

## 3. Trigger convention

Per-task trigger count **N = ceil(median clean tool-call count / 2)**, where the medians are
taken from the **clean calibration runs that open the August window** — not from tonight's
smoke, and not from any pre-ratification run.

Rationale: firing at half the median clean tool-call count places the fault **mid-episode**,
inside the agent's observation window, so a monitor still has episode left in which to react.
This is the DEPENDENCY_VERSION wall lesson: a fault that fires after the agent has effectively
finished is unobservable and mis-scores the monitor. N is computed **per task** (not global)
because clean tool-call counts vary widely across retail tasks (census: ground-truth action
counts range from 0 to double digits).

## 4. Fault design iteration budget

- **Max 2 designs per fault** (F1–F5). A "design" is a parameterization + target tool; changing
  the target tool or the transform counts as a new design.
- A design that fails to qualify is **reported as a finding** in the departure log — **never
  deleted** (D23 culture: failed designs are data, not waste).
- If both designs for a fault fail to qualify, that fault is **retired for the window** with its
  two failures recorded; it is not silently dropped.

## 5. Spend cap (qualification phase)

- Qualification-phase spend cap: **`[DECISION — suggest $40]`** of the **$150** study envelope.
- Metered by **our** CostMeter (agent + user-sim split); never tau-bench's `get_total_cost`
  (assign-not-accumulate bug, PORT_NOTES).
- Enforced **in code**: the qualification loop aborts when projected spend would exceed the cap
  — the same mechanism proven in tonight's $2 smoke.

**Armed-flag invariant as a validity condition.** A qualification result is valid only if the
armed-flag invariant held for every episode — i.e. no fault was armed during any
`calculate_reward` execution (disarm hook, PORT_NOTES §"armed-flag invariant"). An episode in
which the invariant is violated is **void and re-run, not scored**: a still-armed
`surface_removal` collapses the oracle and manufactures a false pass, which would silently
corrupt qualification.

## 6. Candidate set

F1–F5 exactly as committed in `extensions/taubench/faults/`:

- **F1** `read_transform` — price swap, `get_product_details`
- **F2** `surface_removal` — `cancel_pending_order`
- **F3** `error_injection` — `modify_pending_order_items`, authorization-expired
- **F4** `list_truncation` — `get_user_details.orders` (sibling `get_order_details.items`, memo §9.5)
- **F5** `error_injection` — `get_order_details`, read outage

All fault **parameters** (`trigger_n`, `find`/`replace`, error strings, `truncate_fields`/`keep`,
target tool) are **explicitly still open** and are frozen only at ratification. The committed
files are CANDIDATE / UNQUALIFIED examples.

## `[DECISION]` summary (to resolve at ratification)

| Where | Decision | Suggested |
|-------|----------|-----------|
| §1 | k trials per cell (clean and injected) | 3 |
| §2 | agent model (provider + id) | open |
| §2 | user simulator model (provider + id) | open |
| §5 | qualification-phase spend cap | $40 of $150 |

## What this draft does NOT authorize

No episode, clean or injected; no qualification; no fault arming; no monitor measurement.
Ratification is a **separate, dated commit** (A7 pattern). Until then this is text only.
