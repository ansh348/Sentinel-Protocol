"""World server: FastAPI app factory, tool-traffic middleware, /admin endpoints.

Locked architecture decision #3: the middleware (i) increments the global tool-call
counter, (ii) fires the injection when the counter hits N_inject, (iii) evaluates
the active tripwire set against each outgoing response with pure predicate matching
(no LLM calls in the middleware, ever — M1 ships a stub matcher with no active set),
(iv) on a match embeds a tripwire_control object in the response, and (v) appends
every event to the run's JSONL trace.

Injection timing semantics: the counter increments when a countable request
arrives; if it reaches N_inject the mutation is applied BEFORE the request is
dispatched, so call number N_inject is the first to observe the broken world.

One process serves exactly one run (locked decision #2); the conductor starts one
uvicorn instance per run on a port from 8400-8407 and kills it afterwards.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Any, Optional

from fastapi import FastAPI, Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from trace import TraceWriter
from world.injections import DEPRECATION_BODY, apply_injection
from world.state import InjectionSpec, RunConfig, WorldState
from world.services import auth, docs, inventory, pricing, repo, shipping


class TripwireMatcher:
    """Pure-predicate tripwire matcher slot. M1 stub: no active tripwire set, so it
    never matches. M2 loads a compiled TripwireSet here and returns a
    tripwire_control dict when a predicate matches a response. Never an LLM call."""

    def evaluate(self, *, method: str, path: str, status: int,
                 body: Any) -> Optional[dict]:
        return None


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
    buffered (and, from M2 on, rewritten) without BaseHTTPMiddleware's caveats."""

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

        # endpoint_404: removed routes are answered at the middleware boundary so
        # the deprecation body is identical no matter which router owned the path.
        if state.route_removed(path):
            ctx.trace.emit(
                actor=worker_id,
                event_type="tool_call",
                payload={"counter": n, "method": method, "path": path,
                         "query": query, "body": None},
            )
            ctx.trace.emit(
                actor=worker_id,
                event_type="tool_response",
                payload={"counter": n, "status": 404, "body": DEPRECATION_BODY},
            )
            response = JSONResponse(status_code=404, content=DEPRECATION_BODY)
            await response(scope, receive, send)
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
                    await self._flush(scope, send, n, method, path, query,
                                      worker_id, req_chunks, start_message,
                                      body_chunks)
                return
            await send(message)

        await self.app(scope, receive_teed, send_buffered)

    async def _flush(self, scope: Scope, send: Send, n: int, method: str,
                     path: str, query: str, worker_id: str,
                     req_chunks: list[bytes], start_message: dict,
                     body_chunks: list[bytes]) -> None:
        ctx = self.ctx
        status = start_message["status"]
        raw = b"".join(body_chunks)
        response_body = _parse_json(raw)
        request_body = _parse_json(b"".join(req_chunks)) if req_chunks else None

        ctx.trace.emit(
            actor=worker_id,
            event_type="tool_call",
            payload={"counter": n, "method": method, "path": path,
                     "query": query, "body": request_body},
        )

        control = ctx.matcher.evaluate(method=method, path=path, status=status,
                                       body=response_body)
        if control is not None:
            # M2 wires this: embed tripwire_control into the JSON body, emit a
            # tripwire_fire event, and rewrite content-length before sending.
            raise NotImplementedError("tripwire matching arrives in M2")

        ctx.trace.emit(
            actor=worker_id,
            event_type="tool_response",
            payload={"counter": n, "status": status, "body": response_body},
        )

        await send(start_message)
        await send({"type": "http.response.body", "body": raw, "more_body": False})


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
    def admin_inject(spec: InjectionSpec, request: Request) -> dict:
        """Tests and manual tooling ONLY. Comparative runs must use exclusively
        the counter-triggered middleware path (M1 amendment 3); analysis can
        verify that via the trigger field on injection_fired events."""
        detail = apply_injection(state, spec)
        state.admin_injections.append(detail)
        trace.emit(
            actor="admin",
            event_type="injection_fired",
            payload={"trigger": "admin", "counter": state.counter,
                     "injection": detail},
        )
        return {"ok": True, "applied": detail}

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
