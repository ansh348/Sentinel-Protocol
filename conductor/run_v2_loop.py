"""V2 run loop — the REAL matrix detection path (decision_memo_phase1 P3; D28/D29).

A `V2Conductor` reuses the v1 conductor's world / plan / worker / aggregate machinery
but replaces the v1 tripwire+judge detection with the v2 stack: a category-blind v2
compile (probes), and at each WORKER BARRIER (a worker returning its payload) the
cadence fires probes for that worker's surfaces on the SAME world instance with the
worker's own token, harvests the worker's reads through the §8 equivalence gate for
clean baselines, and runs corroboration. A corroborated INTERRUPT routes to a real
replan (recompile + redispatch). This is the path the one-shot matrix uses — NOT the
arm-smoke direct-harvest shortcut.

Same world-instance + token discipline: probes fire against this run's world subprocess
and re-use the most-recently-observed bearer token from the trace, so a cross-instance
token can never manufacture a 401 false positive (the bug the smoke hit and fixed).
DETERMINISTIC detection path ($0 LLM beyond the compile/plan/worker calls the run makes).
"""
from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, wait
from typing import Optional

import httpx

from conductor.run_one import Conductor, Dismiss, PlanStep, RunAbort
from conductor.systems import SystemConfig
from sentinel_v2.arms import run_v2_detection
from sentinel_v2.compile_probes import compile_assumptions, compile_pipeline
from sentinel_v2.corroboration import CorroboratedInvalidation, Grade
from sentinel_v2.probes import ProbeResult
from sentinel_v2.write_footprint import planned_write_patterns

class _SideChannelClient:
    """A perturbation-isolated READ handle over the run's world (D31 fence): every
    request carries the probe-channel marker, so a read never advances the
    injection counter (vector 1), never enters the token stream (vector 2), and
    mutates nothing (a write 405s at the transport). The compile-time §4 gate read
    uses this; it can never perturb the injection clock. /admin reads are
    middleware-excluded, so they pass through counter-neutrally regardless."""

    def __init__(self, base_url: str, timeout: float = 10) -> None:
        self._c = httpx.Client(base_url=base_url, timeout=timeout)

    def _h(self, headers) -> dict:
        h = {"X-Probe-Channel": "1", "X-Worker-Id": "probe"}
        if headers:
            h.update(dict(headers))
        return h

    def get(self, path, *, params=None, headers=None):
        return self._c.get(path, params=params, headers=self._h(headers))

    def head(self, path, *, headers=None):
        return self._c.head(path, headers=self._h(headers))

    def post(self, path, *, json=None, headers=None):
        return self._c.post(path, json=json, headers=self._h(headers))

    def close(self) -> None:
        self._c.close()


class _SideChannelWorld:
    """The `world` handle compile_pipeline's §4 gate route consumes (it needs only
    `.client`). A side-channel read handle, never the worker/injection channel."""

    def __init__(self, client: _SideChannelClient) -> None:
        self.client = client


V2_SYSTEM = SystemConfig(
    "V2", "v2 stack: compile + corroboration + cadence (two-tier, no judge)",
    tripwires_enabled=True,        # triggers compile_and_arm (overridden to v2) + replan recompile
    judge_enabled=False, escalate_any_anomaly=False, revalidation_every_k=None)
V2J_SYSTEM = SystemConfig(
    "V2J", "v2 stack with the rebuilt judge tier (exploratory)",
    tripwires_enabled=True, judge_enabled=False,   # the v2 'judge' is corroboration, not the v1 judge
    escalate_any_anomaly=False, revalidation_every_k=None)


class V2Conductor(Conductor):
    def __init__(self, *, judge: bool = False, **kwargs) -> None:
        super().__init__(system_config=(V2J_SYSTEM if judge else V2_SYSTEM),
                         probe_channel=True, **kwargs)
        self._judge = judge
        self.v2_probes: list = []
        self.v2_baselines: dict = {}          # surface -> earliest clean §8 read (the baseline)
        self.v2_invalidations: list = []      # DISTINCT corroborated invalidations (deduped)
        self.v2_query: dict = {}              # surface -> the baseline's query (§8 same projection)
        self.v2_interrupted_surfaces: set = set()   # D29 wobble dedup: one open per surface
        self.v2_coalesced = 0                 # re-detections of an already-open surface
        self.v2_interrupts = 0                # INTERRUPT-grade invalidations that replanned
        # D30 arm-time capture state
        self._v2_token: Optional[str] = None  # one worker-class token reused by all v2 probes
        self._arm_time_captured = False
        self.v2_arm_capture_counter: Optional[int] = None   # main counter when the sweep ran
        self.v2_baseline_source: dict = {}    # surface -> "arm_time" | "harvest"
        self.v2_baseline_counter: dict = {}   # surface -> main counter when its baseline was captured
        self.v2_arm_probes = 0                # arm-time probe count (the submetric delta)
        # D31: the planned write-set (category-blind, from the plan declaration) and
        # the §4 gate probes the parameterized compile armed.
        self.v2_write_set: tuple = ()
        self.v2_gate_probes: list = []
        self.v2_write_footprints: list = []   # D31 C4: planned-write surfaces, footprint-scoped
        # D31 C2: surfaces a barrier already re-observed (so the guaranteed
        # pre-completion sweep does not redundantly re-sweep a fresh surface), and
        # the one-shot guard + count submetric for that sweep.
        self.v2_observed_surfaces: set = set()
        self._v2_swept = False
        self.v2_pre_completion_probes = 0

    # -- v2 compile replaces the v1 tripwire compile/arm ----------------------
    def compile_and_arm(self) -> None:
        soft, sessions = compile_assumptions(self.plan_text(), self.task_context,
                                             self.trace, isolated_home=self.session_home)
        self.all_calls.extend(sessions)
        if soft is None:
            raise RunAbort("compile_failed", "v2 compile produced no soft set")
        # D31: the run-loop compile was UNDER-PARAMETERIZED — it dropped `world`
        # (so §4 gate probes never armed), `auth_token` (the docs gate shadow), and
        # `planned_write_set` (so a legitimate worker write read as drift). Supply
        # all three. The `world` is a perturbation-isolated side-channel READ handle;
        # the §4 non-perturbation check is counter-neutral (D31), so this compile
        # advances NO injection-counting channel (asserted: injection call-index
        # unchanged with vs without the gate-probe compile).
        self.v2_write_set = planned_write_patterns(self.task.get("plan", []))
        token = self._acquire_v2_token()
        sc_client = _SideChannelClient(self.base_url)
        try:
            cr = compile_pipeline(
                soft, world_rev=int(self.task.get("world_rev", 1)),
                world=_SideChannelWorld(sc_client), auth_token=token,
                planned_write_set=self.v2_write_set)
        finally:
            sc_client.close()
        self.v2_gate_probes = [p for p in cr.probes
                               if p.lens.op.value == "gate_shadow"]
        # D31 C4: keep-not-flush the write footprints (dedup by surface, latest wins)
        by_surface = {f.surface: f for f in self.v2_write_footprints}
        for f in cr.write_footprints:
            by_surface[f.surface] = f
        self.v2_write_footprints = list(by_surface.values())
        # keep-not-flush (D2/D29): keep prior probes, add new ones. Dedup by probe
        # IDENTITY (target + shape + lens), NOT by target alone — a surface can carry
        # several load-bearing assumptions (e.g. a schema-shape AND a value probe on
        # /pricing); collapsing to one per target would silently drop the shape that
        # catches a field rename.
        def _key(p):
            return (p.target, p.fault_shape, p.lens.op, p.lens.pointer,
                    p.lens.header_name, p.lens.field)
        by_key = {_key(p): p for p in self.v2_probes}
        for p in cr.probes:
            by_key[_key(p)] = p
        self.v2_probes = list(by_key.values())
        self.trace.emit(actor="sentinel_v2", event_type="tripwire_set",
                        payload={"layer": "v2_probes", "plan_id": soft.plan_id,
                                 "revision": self.plan.revision,
                                 "count": len(self.v2_probes),
                                 "targets": [p.target for p in self.v2_probes],
                                 "write_set": list(self.v2_write_set),
                                 "gate_probes": [p.target for p in self.v2_gate_probes],
                                 "uncovered": cr.uncovered})
        # D30: the GUARANTEED clean reference. Fire the arm-time sweep ONCE, at run
        # start (the first compile, before any worker tool call). Replan recompiles do
        # NOT re-capture (they run mid-run / post-injection — not clean).
        if not self._arm_time_captured:
            self._arm_time_captured = True
            self._arm_time_capture()

    def _acquire_v2_token(self) -> Optional[str]:
        """One worker-class token, reused by every v2 probe (arm-time + barriers) so the
        baseline and its later comparisons share the same token/principal (§8 same auth).
        Acquired via the main path (a single call inside the clean window); never root."""
        if self._v2_token is None:
            try:
                resp = self._admin("POST", "/auth/token", headers={"X-Worker-Id": "w1"})
                self._v2_token = resp.json().get("token")
            except Exception:
                self._v2_token = None
        return self._v2_token

    def _arm_time_capture(self) -> None:
        """D30: proactively observe every load-bearing surface ONCE through the side
        channel, before any worker tool call, and record the earliest clean §8 read as
        the guaranteed baseline. Category-blind and injection-blind; reads only; the
        bare surface (no query) — a worker harvest later supplies a query-bearing
        projection for surfaces this misses. Side-channel reads do not advance the
        injection clock, so the sweep is in the clean window by construction."""
        if not self.v2_probes:
            return
        from sentinel_v2.probes import ProbeExecutor
        token = self._acquire_v2_token()
        try:
            counter = self._admin("GET", "/admin/state").json().get("counter")
        except Exception:
            counter = None
        self.v2_arm_capture_counter = counter
        client = httpx.Client(base_url=self.base_url, timeout=10)
        ex = ProbeExecutor(client, auth_token=token)
        captured = []
        try:
            for target in dict.fromkeys(p.target for p in self.v2_probes):  # unique, in order
                self.v2_arm_probes += 1
                try:
                    obs = ex.get(target)            # bare surface, no query
                except Exception:
                    continue
                # §8 clean-baseline criterion: a side-effect-free worker-class GET,
                # cache-fresh, captured pre-transform, with a present body — serves every
                # shape probe on the surface (schema/field/hash diff against it later).
                if obs.status is not None and obs.status < 400 and obs.body is not None:
                    self.v2_baselines[target] = obs
                    self.v2_query[target] = ""      # arm-time projection (no query)
                    self.v2_baseline_source[target] = "arm_time"
                    self.v2_baseline_counter[target] = counter
                    captured.append(target)
        finally:
            client.close()
        self.trace.emit(actor="sentinel_v2", event_type="corroboration",
                        payload={"layer": "v2_arm_baseline", "capture_counter": counter,
                                 "captured": captured, "probed": self.v2_arm_probes})

    # -- drain with the v2 worker barrier + guaranteed pre-completion sweep ----
    def drain(self, executor, pending: dict[Future, str]) -> None:
        while True:
            while pending:
                done, _ = wait(list(pending), return_when=FIRST_COMPLETED)
                for future in done:
                    instance_id = pending.pop(future)
                    outcome = future.result()
                    self.outcomes[instance_id] = outcome
                    self._v2_worker_barrier(outcome, executor, pending)
            # all workers idle -> the guaranteed pre-completion sweep (fires once;
            # if a barrier replan re-dispatched into `pending`, that is drained by the
            # inner loop above before the sweep, and the sweep is not re-run).
            if self._v2_swept:
                break
            self._pre_completion_sweep()
            if not pending:
                break

    def _last_observed_token(self) -> Optional[str]:
        """Re-use the most recently observed bearer token (E.2) from the world trace,
        so probes carry the worker's own principal on the SAME world instance."""
        from trace import read_trace
        wt = self.run_dir / "trace_world.jsonl"
        if not wt.exists():
            return None
        token = None
        for e in read_trace(wt):
            if e["event_type"] == "tool_response":
                body = e["payload"].get("body")
                if isinstance(body, dict) and isinstance(body.get("token"), str):
                    token = body["token"]
        return token

    def _harvest_into_baselines(self) -> None:
        """Harvest worker reads from the world trace through the §8 equivalence gate;
        the earliest clean (status<400, region-present) read of each watched surface is
        its baseline. This is the worker-view coverage the matcher consumes."""
        from trace import read_trace
        from sentinel_v2.cadence.harvest import WorkerRead, harvest_equivalence
        wt = self.run_dir / "trace_world.jsonl"
        if not wt.exists():
            return
        targets = {p.target: p for p in self.v2_probes}
        calls: dict = {}
        for e in read_trace(wt):
            et, p = e["event_type"], e["payload"]
            if et == "tool_call":
                calls[p.get("counter")] = (e.get("actor", "unknown"),
                                           p.get("method", "GET"), p.get("path", ""),
                                           p.get("query", ""))
            elif et == "tool_response":
                c = p.get("counter")
                if c not in calls:
                    continue
                actor, method, path, query = calls[c]
                probe = targets.get(path)
                if probe is None or path in self.v2_baselines:
                    continue
                status = p.get("status")
                if status is None or status >= 400:
                    continue                    # a baseline must be a clean read
                result = ProbeResult(method=method, path=path, status=status,
                                     headers={}, body=p.get("body"))
                read = WorkerRead(surface_id=path, method=method, auth_principal=actor,
                                  cache_state="fresh", raw_captured_pre_transform=True,
                                  result=result)
                if harvest_equivalence(read, expected_surface=path, lens=probe.lens,
                                       expected_principal=actor).ok:
                    # D30: a worker harvest fills surfaces the arm-time sweep MISSED
                    # (e.g. query-required surfaces); it never overwrites an arm-time
                    # baseline (the guaranteed source) — `path in self.v2_baselines`
                    # above already skips those, so a post-injection read cannot poison
                    # a clean arm-time reference.
                    self.v2_baselines[path] = result
                    # §8 same projection: the probe must replay the worker's query
                    self.v2_query[path] = query
                    self.v2_baseline_source[path] = "harvest"
                    self.v2_baseline_counter[path] = c

    def _worker_surfaces(self, outcome) -> set:
        """The probe surfaces this worker actually touched (its output-dependency
        surfaces). Falls back to the full probe set if the trace shows none yet."""
        from trace import read_trace
        wt = self.run_dir / "trace_world.jsonl"
        targets = {p.target for p in self.v2_probes}
        touched = set()
        if wt.exists():
            for e in read_trace(wt):
                if (e["event_type"] == "tool_call"
                        and e.get("actor") == outcome.instance_id
                        and e["payload"].get("path") in targets):
                    touched.add(e["payload"]["path"])
        return touched or targets

    def _current_counter(self) -> Optional[int]:
        try:
            return self._admin("GET", "/admin/state").json().get("counter")
        except Exception:
            return None

    def _record_invalidations(self, invs, *, subplan_id, counter, where,
                              emit_interrupt: bool = False) -> list:
        """D29 wobble dedup + escalation, shared by the worker barrier and the
        pre-completion sweep. Returns the NEW interrupt-grade invalidations (a
        re-detection of an already-open surface coalesces into a suppressed_refire —
        never a new interrupt or replan, so a sustained violation cannot flood).
        `emit_interrupt` records the M6 `interrupt` detection marker directly — used
        by the pre-completion path, which detects but does not replan (the barrier
        path instead emits its `interrupt` through the replan)."""
        new = [i for i in invs if i.target not in self.v2_interrupted_surfaces]
        for inv in invs:
            if inv.target in self.v2_interrupted_surfaces:
                self.v2_coalesced += 1
                self.trace.emit(actor="sentinel_v2", event_type="suppressed_refire",
                                payload={"where": where,
                                         "tripwire_id": f"v2_probe::{inv.target}",
                                         "target": inv.target, "counter": counter})
        for inv in new:
            self.v2_invalidations.append(inv)
            self.v2_interrupted_surfaces.add(inv.target)
            # an escalation carrying the surface (_path) makes the interrupt
            # attributable to the injection for the M6 instrument (metrics §0)
            self.trace.emit(actor="sentinel_v2", event_type="escalation",
                            payload={"tripwire_id": f"v2_probe::{inv.target}",
                                     "evidence": {"_path": inv.target,
                                                  "grade": inv.grade.value},
                                     "subplan_id": subplan_id, "counter": counter,
                                     "where": where})
            if emit_interrupt and inv.grade is Grade.INTERRUPT:
                # the M6 detection marker for a pre-completion interrupt (no replan)
                self.trace.emit(actor="conductor", event_type="interrupt",
                                payload={"tripwire_id": f"v2_probe::{inv.target}",
                                         "evidence": {"_path": inv.target},
                                         "where": where, "counter": counter})
        return [i for i in new if i.grade is Grade.INTERRUPT]

    def _v2_worker_barrier(self, outcome, executor, pending) -> None:
        if not self.v2_probes:
            return
        self._harvest_into_baselines()
        # PRE_COMPLETION probes (the §4 gate shadow, whole-payload) are NOT fired at a
        # barrier — they belong to the guaranteed pre-completion sweep. Firing the
        # gate shadow at a barrier would route its detection through a mid-run replan
        # (re-running the worker, and a flaky orchestrator reply can abort the run);
        # the shadow is observable only on the side channel anyway, so the sweep is
        # its proper home.
        barrier_probes = [p for p in self.v2_probes
                          if p.target in self._worker_surfaces(outcome)
                          and p.cadence_hint.value != "pre_completion"]
        if not barrier_probes:
            return
        # §8 same token: reuse the v2 token the arm-time baseline was captured with
        # (falls back to the worker's latest token if the arm-time acquisition failed).
        token = self._v2_token or self._last_observed_token()
        client = httpx.Client(base_url=self.base_url, timeout=10)
        try:
            det = run_v2_detection(barrier_probes, client, auth_token=token,
                                   baselines=self.v2_baselines, queries=self.v2_query,
                                   judge=self._judge)
        except Exception as exc:                 # a barrier fault never crashes the run
            self.trace.emit(actor="sentinel_v2", event_type="error",
                            payload={"where": "v2_barrier", "detail": str(exc)[:200]})
            return
        finally:
            client.close()
        # these surfaces are now FRESH (re-observed at this barrier) — the guaranteed
        # pre-completion sweep will not redundantly re-sweep them.
        self.v2_observed_surfaces.update(p.target for p in barrier_probes)
        interrupts = self._record_invalidations(
            det["invalidations"], subplan_id=outcome.subplan_id,
            counter=self._current_counter(), where="v2_cadence")
        if interrupts and self.replans_done < self.max_replans:
            self._v2_replan(interrupts[0], outcome, executor, pending)

    def _pre_completion_sweep(self) -> None:
        """D29 §3.1 guaranteed pre-completion sweep (D31 C2). Fire ONCE after the last
        worker drains, before aggregate: re-observe every load-bearing surface no
        barrier re-observed — most importantly the side-channel-only §4 gate shadow,
        which a worker can never touch. Side-channel, $0 dollars (count submetric);
        unreachable surfaces route to the uncovered valve. A pre-completion detection
        is RECORDED (M6/C7) but does not replan — the run is ending, there is no
        productive work left to redispatch."""
        if self._v2_swept or (not self.v2_probes and not self.v2_write_footprints):
            return
        self._v2_swept = True
        self._harvest_into_baselines()
        from sentinel_v2.cadence.sweep import run_pre_completion_sweep
        token = self._v2_token or self._last_observed_token()
        client = httpx.Client(base_url=self.base_url, timeout=10)
        try:
            res = run_pre_completion_sweep(
                self.v2_probes, self.v2_observed_surfaces,
                self.v2_interrupted_surfaces, client=client, auth_token=token,
                baselines=self.v2_baselines, queries=self.v2_query, judge=self._judge,
                emit=lambda et, p: self.trace.emit(actor="sentinel_v2",
                                                   event_type=et, payload=p))
            self.v2_pre_completion_probes += len(res["swept"])
            self.v2_observed_surfaces.update(res["reachable"])
            # a pre-completion detection emits its own M6 interrupt marker (no replan)
            self._record_invalidations(res["invalidations"], subplan_id="pre_completion",
                                       counter=self._current_counter(),
                                       where="v2_pre_completion_sweep",
                                       emit_interrupt=True)
            self.trace.emit(actor="sentinel_v2", event_type="corroboration",
                            payload={"layer": "v2_pre_completion_sweep",
                                     "swept": res["swept"], "reachable": res["reachable"],
                                     "uncovered": res["uncovered"]})
            self._evaluate_write_footprints(client, token)
        except Exception as exc:                 # the sweep never crashes the run
            self.trace.emit(actor="sentinel_v2", event_type="error",
                            payload={"where": "v2_pre_completion_sweep",
                                     "detail": str(exc)[:200]})
        finally:
            client.close()

    def _evaluate_write_footprints(self, client, token) -> None:
        """D31 C4 write-surface policy, evaluated on the FINAL state (pre-completion).
        Off-footprint change or an in-footprint deviation from the authorized
        transition is DRIFT (interrupt); an unverifiable footprint is UNCOVERED_CAUTION
        (loud, scored by C7 — never silently clean). The footprint check is the PRIMARY
        predicate for a write surface: a legitimate permanent write is consistent with
        its footprint and so is never promoted as drift by D28 persistence (the write
        surface never enters the ordinary drift+persistence path)."""
        if not self.v2_write_footprints:
            return
        from sentinel_v2.probes import ProbeExecutor
        from sentinel_v2.write_surface import (FootprintVerdict,
                                              evaluate_write_footprint)
        ex = ProbeExecutor(client, auth_token=token)
        drifts = []
        for fp in self.v2_write_footprints:
            self.v2_pre_completion_probes += 1
            try:
                obs = ex.get(fp.surface)
            except Exception as exc:
                self.trace.emit(actor="sentinel_v2", event_type="uncovered",
                                payload={"where": "v2_write_footprint",
                                         "target": fp.surface,
                                         "reason": "unreachable write surface",
                                         "detail": str(exc)[:120]})
                continue
            ev = evaluate_write_footprint(fp, self.v2_baselines.get(fp.surface), obs)
            if ev.verdict is FootprintVerdict.DRIFT:
                drifts.append(CorroboratedInvalidation(
                    target=fp.surface, grade=Grade.INTERRUPT,
                    fault_shape="value_changed", evidence_class="content_shaped",
                    reason=f"write-surface drift: {ev.reason}", witness=ev.witness))
            elif ev.verdict is FootprintVerdict.UNCOVERED_CAUTION:
                self.trace.emit(actor="sentinel_v2", event_type="uncovered",
                                payload={"where": "v2_write_footprint",
                                         "target": fp.surface, "grade": "caution",
                                         "reason": ev.reason})
            # CLEAN -> consistent with the authorized footprint; nothing to record
        if drifts:
            self._record_invalidations(drifts, subplan_id="pre_completion",
                                       counter=self._current_counter(),
                                       where="v2_write_footprint", emit_interrupt=True)

    def _v2_replan(self, inv, outcome, executor, pending) -> None:
        paused = self.pause_workers("global", [], outcome.instance_id)
        payload = {
            "tripwire": {"id": f"v2_probe::{inv.target}", "target": inv.target,
                         "scope": "global"},
            "verdict": {"grade": inv.grade.value, "reason": inv.reason},
            "evidence": {"_path": inv.target},
            "workers": [{"worker_id": o.instance_id, "subplan_id": o.subplan_id,
                         "status": o.status} for o in self.outcomes.values()],
            "paused_workers": paused,
            "completed_results": self._completed_results(),
        }
        reply = self.replan(payload)             # emits the `interrupt` event
        self.v2_interrupts += 1
        if isinstance(reply, Dismiss):
            base = outcome.instance_id.split("r")[0]
            self._admin("POST", "/admin/clear_tripped",
                        json={"worker_ids": [outcome.instance_id, base, "unknown"]})
            self.wave += 1
            self.dispatch(executor, [PlanStep(subplan_id=outcome.subplan_id,
                                              worker_id=base,
                                              subtask=self._subtask_of(outcome.subplan_id))],
                          pending)
            return
        self.replans_done += 1
        self.compile_and_arm()                   # recompile v2 probes for the revised plan
        self.wave += 1
        self.trace.emit(actor="conductor", event_type="redispatch",
                        payload={"after": "v2_replan", "wave": self.wave,
                                 "revision": self.plan.revision,
                                 "steps": [s.model_dump() for s in self.plan.steps]})
        self.dispatch(executor, self.plan.steps, pending)


def run_v2_loop(*, task_path, injection=None, n_inject=None, seed=1,
                runs_root="runs", judge=False, max_replans=2) -> dict:
    """Run one cell through the real v2 loop and return the run summary (+ the
    conductor for v2-state inspection)."""
    cond = V2Conductor(task_path=task_path, injection=injection, n_inject=n_inject,
                       seed=seed, runs_root=runs_root, judge=judge,
                       max_replans=max_replans)
    summary = cond.run()
    summary["v2_invalidations"] = len(cond.v2_invalidations)
    summary["v2_interrupts"] = cond.v2_interrupts
    summary["v2_coalesced"] = cond.v2_coalesced
    summary["pre_completion_probes"] = cond.v2_pre_completion_probes
    summary["write_set"] = list(cond.v2_write_set)
    summary["gate_probes"] = [p.target for p in cond.v2_gate_probes]
    summary["v2_grades"] = [i.grade.value for i in cond.v2_invalidations]
    summary["v2_targets"] = [i.target for i in cond.v2_invalidations]
    summary["run_dir"] = str(cond.run_dir)
    # D30 right-reason fields
    summary["arm_capture_counter"] = cond.v2_arm_capture_counter
    summary["arm_probes"] = cond.v2_arm_probes
    summary["baseline_source"] = dict(cond.v2_baseline_source)
    summary["baseline_counter"] = dict(cond.v2_baseline_counter)
    # injection call-index from the world trace (None on a clean cell)
    inj_counter = None
    from trace import read_trace
    wt = cond.run_dir / "trace_world.jsonl"
    if wt.exists():
        for e in read_trace(wt):
            if e["event_type"] == "injection_fired":
                inj_counter = e["payload"].get("counter")
                break
    summary["injection_counter"] = inj_counter
    # the detected surfaces' baseline provenance (for the right-reason assertion)
    summary["detected_baselines"] = [
        {"target": i.target, "grade": i.grade.value,
         "baseline_source": cond.v2_baseline_source.get(i.target),
         "baseline_counter": cond.v2_baseline_counter.get(i.target)}
        for i in cond.v2_invalidations]
    return summary
