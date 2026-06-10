"""Single-run conductor: executes one (task, system, injection, seed) run end
to end — world server lifecycle, orchestrator plan, sentinel compile+arm,
worker dispatch, escalation/judge/pause/replan/redispatch, aggregation,
programmatic success check, complete JSONL trace.

M3 amendments wired here: recompile-on-replan (fresh TripwireSet per revised
plan, second compile cost in the trace), scope-aware pause (global kills all
live workers, local only the affected subplan chain), replan cap (default 2;
exceeding marks the run failed with reason replan_loop), and used-vs-discarded
marking on the aggregate event.

Trace layout: the world server (separate process) writes trace_world.jsonl,
the conductor writes trace.jsonl, same Section 6 event schema; trace.read_run
merges them by ts for analysis.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import socket
import subprocess
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import httpx
import psutil
import yaml
from pydantic import BaseModel, Field, ValidationError

from conductor.sessions import (ORCHESTRATOR_MODEL, WORKER_MODEL, SessionResult,
                                default_scratch_root, get_cli_version, run_claude)
from conductor.systems import SYSTEMS, SystemConfig
from sentinel.compile import compile_tripwires, strip_markdown_fence
from sentinel.judge import judge_escalation
from trace import TraceWriter
from world.state import InjectionSpec, RunConfig

REPO_ROOT = Path(__file__).resolve().parent.parent
PORT_POOL = range(8400, 8408)
MAX_ESCALATIONS = 6  # backstop against NOISE refire loops


class PlanStep(BaseModel):
    subplan_id: str
    worker_id: str
    subtask: str


class Plan(BaseModel):
    plan_id: str
    revision: int = 0
    steps: list[PlanStep] = Field(min_length=1)
    aggregation: str = ""


class AggregateReply(BaseModel):
    final_report: Any = None
    used: list[str] = Field(default_factory=list)
    discarded: list[str] = Field(default_factory=list)
    redo: list[PlanStep] = Field(default_factory=list)


@dataclass
class WorkerOutcome:
    instance_id: str
    subplan_id: str
    status: str          # done | escalated | blocked | paused | invalid_output | failed
    output: Any
    result: SessionResult


class RunAbort(Exception):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}")
        self.reason = reason
        self.detail = detail


def _parse_json_reply(text: Optional[str]) -> tuple[Any, bool]:
    if not text:
        raise ValueError("empty reply")
    body, stripped = strip_markdown_fence(text)
    return json.loads(body.strip()), stripped


def _pick_port() -> int:
    for port in PORT_POOL:
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("no free port in the 8400-8407 pool")


def _kill_tree(pid: int) -> None:
    try:
        parent = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return
    procs = parent.children(recursive=True) + [parent]
    for proc in procs:
        try:
            proc.kill()
        except psutil.NoSuchProcess:
            pass
    psutil.wait_procs(procs, timeout=10)


def _load_checker(checker_rel: str):
    path = REPO_ROOT / "tasks" / checker_rel
    spec = importlib.util.spec_from_file_location(f"checker_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Conductor:
    def __init__(self, *, task_path: str | Path, system_id: str,
                 injection: Optional[str] = None, n_inject: Optional[int] = None,
                 seed: int = 1, runs_root: str | Path = "runs",
                 max_replans: int = 2) -> None:
        self.task = yaml.safe_load(Path(task_path).read_text(encoding="utf-8"))
        self.system: SystemConfig = SYSTEMS[system_id]
        self.injection_name = injection
        self.n_inject = n_inject
        self.seed = seed
        self.max_replans = max_replans

        label = injection or "clean"
        base_id = f"{self.task['id']}-{system_id}-{label}-s{seed}"
        self.run_dir = Path(runs_root) / base_id
        suffix = 1
        while self.run_dir.exists():
            suffix += 1
            self.run_dir = Path(runs_root) / f"{base_id}-{suffix}"
        self.run_id = self.run_dir.name
        self.run_dir.mkdir(parents=True)

        self.trace = TraceWriter(self.run_dir / "trace.jsonl", run_id=self.run_id,
                                 seed=seed, system=system_id,
                                 task_id=self.task["id"])
        # ONE isolated home for the whole run: the orchestrator's --resume
        # turns need their session state to persist across invocations (a
        # per-call throwaway home would lose the session between turns).
        self.session_home = default_scratch_root() / f"home_{self.run_id}"
        self.port: Optional[int] = None
        self.world_proc: Optional[subprocess.Popen] = None
        self.base_url = ""

        self.orch_session_id: Optional[str] = None
        self.orch_system_prompt = ""
        self.worker_template = (REPO_ROOT / "prompts" / "worker.md").read_text(encoding="utf-8")

        self.armed_tripwires: dict[str, dict] = {}
        self.plan: Optional[Plan] = None
        self.outcomes: dict[str, WorkerOutcome] = {}
        self.live_pids: dict[str, int] = {}
        self.paused: set[str] = set()
        self.subplan_of: dict[str, str] = {}
        self.replans_done = 0
        self.escalations_seen = 0
        self.redo_used = False
        self.wave = 0
        self.all_calls: list[SessionResult] = []
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ world

    def start_world(self) -> None:
        self.port = _pick_port()
        self.base_url = f"http://localhost:{self.port}"
        injection_spec = None
        if self.injection_name:
            entry = next(i for i in self.task["injections"]
                         if i["type"] == self.injection_name)
            injection_spec = InjectionSpec(type=entry["type"],
                                           params=entry.get("params", {}))
        config = RunConfig(run_id=self.run_id, seed=self.seed,
                           system=self.system.id, task_id=self.task["id"],
                           n_inject=self.n_inject, injection=injection_spec,
                           trace_path=str(self.run_dir / "trace_world.jsonl"))
        cfg_path = self.run_dir / "world_config.json"
        cfg_path.write_text(config.model_dump_json(), encoding="utf-8")
        log = open(self.run_dir / "world_server.log", "w", encoding="utf-8")
        self.world_proc = subprocess.Popen(
            [sys.executable, "-m", "world.server", "--port", str(self.port),
             "--config", str(cfg_path)],
            cwd=str(REPO_ROOT), stdout=log, stderr=log)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try:
                if httpx.get(f"{self.base_url}/health", timeout=2).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.3)
        raise RunAbort("world_start_failed", "health check never passed")

    def _admin(self, method: str, path: str, **kwargs) -> httpx.Response:
        response = httpx.request(method, f"{self.base_url}{path}", timeout=10,
                                 **kwargs)
        response.raise_for_status()
        return response

    # ------------------------------------------------------------ orchestrator

    def _orchestrator_turn(self, message: dict, event_type: str) -> Any:
        result = run_claude(model=ORCHESTRATOR_MODEL,
                            system_prompt=self.orch_system_prompt,
                            stdin_text=json.dumps(message),
                            max_turns=6, no_tools=True,
                            resume=self.orch_session_id,
                            isolated_home=self.session_home)
        self.all_calls.append(result)
        parsed, error, fences = None, None, False
        try:
            parsed, fences = _parse_json_reply(result.result_text)
        except (ValueError, ValidationError) as exc:
            error = str(exc)[:500]
        self.trace.emit(actor="orchestrator", event_type=event_type,
                        payload={"mode": message.get("mode"),
                                 "valid": parsed is not None,
                                 "fences_stripped": fences, "error": error,
                                 "reply": parsed, **result.trace_payload()},
                        usage=result.trace_usage())
        if result.session_id:
            self.orch_session_id = result.session_id
        if parsed is None:
            raise RunAbort("orchestrator_invalid",
                           f"{event_type}: {error or 'no output'}")
        return parsed

    def make_plan(self) -> Plan:
        template = (REPO_ROOT / "prompts" / "orchestrator.md").read_text(encoding="utf-8")
        self.orch_system_prompt = (template
                                   .replace("{world_base_url}", self.base_url)
                                   .replace("{task_goal}", self.task["goal"].strip())
                                   .replace("{task_context}", self.task["task_context"].strip())
                                   .replace("{fan_out}", str(self.task.get("fan_out", 4))))
        raw = self._orchestrator_turn({"mode": "plan"}, "plan")
        try:
            plan = Plan.model_validate(raw)
        except ValidationError as exc:
            raise RunAbort("orchestrator_invalid", f"plan schema: {str(exc)[:300]}")
        self.plan = plan
        return plan

    def replan(self, interrupt_payload: dict) -> Plan:
        self.trace.emit(actor="conductor", event_type="interrupt",
                        payload=interrupt_payload)
        raw = self._orchestrator_turn({"mode": "interrupt", **interrupt_payload},
                                      "replan")
        try:
            plan = Plan.model_validate(raw)
        except ValidationError as exc:
            raise RunAbort("orchestrator_invalid", f"replan schema: {str(exc)[:300]}")
        self.plan = plan
        return plan

    def aggregate(self, redo_permitted: bool) -> AggregateReply:
        results = [{"worker_id": o.instance_id, "subplan_id": o.subplan_id,
                    "status": o.status, "output": o.output}
                   for o in self.outcomes.values()]
        raw = self._orchestrator_turn(
            {"mode": "aggregate", "results": results,
             "redo_permitted": redo_permitted}, "aggregate")
        try:
            return AggregateReply.model_validate(raw)
        except ValidationError as exc:
            raise RunAbort("orchestrator_invalid", f"aggregate schema: {str(exc)[:300]}")

    # ---------------------------------------------------------------- sentinel

    def plan_text(self) -> str:
        lines = [f"Goal: {self.task['goal'].strip()}", "", "Plan:"]
        for i, step in enumerate(self.plan.steps, start=1):
            lines.append(f"{i}. [{step.subplan_id}] ({step.worker_id}) {step.subtask}")
        return "\n".join(lines)

    def compile_and_arm(self) -> None:
        tripwire_set, results = compile_tripwires(
            self.plan_text(), self.task["task_context"].strip(), self.trace,
            isolated_home=self.session_home)
        self.all_calls.extend(results)
        if tripwire_set is None:
            raise RunAbort("compile_failed",
                           f"no schema-valid set after {len(results)} attempts")
        payload = json.loads(tripwire_set.model_dump_json())
        self._admin("POST", "/admin/arm_tripwires", json=payload)
        self.armed_tripwires = {t["id"]: t for t in payload["tripwires"]}
        self.trace.emit(actor="sentinel", event_type="tripwire_set",
                        payload={"plan_id": payload["plan_id"],
                                 "revision": self.plan.revision,
                                 "count": len(payload["tripwires"]),
                                 "tripwires": payload["tripwires"]})

    # ----------------------------------------------------------------- workers

    def _instance_id(self, worker_id: str) -> str:
        return worker_id if self.wave == 0 else f"{worker_id}r{self.wave}"

    def _run_worker(self, step: PlanStep, instance_id: str) -> WorkerOutcome:
        self.trace.emit(actor=instance_id, event_type="worker_start",
                        payload={"subplan_id": step.subplan_id,
                                 "wave": self.wave, "subtask": step.subtask})
        rendered = (self.worker_template
                    .replace("{world_base_url}", self.base_url)
                    .replace("{worker_id}", instance_id)
                    .replace("{subtask}", step.subtask))
        result = run_claude(
            model=WORKER_MODEL, system_prompt=rendered, prompt=step.subtask,
            max_turns=14,
            allowed_tools=f"Bash(curl http://localhost:{self.port}/*)",
            isolated_home=self.session_home,
            on_spawn=lambda pid: self.live_pids.__setitem__(instance_id, pid))
        self.all_calls.append(result)
        self.live_pids.pop(instance_id, None)

        status, output, fences = "failed", None, False
        if instance_id in self.paused:
            status = "paused"
        elif result.exit_code == 0 and result.result_text:
            try:
                output, fences = _parse_json_reply(result.result_text)
                status = output.get("status", "invalid_output") \
                    if isinstance(output, dict) else "invalid_output"
            except ValueError:
                status, output = "invalid_output", {"raw": result.result_text[:2000]}
        self.trace.emit(actor=instance_id, event_type="worker_end",
                        payload={"subplan_id": step.subplan_id, "status": status,
                                 "wave": self.wave, "output": output,
                                 "fences_stripped": fences,
                                 **result.trace_payload()},
                        usage=result.trace_usage())
        return WorkerOutcome(instance_id, step.subplan_id, status, output, result)

    def dispatch(self, executor: ThreadPoolExecutor, steps: list[PlanStep],
                 pending: dict[Future, str]) -> None:
        for step in steps:
            instance_id = self._instance_id(step.worker_id)
            self.subplan_of[instance_id] = step.subplan_id
            future = executor.submit(self._run_worker, step, instance_id)
            pending[future] = instance_id

    def pause_workers(self, scope: str, affected_subplans: list[str],
                      escalating: str) -> list[str]:
        with self._lock:
            victims = []
            for instance_id, pid in list(self.live_pids.items()):
                if instance_id == escalating:
                    continue
                if scope == "global" or self.subplan_of.get(instance_id) in affected_subplans:
                    victims.append(instance_id)
                    self.paused.add(instance_id)
                    _kill_tree(pid)
        self.trace.emit(actor="conductor", event_type="pause",
                        payload={"scope": scope,
                                 "affected_subplans": affected_subplans,
                                 "paused_workers": victims,
                                 "escalating_worker": escalating})
        return victims

    # -------------------------------------------------------------- escalation

    def handle_escalation(self, outcome: WorkerOutcome, executor, pending) -> None:
        self.escalations_seen += 1
        if self.escalations_seen > MAX_ESCALATIONS:
            raise RunAbort("escalation_loop",
                           f"more than {MAX_ESCALATIONS} escalations")
        tripwire_id = (outcome.output or {}).get("tripwire_id", "unknown")
        evidence = (outcome.output or {}).get("evidence", {})
        self.trace.emit(actor=outcome.instance_id, event_type="escalation",
                        payload={"tripwire_id": tripwire_id, "evidence": evidence,
                                 "subplan_id": outcome.subplan_id})

        tripwire = self.armed_tripwires.get(tripwire_id, {"id": tripwire_id})
        verdict = None
        if self.system.judge_enabled:
            verdict, judge_results = judge_escalation(
                tripwire, evidence, self.plan_text(), self.trace,
                isolated_home=self.session_home)
            self.all_calls.extend(judge_results)

        if verdict is None or verdict.verdict == "NOISE":
            if verdict is None and self.system.judge_enabled:
                self.trace.emit(actor="conductor", event_type="error",
                                payload={"where": "judge",
                                         "detail": "no valid verdict; treating as NOISE"})
            if tripwire_id in self.armed_tripwires:
                self._admin("POST", "/admin/suppress",
                            json={"tripwire_id": tripwire_id})
            step = PlanStep(subplan_id=outcome.subplan_id,
                            worker_id=outcome.instance_id.split("r")[0],
                            subtask=self._subtask_of(outcome.subplan_id))
            self.wave += 1
            self.trace.emit(actor="conductor", event_type="redispatch",
                            payload={"after": "noise", "wave": self.wave,
                                     "steps": [step.model_dump()]})
            self.dispatch(executor, [step], pending)
            return

        # GENUINE
        if self.replans_done >= self.max_replans:
            raise RunAbort("replan_loop",
                           f"replan cap {self.max_replans} exceeded")
        paused = self.pause_workers(verdict.scope_confirmed,
                                    verdict.affected_subplans or [outcome.subplan_id],
                                    outcome.instance_id)
        interrupt_payload = {
            "tripwire": tripwire,
            "verdict": verdict.model_dump(),
            "evidence": evidence,
            "workers": [{"worker_id": o.instance_id, "subplan_id": o.subplan_id,
                         "status": o.status} for o in self.outcomes.values()],
            "paused_workers": paused,
        }
        plan = self.replan(interrupt_payload)
        self.replans_done += 1
        if self.system.tripwires_enabled:
            # M3 amendment 1: the revised plan ships with NEW tripwires; the
            # second compile's cost lands in the trace like the first.
            self.compile_and_arm()
        self.wave += 1
        self.trace.emit(actor="conductor", event_type="redispatch",
                        payload={"after": "replan", "wave": self.wave,
                                 "revision": plan.revision,
                                 "steps": [s.model_dump() for s in plan.steps]})
        self.dispatch(executor, plan.steps, pending)

    def _subtask_of(self, subplan_id: str) -> str:
        for step in self.plan.steps:
            if step.subplan_id == subplan_id:
                return step.subtask
        return f"Redo the work for {subplan_id}."

    # --------------------------------------------------------------- main flow

    def drain(self, executor, pending: dict[Future, str]) -> None:
        while pending:
            done, _ = wait(list(pending), return_when=FIRST_COMPLETED)
            for future in done:
                instance_id = pending.pop(future)
                outcome: WorkerOutcome = future.result()
                self.outcomes[instance_id] = outcome
                if (outcome.status == "escalated"
                        and self.system.tripwires_enabled):
                    self.handle_escalation(outcome, executor, pending)

    def run(self) -> dict:
        success, reason, detail = False, None, ""
        try:
            self.start_world()
            self.trace.emit(actor="conductor", event_type="run_start",
                            payload={"cli_version": get_cli_version(),
                                     "system": self.system.id,
                                     "task": self.task["id"],
                                     "injection": self.injection_name,
                                     "n_inject": self.n_inject,
                                     "seed": self.seed, "port": self.port,
                                     "max_replans": self.max_replans})
            plan = self.make_plan()
            if self.system.tripwires_enabled:
                self.compile_and_arm()

            executor = ThreadPoolExecutor(max_workers=4)
            pending: dict[Future, str] = {}
            self.dispatch(executor, plan.steps, pending)
            self.drain(executor, pending)

            agg = self.aggregate(redo_permitted=(self.system.id == "S1"))
            if agg.redo and self.system.id == "S1" and not self.redo_used:
                self.redo_used = True
                self.wave += 1
                self.trace.emit(actor="conductor", event_type="redispatch",
                                payload={"after": "redo", "wave": self.wave,
                                         "steps": [s.model_dump() for s in agg.redo]})
                self.dispatch(executor, agg.redo, pending)
                self.drain(executor, pending)
                agg = self.aggregate(redo_permitted=False)
            executor.shutdown(wait=False)

            declared_used = set(agg.used)
            mechanical_discarded = sorted(set(self.outcomes) - declared_used)
            self.trace.emit(actor="orchestrator", event_type="aggregate",
                            payload={"final_report": agg.final_report,
                                     "used": sorted(declared_used),
                                     "discarded_declared": sorted(set(agg.discarded)),
                                     "discarded": mechanical_discarded})

            ground_truth = self._admin("GET", "/admin/ground_truth").json()
            checker = _load_checker(self.task["checker"])
            success, detail = checker.check(agg.final_report, ground_truth)
            self.trace.emit(actor="conductor", event_type="success_check",
                            payload={"success": success, "detail": detail})
        except RunAbort as abort:
            reason, detail = abort.reason, abort.detail
            self.trace.emit(actor="conductor", event_type="error",
                            payload={"reason": reason, "detail": detail})
        finally:
            total_cost = round(sum(r.cost_usd for r in self.all_calls), 6)
            self.trace.emit(actor="conductor", event_type="run_end",
                            payload={"success": success, "reason": reason,
                                     "detail": detail if not success else "",
                                     "replans": self.replans_done,
                                     "escalations": self.escalations_seen,
                                     "waves": self.wave,
                                     "llm_calls": len(self.all_calls),
                                     "cost_usd": total_cost})
            self.trace.close()
            for pid in list(self.live_pids.values()):
                _kill_tree(pid)  # aborts must not orphan in-flight workers
            if self.world_proc is not None:
                _kill_tree(self.world_proc.pid)
            shutil.rmtree(self.session_home, ignore_errors=True)
        return {"run_id": self.run_id, "run_dir": str(self.run_dir),
                "success": success, "reason": reason,
                "replans": self.replans_done, "cost_usd": total_cost}


def run_one(**kwargs) -> dict:
    return Conductor(**kwargs).run()


def main(argv: Optional[list[str]] = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="execute one pilot run")
    parser.add_argument("--task", required=True)
    parser.add_argument("--system", required=True, choices=sorted(SYSTEMS))
    parser.add_argument("--injection", default=None)
    parser.add_argument("--n-inject", type=int, default=None)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--runs-root", default="runs")
    parser.add_argument("--max-replans", type=int, default=2)
    args = parser.parse_args(argv)
    summary = run_one(task_path=args.task, system_id=args.system,
                      injection=args.injection, n_inject=args.n_inject,
                      seed=args.seed, runs_root=args.runs_root,
                      max_replans=args.max_replans)
    print(json.dumps(summary, indent=2))
    return 0 if summary["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
