"""Shared JSONL trace writer: the Section 6 event schema (BUILD_BRIEF), from day one.

Every event carries exactly: ts, run_id, seed, system, task_id, actor, event_type,
payload. Events for LLM calls additionally carry usage: {input_tokens, output_tokens,
cost_usd, model, session_id}. M6 metrics consume these events unchanged; if a metric
needs an event that is not emitted, fix the emitter, not the metric.

`ts` is wall-clock and appears ONLY in trace events, never in world-server response
payloads (determinism amendment: same-seed runs are byte-identical with no exclusion
lists). Metrics are defined over tool-call counts, not timestamps.
"""
from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Traces are the publishable artifact (FSE artifact evaluation), so credentials
# must never appear in runs/*.jsonl. This guard fails loud at emit time rather
# than redacting silently; world tokens are tok_<hex>, so no false positives.
CREDENTIAL_PATTERN = re.compile(r"sk-ant-[A-Za-z0-9_\-]{16,}")

EVENT_TYPES = frozenset({
    "run_start",
    "plan",
    "compile",
    "tripwire_set",
    "worker_start",
    "tool_call",
    "tool_response",
    "injection_fired",
    "tripwire_fire",
    "escalation",
    "judge_verdict",
    "interrupt",
    "pause",
    "revalidation",  # S3 only
    "replan",
    "redispatch",
    "worker_end",
    "aggregate",
    "success_check",
    "run_end",
    "throttle",
    "error",
    # M3 amendment 2: emitted when a tripped worker keeps calling tools after
    # STOP_AND_ESCALATE; the middleware hard-stops it with a 409.
    "worker_noncompliance",
    # D7: a fire/escalation eaten by the NOISE interrupt policy — either a
    # matcher-suppressed match (where=matcher) or an escalation deduped by
    # (tripwire_id, evidence_hash) without re-judgment (where=conductor).
    "suppressed_refire",
    # M4 condition 1: in unjudged routes (S2/S4) the orchestrator may judge a
    # raw anomaly itself and dismiss it instead of replanning.
    "dismissal",
    # D20 strict reply reader: an orchestrator reply that parsed as JSON but
    # failed strict schema validation (each rejection precedes its re-prompt
    # turn, so per-system dialect-error rates and costs are measurable).
    "reply_rejected",
    # v2 probe side channel (v6.1 §11.9 amendment #1; prereg_1b): probe
    # traffic is separately metered and rides its own event pair — it never
    # advances the tool-call counter, so tool_call/tool_response would lie.
    # Emitted only on probe_channel-enabled (1b) runs; banked traces have none.
    "probe_call",
    "probe_response",
    # v2 corroboration layer (design §2.2; ruling D28): the persistence decision
    # for each surface, recorded so a run is byte-replayable. Deterministic, no
    # LLM. Emitted only under the v2 flag; banked Phase-1 traces have none.
    "corroboration",
    # v2 UNCOVERED valve (D29 §4; D31): a load-bearing surface that could not be
    # certified — an unreachable sweep target, or a write-surface footprint with no
    # checkable expected post-state — recorded LOUDLY (caution; scored by C7), never
    # silently dropped. Emitted only under the v2 flag; banked traces have none.
    "uncovered",
})

USAGE_FIELDS = ("input_tokens", "output_tokens", "cost_usd", "model", "session_id")


class TraceWriter:
    """Append-only JSONL writer; one event per line, flushed per line so a killed
    process never leaves a partially buffered trace (overnight-queue requirement)."""

    def __init__(self, path: str | Path, *, run_id: str, seed: int, system: str,
                 task_id: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id
        self.seed = seed
        self.system = system
        self.task_id = task_id
        self._lock = threading.Lock()
        self._fh = open(self.path, "a", encoding="utf-8")

    def emit(self, *, actor: str, event_type: str, payload: dict[str, Any],
             usage: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        if event_type not in EVENT_TYPES:
            raise ValueError(f"unknown event_type: {event_type!r}")
        event: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "seed": self.seed,
            "system": self.system,
            "task_id": self.task_id,
            "actor": actor,
            "event_type": event_type,
            "payload": payload,
        }
        if usage is not None:
            missing = [f for f in USAGE_FIELDS if f not in usage]
            if missing:
                raise ValueError(f"usage payload missing fields: {missing}")
            event["usage"] = usage
        line = json.dumps(event, separators=(",", ":"), ensure_ascii=False)
        if CREDENTIAL_PATTERN.search(line):
            raise ValueError(
                "credential-like material in trace event; traces are publishable "
                "artifacts and must never contain secrets (refusing to write)")
        with self._lock:
            self._fh.write(line + "\n")
            self._fh.flush()
        return event

    def close(self) -> None:
        with self._lock:
            if not self._fh.closed:
                self._fh.close()


def read_trace(path: str | Path) -> list[dict[str, Any]]:
    """Parse a JSONL trace back into a list of events (used by tests and analysis)."""
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def read_run(run_dir: str | Path) -> list[dict[str, Any]]:
    """Merge every *.jsonl trace in a run directory, ordered by ts. The world
    server (separate process) and the conductor write separate files to avoid
    cross-process interleaved appends; the event schema is identical and M6
    metrics consume the merged stream."""
    events: list[dict[str, Any]] = []
    for path in sorted(Path(run_dir).glob("*.jsonl")):
        events.extend(read_trace(path))
    events.sort(key=lambda e: e["ts"])
    return events
