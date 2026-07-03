"""Live plumbing smoke for the tau-bench plain baseline. **MAKES REAL MODEL CALLS.**

Runs up to N clean episodes (no faults) of the STOCK plain baseline (tool_calling_agent,
temp 0.0) against a FaultedEnv wrapped with an EMPTY fault set -- proving the wrapper is
inert in the live path. Both call sites (agent + user simulator) are metered by OUR
CostMeter off the litellm response; tau-bench's get_total_cost is never read (PORT_NOTES).

A hard USD cap is enforced IN CODE via a projected-cost guard inside the litellm wrapper:
before every call, if (spent + estimate) would exceed the cap it raises BudgetExceeded, which
aborts the episode loop. Nothing here arms a fault; `fault_active` is asserted False every
episode.

Run from the repo root:
    PYTHONUTF8=1 python -m extensions.taubench.live_smoke
Env overrides: SMOKE_CAP, SMOKE_N, SMOKE_AGENT_MODEL, SMOKE_AGENT_PROVIDER,
SMOKE_USER_MODEL, SMOKE_USER_PROVIDER, SMOKE_MAX_STEPS, SMOKE_OUT.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]  # extensions/taubench/live_smoke.py -> repo root
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# --- credentials: load ../.env (parent of the repo root) ---------------------------------
from dotenv import load_dotenv  # noqa: E402

load_dotenv(dotenv_path=str(_ROOT.parent / ".env"))

import litellm  # noqa: E402

from extensions.taubench.instrumentation import CostMeter  # noqa: E402

CAP = float(os.environ.get("SMOKE_CAP", "2.00"))
N_EPISODES = int(os.environ.get("SMOKE_N", "3"))
MAX_STEPS = int(os.environ.get("SMOKE_MAX_STEPS", "30"))  # stock tau-bench default
SEED_EST = 0.05  # conservative USD estimate for the first call, before any is observed
USER_MODEL = os.environ.get("SMOKE_USER_MODEL", "gpt-4o")
USER_PROVIDER = os.environ.get("SMOKE_USER_PROVIDER", "openai")
OUT = os.environ.get(
    "SMOKE_OUT",
    str(Path(os.environ.get("TMPDIR", "")) / "smoke_results.json") if os.environ.get("TMPDIR")
    else str(_ROOT / "runs" / "taubench_smoke" / "smoke_results.json"),
)
TRACE_DIR = _ROOT / "runs" / "taubench_smoke"


class BudgetExceeded(RuntimeError):
    pass


def _model_priced(model: str) -> bool:
    """True iff litellm knows a price for `model` (so response_cost will populate)."""
    try:
        if model in litellm.model_cost:
            info = litellm.model_cost[model]
            return bool(info.get("input_cost_per_token"))
    except Exception:
        pass
    try:
        info = litellm.get_model_info(model)
        return bool(info and info.get("input_cost_per_token"))
    except Exception:
        return False


def pick_haiku_model() -> str | None:
    """Pick a Haiku-class Claude model that litellm has pricing for (so the cap can bind).
    Prefer newer, fall back to older stable ids."""
    override = os.environ.get("SMOKE_AGENT_MODEL")
    if override:
        return override
    preference = [
        "claude-haiku-4-5", "claude-haiku-4-5-20251001",
        "claude-3-5-haiku-latest", "claude-3-5-haiku-20241022",
        "claude-3-haiku-20240307",
    ]
    for m in preference:
        if _model_priced(m):
            return m
    # last resort: any anthropic haiku key in the cost map with a price
    for k, v in litellm.model_cost.items():
        if "haiku" in k.lower() and v.get("litellm_provider") == "anthropic" and v.get("input_cost_per_token"):
            return k
    return None


# --- metering wrapper: tags agent vs user by the presence of `tools`; enforces the cap ----
_real_completion = litellm.completion
METER = CostMeter(strict=False)


def metered_completion(*args, **kwargs):
    role = "agent" if kwargs.get("tools") else "user"
    est = METER.max_call_cost if METER.n_llm_calls > 0 else SEED_EST
    projected = METER.llm_cost + est
    if projected > CAP:
        raise BudgetExceeded(
            f"projected ${projected:.4f} (spent ${METER.llm_cost:.4f} + est ${est:.4f}) "
            f"> cap ${CAP:.2f}"
        )
    res = _real_completion(*args, **kwargs)
    hp = getattr(res, "_hidden_params", {}) or {}
    cost = hp.get("response_cost")
    if cost is None:
        try:
            cost = litellm.completion_cost(completion_response=res)
        except Exception:
            cost = 0.0
    usage = getattr(res, "usage", None)
    pt = getattr(usage, "prompt_tokens", 0) or 0
    ct = getattr(usage, "completion_tokens", 0) or 0
    METER.record_llm_call(role, cost or 0.0, pt, ct, model=kwargs.get("model"))
    if METER.llm_cost >= CAP:
        raise BudgetExceeded(f"spent ${METER.llm_cost:.4f} >= cap ${CAP:.2f}")
    return res


# Install the wrapper on litellm AND on the bound names tau-bench imported.
litellm.completion = metered_completion
import tau_bench.envs.user as _tbu  # noqa: E402

_tbu.completion = metered_completion
import tau_bench.agents.tool_calling_agent as _tca  # noqa: E402

_tca.completion = metered_completion

from extensions.taubench.faulted_env import FaultedEnv  # noqa: E402
from tau_bench.agents.tool_calling_agent import ToolCallingAgent  # noqa: E402


def pick_short_tasks(n: int) -> list[int]:
    """The n retail test tasks with the fewest (but nonzero) ground-truth actions."""
    env = FaultedEnv(faults=[], task_index=0)  # deterministic construction, no model call
    sized = []
    for i, t in enumerate(env.inner.tasks):
        k = len([a for a in t.actions if a.name != "respond"])
        if k > 0:
            sized.append((k, i))
    sized.sort()
    return [i for _, i in sized[:n]]


def run_episode(task_index, agent_model, agent_provider, trace_path):
    before = METER.snapshot()
    t0 = time.monotonic()
    env = FaultedEnv(
        faults=[], task_index=task_index, live_user=True,
        user_model=USER_MODEL, user_provider=USER_PROVIDER, trace_path=trace_path,
    )
    agent = ToolCallingAgent(
        tools_info=env.inner.tools_info, wiki=env.inner.wiki,
        model=agent_model, provider=agent_provider, temperature=0.0,
    )
    result = agent.solve(env, task_index=task_index, max_num_steps=MAX_STEPS)
    wall = time.monotonic() - t0
    after = METER.snapshot()

    # Inertness: no fault ever armed/fired in the live path.
    assert not env.fault_active, "a fault was active in the clean live path"
    assert not env.trace.events("fault_fire"), "a fault_fire event appeared in a clean episode"
    assert env.inner.tools_map == env._pristine_map, "tools_map drifted in a clean episode"

    return {
        "task_index": task_index,
        "native_reward": result.reward,
        "agent_tool_calls": env.cost_meter.n_tool_calls,
        "agent_cost": round(after["agent_cost"] - before["agent_cost"], 6),
        "user_cost": round(after["user_cost"] - before["user_cost"], 6),
        "episode_cost": round(after["llm_cost"] - before["llm_cost"], 6),
        "llm_calls": after["n_llm_calls"] - before["n_llm_calls"],
        "wall_s": round(wall, 2),
        "trace_path": str(trace_path),
        "probe_trace_path": str(trace_path).replace(".jsonl", ".probe.jsonl"),
        "fault_active_ever": env.fault_active,
    }


def run_all(agent_model, agent_provider):
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    tasks = pick_short_tasks(N_EPISODES)
    episodes, blocker = [], None
    for task_index in tasks:
        if METER.llm_cost + SEED_EST > CAP:
            blocker = f"cap guard: stopped before task {task_index} (spent ${METER.llm_cost:.4f})"
            break
        trace_path = TRACE_DIR / f"ep_{task_index:03d}.jsonl"
        try:
            episodes.append(run_episode(task_index, agent_model, agent_provider, str(trace_path)))
        except BudgetExceeded as exc:
            episodes.append({"task_index": task_index, "aborted": "budget", "detail": str(exc)})
            blocker = f"budget cap hit on task {task_index}: {exc}"
            break
        except Exception as exc:  # auth / provider / upstream
            episodes.append({"task_index": task_index, "aborted": "error",
                             "error_type": type(exc).__name__, "detail": str(exc)[:400]})
            blocker = f"{type(exc).__name__} on task {task_index}: {str(exc)[:200]}"
            break
    return episodes, blocker, tasks


def main():
    agent_model = pick_haiku_model()
    agent_provider = os.environ.get("SMOKE_AGENT_PROVIDER", "anthropic")
    fell_back = False

    if agent_model is None or not _model_priced(agent_model):
        # Pricing misbehaves -> user-authorized fallback (option 3): gpt-4o-mini agent.
        agent_model, agent_provider, fell_back = "gpt-4o-mini", "openai", True

    episodes, blocker, tasks = run_all(agent_model, agent_provider)

    # If the FIRST episode died on an agent-side auth/provider error, fall back once.
    only_error = (
        not fell_back and len(episodes) == 1 and episodes[0].get("aborted") == "error"
        and agent_provider == "anthropic"
    )
    if only_error:
        agent_model, agent_provider, fell_back = "gpt-4o-mini", "openai", True
        # fresh meter is not reset (cap is cumulative for the phase); continue accounting
        episodes2, blocker2, _ = run_all(agent_model, agent_provider)
        episodes = episodes + [{"note": "fell back to gpt-4o-mini agent after anthropic error"}] + episodes2
        blocker = blocker2

    summary = {
        "cap_usd": CAP,
        "agent_model": agent_model, "agent_provider": agent_provider,
        "user_model": USER_MODEL, "user_provider": USER_PROVIDER,
        "fell_back_to_openai_agent": fell_back,
        "tasks_selected": tasks,
        "n_episodes_attempted": len([e for e in episodes if "task_index" in e]),
        "blocker": blocker,
        "totals": METER.snapshot(),
        "cap_ok": METER.llm_cost <= CAP,
        "episodes": episodes,
    }
    Path(OUT).parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
