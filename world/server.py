"""World server: FastAPI app factory, tool-traffic middleware, /admin endpoints.

Locked architecture decision #3: the middleware (i) increments the global tool-call
counter, (ii) fires the injection when the counter hits N_inject, (iii) evaluates
the active tripwire set against each outgoing response with pure predicate matching
(no LLM calls in the middleware, ever), (iv) on a match embeds a tripwire_control
object in the response, and (v) appends every event to the run's JSONL trace.

Injection timing semantics: the counter increments when a countable request
arrives; if it reaches N_inject the mutation is applied BEFORE the request is
dispatched, so call number N_inject is the first to observe the broken world.

Hard-stop enforcement (M3 amendment 2): after a worker receives
STOP_AND_ESCALATE, any subsequent call from it is answered 409 with the same
control object and a worker_noncompliance trace event — pause semantics stay
deterministic even if the model disobeys worker.md.

One process serves exactly one run (locked decision #2); the conductor starts one
uvicorn instance per run on a port from 8400-8407 and kills it afterwards.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import Any, Optional

from fastapi import FastAPI, Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from sentinel.dsl import Tripwire, TripwireSet
from trace import TraceWriter
from world.injections import DEPRECATION_BODY, apply_injection
from world.state import InjectionSpec, RunConfig, WorldState
from world.services import auth, docs, inventory, pricing, repo, shipping

_MISSING = object()

# Canonical concrete paths covering every route family; used to classify
# url_patterns at arm time (D5) and by the Phase 0 mechanized-observable bit.
PATH_SAMPLES = (
    "/auth/token", "/auth/validate",
    "/inventory/items", "/inventory/items/WID-001", "/inventory/items/GAD-001",
    "/pricing/quote/WID-001", "/pricing/quote/GAD-001", "/pricing/quotes",
    "/shipping/destinations", "/shipping/rates/WID-001", "/shipping/rates/GAD-001",
    "/docs/passages", "/docs/passages/pol-returns", "/docs/passages/ops-warehouses",
    "/docs/search", "/docs/validate", "/docs/package",
    "/repo/files", "/repo/files/config/settings.yaml", "/repo/files/src/aggregate.py",
    "/repo/validate",
)


def classify_url_pattern(pattern: str) -> Optional[str]:
    """deviations.md D5: url_pattern is matched as a glob per the DSL comment,
    but the frozen compile prompt gives the model no way to know that, and
    compiled sets reliably emit regex-style patterns. Classification is static
    and deterministic, decided once at arm time against PATH_SAMPLES: glob if
    the pattern glob-matches any sample, else regex if it regex-matches any
    sample, else None (a dead pattern that never matches anything)."""
    if any(fnmatchcase(p, pattern) for p in PATH_SAMPLES):
        return "glob"
    try:
        rx = re.compile(pattern)
    except re.error:
        return None
    if any(rx.search(p) for p in PATH_SAMPLES):
        return "regex"
    return None


def _pointer_lookup(body: Any, pointer: str) -> Any:
    """Resolve a JSON pointer (RFC6901-style '/a/b'; dotted 'a.b' tolerated)
    against a parsed response body. Returns _MISSING when unresolvable."""
    if pointer.startswith("/"):
        parts = [p.replace("~1", "/").replace("~0", "~")
                 for p in pointer[1:].split("/") if p != ""]
    elif "/" in pointer:
        parts = [p for p in pointer.split("/") if p != ""]
    else:
        parts = pointer.split(".")
    node = body
    for part in parts:
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        else:
            return _MISSING
    return node


class TripwireMatcher:
    """Pure-predicate tripwire matcher. Armed with a DSL-validated TripwireSet
    via /admin/arm_tripwires; never an LLM call.

    Predicate semantics: signal gates (type/method/url_pattern) AND all present
    predicates must hold. url_pattern and order_violation tools are globs
    (fnmatchcase) over world paths, per the DSL comment. A tripwire whose only
    predicate is contradicts_assumption is touch-triggered per deviations.md
    D3: any gated response fires once per (tripwire, path)."""

    def __init__(self) -> None:
        self.tripwires: list[Tripwire] = []
        self.suppressed: set[str] = set()
        self._touch_seen: set[tuple[str, str]] = set()
        self._call_history: list[tuple[str, str]] = []
        self._pattern_mode: dict[str, Optional[str]] = {}

    def arm(self, tripwire_set: TripwireSet) -> None:
        self.tripwires = list(tripwire_set.tripwires)
        self.suppressed.clear()
        self._touch_seen.clear()
        self._call_history.clear()
        self._pattern_mode = {
            tw.id: classify_url_pattern(tw.signal.url_pattern)
            for tw in self.tripwires if tw.signal.url_pattern
        }

    def pattern_mode(self, tripwire_id: str) -> Optional[str]:
        return self._pattern_mode.get(tripwire_id)

    def suppress(self, tripwire_id: str) -> None:
        self.suppressed.add(tripwire_id)

    def get(self, tripwire_id: str) -> Optional[Tripwire]:
        return next((t for t in self.tripwires if t.id == tripwire_id), None)

    def evaluate(self, *, method: str, path: str, status: int,
                 body: Any) -> list[Tripwire]:
        matched = [tw for tw in self.tripwires
                   if tw.id not in self.suppressed
                   and self._matches(tw, method, path, status, body)]
        self._call_history.append((method.upper(), path))
        return matched

    def _matches(self, tw: Tripwire, method: str, path: str, status: int,
                 body: Any) -> bool:
        sig = tw.signal
        if sig.type == "retrieval_content" and not path.startswith("/docs"):
            return False
        if sig.type == "auth_state" and not (status == 401
                                             or path.startswith("/auth")):
            return False
        if sig.method and sig.method.upper() != method.upper():
            return False
        if sig.url_pattern:
            mode = self._pattern_mode.get(tw.id)
            if mode == "glob":
                if not fnmatchcase(path, sig.url_pattern):
                    return False
            elif mode == "regex":
                if not re.search(sig.url_pattern, path):
                    return False
            else:
                return False  # dead pattern: never matches (D5)

        predicates: list[bool] = []
        if sig.status_in is not None:
            predicates.append(status in sig.status_in)
        if sig.field_absent is not None:
            predicates.append(_pointer_lookup(body, sig.field_absent) is _MISSING)
        if sig.field_regex is not None:
            hit = False
            for pointer, pattern in sig.field_regex.items():
                value = _pointer_lookup(body, pointer)
                try:
                    if value is not _MISSING and re.search(pattern, str(value)):
                        hit = True
                except re.error:
                    pass
            predicates.append(hit)
        if sig.order_violation is not None:
            observed = sig.order_violation.get("observed", "")
            required = sig.order_violation.get("required_before", "")
            if observed and fnmatchcase(path, observed):
                seen = any(fnmatchcase(p, required)
                           for _, p in self._call_history)
                predicates.append(not seen)
            else:
                predicates.append(False)

        if predicates:
            return all(predicates)
        if sig.contradicts_assumption is not None:
            key = (tw.id, path)
            if key in self._touch_seen:
                return False
            self._touch_seen.add(key)
            return True
        return False


def build_control(tw: Tripwire, *, method: str, path: str, status: int,
                  counter: int, body: Any) -> dict:
    """The tripwire_control object embedded in the worker's tool response.
    Evidence is resolved here so the worker can copy it with zero reasoning."""
    meta = {"status": status, "path": path, "method": method, "counter": counter}
    evidence: dict[str, Any] = {}
    for field in tw.evidence_fields:
        if field in meta:
            evidence[field] = meta[field]
        else:
            value = _pointer_lookup(body, field)
            evidence[field] = None if value is _MISSING else value
    return {
        "action": "STOP_AND_ESCALATE",
        "tripwire_id": tw.id,
        "severity": tw.severity.value,
        "evidence_fields": list(tw.evidence_fields),
        "evidence": evidence,
    }


@dataclass
class AppContext:
    config: RunConfig
    state: WorldState
    trace: TraceWriter
    matcher: TripwireMatcher


def _parse_json(raw: bytes) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return raw.decode("utf-8", errors="replace")


class WorldMiddleware:
    """Pure ASGI middleware so request bodies can be teed and response bodies
    buffered/rewritten without BaseHTTPMiddleware's caveats."""

    EXCLUDED_EXACT = frozenset({"/health", "/openapi.json"})
    EXCLUDED_PREFIXES = ("/admin/",)

    def __init__(self, app: ASGIApp, ctx: AppContext) -> None:
        self.app = app
        self.ctx = ctx

    def _excluded(self, path: str) -> bool:
        return (path in self.EXCLUDED_EXACT
                or any(path.startswith(p) for p in self.EXCLUDED_PREFIXES))

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self._excluded(scope["path"]):
            await self.app(scope, receive, send)
            return

        ctx = self.ctx
        state = ctx.state
        config = ctx.config

        state.counter += 1
        n = state.counter
        method = scope["method"]
        path = scope["path"]
        query = scope.get("query_string", b"").decode("utf-8", errors="replace")
        headers = {k.decode("latin-1").lower(): v.decode("latin-1")
                   for k, v in scope.get("headers", [])}
        worker_id = headers.get("x-worker-id", "unknown")

        # Counter-triggered injection: the only path comparative runs may use.
        if (config.injection is not None and config.n_inject is not None
                and not state.injection_fired and n >= config.n_inject):
            detail = apply_injection(state, config.injection)
            state.injection_fired = True
            state.injection_fired_at = n
            ctx.trace.emit(
                actor="world",
                event_type="injection_fired",
                payload={"trigger": "counter", "counter": n, "injection": detail},
            )

        # Hard stop for tripped workers (M3 amendment 2).
        if worker_id in state.tripped_workers:
            control = state.tripped_workers[worker_id]
            body_409 = {"error": "worker_tripped",
                        "detail": "stop and escalate; further tool calls are refused",
                        "tripwire_control": control}
            ctx.trace.emit(actor=worker_id, event_type="tool_call",
                           payload={"counter": n, "method": method, "path": path,
                                    "query": query, "body": None})
            ctx.trace.emit(actor=worker_id, event_type="worker_noncompliance",
                           payload={"counter": n, "path": path,
                                    "tripwire_id": control["tripwire_id"]})
            ctx.trace.emit(actor=worker_id, event_type="tool_response",
                           payload={"counter": n, "status": 409, "body": body_409})
            response = JSONResponse(status_code=409, content=body_409)
            await response(scope, receive, send)
            return

        # endpoint_404: removed routes are answered at the middleware boundary so
        # the deprecation body is identical no matter which router owned the path.
        if state.route_removed(path):
            await self._respond(scope, receive, send, n, method, path, query,
                                worker_id, request_body=None, status=404,
                                body=dict(DEPRECATION_BODY))
            return

        req_chunks: list[bytes] = []

        async def receive_teed() -> dict:
            message = await receive()
            if message["type"] == "http.request":
                req_chunks.append(message.get("body", b""))
            return message

        start_message: dict = {}
        body_chunks: list[bytes] = []

        async def send_buffered(message: dict) -> None:
            if message["type"] == "http.response.start":
                start_message.update(message)
                return
            if message["type"] == "http.response.body":
                body_chunks.append(message.get("body", b""))
                if not message.get("more_body", False):
                    raw = b"".join(body_chunks)
                    request_body = (_parse_json(b"".join(req_chunks))
                                    if req_chunks else None)
                    await self._respond(scope, receive, send, n, method, path,
                                        query, worker_id,
                                        request_body=request_body,
                                        status=start_message["status"],
                                        body=_parse_json(raw))
                return
            await send(message)

        await self.app(scope, receive_teed, send_buffered)

    async def _respond(self, scope: Scope, receive: Receive, send: Send, n: int,
                       method: str, path: str, query: str, worker_id: str, *,
                       request_body: Any, status: int, body: Any) -> None:
        ctx = self.ctx
        ctx.trace.emit(
            actor=worker_id,
            event_type="tool_call",
            payload={"counter": n, "method": method, "path": path,
                     "query": query, "body": request_body},
        )

        # Pure predicate matching against the outgoing response.
        control: Optional[dict] = None
        for tw in ctx.matcher.evaluate(method=method, path=path, status=status,
                                       body=body):
            log_only = tw.action.on_trigger == "LOG"
            ctx.trace.emit(
                actor="world",
                event_type="tripwire_fire",
                payload={"counter": n, "tripwire_id": tw.id,
                         "severity": tw.severity.value,
                         "on_trigger": tw.action.on_trigger,
                         "log_only": log_only, "path": path, "status": status,
                         "worker_id": worker_id,
                         "url_match_mode": ctx.matcher.pattern_mode(tw.id)},
            )
            if not log_only and control is None:
                control = build_control(tw, method=method, path=path,
                                        status=status, counter=n, body=body)

        if control is not None:
            ctx.state.tripped_workers[worker_id] = control
            if isinstance(body, dict):
                body = {**body, "tripwire_control": control}
            else:
                body = {"tripwire_control": control, "raw": body}

        ctx.trace.emit(
            actor=worker_id,
            event_type="tool_response",
            payload={"counter": n, "status": status, "body": body},
        )

        if isinstance(body, str):
            response = Response(content=body, status_code=status,
                                media_type="text/plain")
        else:
            response = Response(
                content=json.dumps(body, separators=(",", ":"),
                                   ensure_ascii=False),
                status_code=status, media_type="application/json")
        await response(scope, receive, send)


def create_app(config: RunConfig, trace: Optional[TraceWriter] = None) -> FastAPI:
    state = WorldState(config)
    trace = trace or TraceWriter(config.trace_path, run_id=config.run_id,
                                 seed=config.seed, system=config.system,
                                 task_id=config.task_id)
    ctx = AppContext(config=config, state=state, trace=trace,
                     matcher=TripwireMatcher())

    # /docs is the document-store service; FastAPI's own UI pages are disabled
    # (the OpenAPI spec itself stays available at /openapi.json).
    app = FastAPI(title="tripwire-pilot world", docs_url=None, redoc_url=None)
    app.state.ctx = ctx

    for service in (auth, inventory, pricing, shipping, docs, repo):
        app.include_router(service.router)

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    @app.post("/admin/inject")
    def admin_inject(spec: InjectionSpec) -> dict:
        """Tests and manual tooling ONLY. Comparative runs must use exclusively
        the counter-triggered middleware path (M1 amendment 3)."""
        detail = apply_injection(state, spec)
        state.admin_injections.append(detail)
        trace.emit(
            actor="admin",
            event_type="injection_fired",
            payload={"trigger": "admin", "counter": state.counter,
                     "injection": detail},
        )
        return {"ok": True, "applied": detail}

    @app.post("/admin/arm_tripwires")
    def admin_arm(tripwire_set: TripwireSet) -> dict:
        """Arm (or re-arm after a replan) the compiled tripwire set. Resets
        matcher state and tripped-worker flags: a fresh plan starts clean."""
        ctx.matcher.arm(tripwire_set)
        state.tripped_workers.clear()
        return {"ok": True, "armed": len(tripwire_set.tripwires),
                "plan_id": tripwire_set.plan_id,
                # D5 condition: per-tripwire dialect, decided and recorded at
                # arm time ("dead" = pattern can never match any world path)
                "pattern_modes": {tw.id: (ctx.matcher.pattern_mode(tw.id) or "dead")
                                  for tw in tripwire_set.tripwires
                                  if tw.signal.url_pattern}}

    @app.post("/admin/clear_tripped")
    def admin_clear_tripped(body: dict) -> dict:
        """Forgive a worker lineage after a NOISE verdict: without this, a
        redispatched worker that presents the old id keeps receiving the stale
        409 control and re-escalates the same adjudicated noise forever."""
        for worker_id in body.get("worker_ids", []):
            state.tripped_workers.pop(worker_id, None)
        return {"ok": True, "tripped_workers": sorted(state.tripped_workers)}

    @app.post("/admin/suppress")
    def admin_suppress(body: dict) -> dict:
        """Suppress one tripwire after a NOISE verdict (the sentinel tier has
        adjudicated it; refiring would loop the same noise forever)."""
        ctx.matcher.suppress(body["tripwire_id"])
        return {"ok": True, "suppressed": sorted(ctx.matcher.suppressed)}

    @app.get("/admin/ground_truth")
    def admin_ground_truth() -> dict:
        """Programmatic success checkers compare final answers against this
        snapshot (admin path: never counted, never visible to workers)."""
        shipping_nested: dict[str, dict[str, Any]] = {}
        for (sku, dest), entry in state.shipping.items():
            shipping_nested.setdefault(sku, {})[dest] = entry
        return {
            "prices": state.prices,
            "inventory": state.inventory,
            "shipping": shipping_nested,
            "passages": {pid: {"title": p["title"], "content": p["content"]}
                         for pid, p in state.passages.items()},
            "repo_files": state.repo_files,
        }

    @app.get("/admin/state")
    def admin_state() -> dict:
        return {
            "counter": state.counter,
            "injection_fired": state.injection_fired,
            "injection_fired_at": state.injection_fired_at,
            "admin_injections": state.admin_injections,
            "removed_routes": sorted(state.removed_routes),
            "trapped_gates": sorted(state.trapped_gates),
            "pricing_drift": state.pricing_drift,
            "active_tokens": len(state.active_tokens),
            "revoked_tokens": len(state.revoked_tokens),
            "armed_tripwires": [t.id for t in ctx.matcher.tripwires],
            "suppressed_tripwires": sorted(ctx.matcher.suppressed),
            "tripped_workers": sorted(state.tripped_workers),
        }

    app.add_middleware(WorldMiddleware, ctx=ctx)
    return app


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="tripwire-pilot world server")
    parser.add_argument("--port", type=int, default=8400)
    parser.add_argument("--config", type=str, default=None,
                        help="path to a RunConfig JSON file (conductor-provided)")
    args = parser.parse_args(argv)

    if args.config:
        with open(args.config, encoding="utf-8") as fh:
            config = RunConfig.model_validate(json.load(fh))
    else:
        # manual default for `make serve`; never used by comparative runs
        config = RunConfig(run_id="manual", seed=1, system="manual",
                           task_id="manual", trace_path="runs/manual/trace.jsonl")

    import uvicorn

    uvicorn.run(create_app(config), host="127.0.0.1", port=args.port,
                log_level="warning")


if __name__ == "__main__":
    main()
