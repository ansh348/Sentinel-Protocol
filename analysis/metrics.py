"""Protocol Section 6.1 operational definitions, computed from merged run
traces alone (trace.read_run). If a metric needs an event that is not emitted,
the emitter gets fixed, not the metric.

Attribution is by trace rule (the protocol's 20% manual audit happens outside
this module). A pause/interrupt is ATTRIBUTABLE to the injection iff, before
it, some tripwire_fire / escalation / tool_response event at or after the
injection counter touched the injected surface:

  endpoint_404, gate_skip_trap  -> path glob-matches params.path
  schema_drift (pricing)        -> path startswith /pricing
  schema_drift (repo_config)    -> path startswith /repo
  token_expiry                  -> response/evidence status == 401
  doc_contradiction             -> path == /docs/passages/<passage_id>

Wasted-work buckets (M6 amendment 1d: each token counted exactly once):
  window bucket    worker sessions active inside [injection, decision)
  discarded bucket aggregate-marked discarded workers NOT already in window
worker_noncompliance 409s carry ordinary tool_call events and are therefore
counted once via the tool-call window; suppressed_refire events carry no tool
call and appear only in the policy-accounting savings counters.
"""
from __future__ import annotations

from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any, Callable, Optional

from trace import read_run

PAUSE_DECISION_EVENTS = ("pause",)


def _usage_tokens(event: dict) -> int:
    usage = event.get("usage") or {}
    return (usage.get("input_tokens") or 0) + (usage.get("output_tokens") or 0)


def _usage_cost(event: dict) -> float:
    return (event.get("usage") or {}).get("cost_usd") or 0.0


def injection_info(events: list[dict]) -> Optional[dict]:
    for event in events:
        if (event["event_type"] == "injection_fired"
                and event["payload"].get("trigger") == "counter"):
            return {"ts": event["ts"],
                    "counter": event["payload"]["counter"],
                    "type": event["payload"]["injection"]["type"],
                    "params": {k: v for k, v in
                               event["payload"]["injection"].items()
                               if k != "type"}}
    return None


def surface_predicate(inj_type: str, params: dict) -> Callable[[str, Any], bool]:
    if inj_type in ("endpoint_404", "gate_skip_trap"):
        pattern = params.get("path", "*")
        # D31: the §4 gate is observed through its read-only SHADOW surface
        # (/repo/validate -> /repo/gate_status), so a gate_skip_trap interrupt the v2
        # stack raises on the shadow is attributable to the injection even when no
        # worker ever reached the gate itself. Instrument-level surface mapping (the
        # benchmark fact), not a category cue in the detector.
        _SHADOW = {"/repo/validate": "/repo/gate_status",
                   "/docs/validate": "/docs/gate_status"}
        shadow = _SHADOW.get(pattern)
        return lambda path, status: bool(path) and (
            fnmatchcase(path, pattern) or (shadow is not None and path == shadow))
    if inj_type == "schema_drift":
        prefix = "/repo" if params.get("target") == "repo_config" else "/pricing"
        return lambda path, status: bool(path) and path.startswith(prefix)
    if inj_type == "token_expiry":
        return lambda path, status: status == 401
    if inj_type == "doc_contradiction":
        target = f"/docs/passages/{params.get('passage_id', 'pol-returns')}"
        return lambda path, status: path == target
    return lambda path, status: False


def _touch_events(events: list[dict], inj: dict) -> list[dict]:
    """Events that touched the injected surface at/after the injection."""
    pred = surface_predicate(inj["type"], inj["params"])
    touches = []
    for event in events:
        p = event["payload"]
        if event["event_type"] in ("tripwire_fire", "tool_response"):
            if p.get("counter", -1) >= inj["counter"] and \
                    pred(p.get("path", ""), p.get("status")):
                touches.append(event)
        elif event["event_type"] == "escalation":
            ev = p.get("evidence") or {}
            path = ev.get("_path") or ev.get("path") or ""
            status = ev.get("_status") or ev.get("status")
            if event["ts"] >= inj["ts"] and pred(path, status):
                touches.append(event)
    return touches


def _attributable(events: list[dict], inj: Optional[dict],
                  candidate: dict) -> bool:
    if inj is None:
        return False
    return any(t["ts"] <= candidate["ts"] for t in _touch_events(events, inj))


def first_attributable_pause(events: list[dict],
                             inj: Optional[dict]) -> Optional[dict]:
    if inj is None:
        return None
    for event in events:
        if (event["event_type"] in PAUSE_DECISION_EVENTS
                and event["ts"] >= inj["ts"]
                and _attributable(events, inj, event)):
            return event
    return None


def _counter_at(events: list[dict], ts: str) -> int:
    counters = [e["payload"]["counter"] for e in events
                if e["event_type"] == "tool_call" and e["ts"] <= ts]
    return max(counters, default=0)


def time_to_detect(events: list[dict], inj: Optional[dict]) -> Optional[int]:
    """Global tool-call count between injection and the first attributable
    orchestrator-level pause. None when never detected."""
    pause = first_attributable_pause(events, inj)
    if pause is None:
        return None
    return max(0, _counter_at(events, pause["ts"]) - inj["counter"])


def _decision_ts(events: list[dict], inj: dict, system: str) -> str:
    """End of the wasted-work window: the first attributable pause; for S1,
    the first aggregate after injection; otherwise (no detection, M6
    amendment 1c) the end of the run."""
    pause = first_attributable_pause(events, inj)
    if pause is not None:
        return pause["ts"]
    if system == "S1":
        for event in events:
            if event["event_type"] == "aggregate" and event["ts"] >= inj["ts"]:
                return event["ts"]
    return events[-1]["ts"]


def wasted_work(events: list[dict], inj: Optional[dict]) -> dict:
    if inj is None:
        return {"tool_calls": 0, "tokens": 0, "usd": 0.0,
                "window_workers": [], "discarded_workers": []}
    system = events[0]["system"]
    end_ts = _decision_ts(events, inj, system)

    tool_calls = sum(
        1 for e in events if e["event_type"] == "tool_call"
        and e["payload"].get("counter", -1) >= inj["counter"]
        and e["ts"] < end_ts)

    starts = {e["actor"]: e["ts"] for e in events
              if e["event_type"] == "worker_start"}
    window_workers, tokens, usd = [], 0, 0.0
    worker_ends = {e["actor"]: e for e in events
                   if e["event_type"] == "worker_end"}
    for actor, end_event in worker_ends.items():
        started = starts.get(actor, end_event["ts"])
        if end_event["ts"] >= inj["ts"] and started <= end_ts:
            window_workers.append(actor)
            tokens += _usage_tokens(end_event)
            usd += _usage_cost(end_event)

    # discarded-partials term (M3 amendment 5 marking), exactly-once
    discarded: list[str] = []
    for event in reversed(events):
        if event["event_type"] == "aggregate" and "discarded" in event["payload"]:
            discarded = list(event["payload"]["discarded"])
            break
    discarded_new = [w for w in discarded if w not in window_workers]
    for actor in discarded_new:
        end_event = worker_ends.get(actor)
        if end_event is not None:
            tokens += _usage_tokens(end_event)
            usd += _usage_cost(end_event)
    return {"tool_calls": tool_calls, "tokens": tokens, "usd": round(usd, 6),
            "window_workers": sorted(window_workers),
            "discarded_workers": sorted(discarded_new)}


def interrupts(events: list[dict], inj: Optional[dict]) -> dict:
    total = [e for e in events if e["event_type"] == "interrupt"]
    false_count = sum(1 for e in total if not _attributable(events, inj, e))
    return {"total": len(total), "false": false_count,
            "fir": (false_count / len(total)) if total else None}


def policy_accounting(events: list[dict]) -> dict:
    refires = [e for e in events if e["event_type"] == "suppressed_refire"]
    by_where: dict[str, int] = {}
    for event in refires:
        where = event["payload"].get("where", "unknown")
        by_where[where] = by_where.get(where, 0) + 1
    return {
        "suppressed_refires": by_where,
        "worker_noncompliance": sum(
            1 for e in events if e["event_type"] == "worker_noncompliance"),
        "dismissals": sum(1 for e in events
                          if e["event_type"] == "dismissal"),
    }


def run_metrics(run_dir: str | Path) -> dict:
    events = read_run(run_dir)
    head = events[0]
    inj = injection_info(events)
    success = None
    for event in events:
        if event["event_type"] == "success_check":
            success = bool(event["payload"]["success"])
    total_cost = round(sum(_usage_cost(e) for e in events), 6)
    total_tokens = sum(_usage_tokens(e) for e in events)
    ttd = time_to_detect(events, inj)
    return {
        "run_id": head["run_id"], "task": head["task_id"],
        "system": head["system"], "seed": head["seed"],
        "injection": inj["type"] if inj else None,
        "injected": inj is not None,
        "detected": ttd is not None,
        "ttd_tool_calls": ttd,
        "wasted": wasted_work(events, inj),
        "interrupts": interrupts(events, inj),
        "policy": policy_accounting(events),
        "success": success,
        "total_cost_usd": total_cost,
        "total_tokens": total_tokens,
    }
