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
import functools
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
from world.injections import (DEPRECATION_BODY, QUOTA_EXHAUSTED_BODY,
                              apply_injection)
from world import noise  # A7 benign-noise (D36); gated on config.noise_profile
from world.pagination import TOTAL_COUNT_KEY
from world.state import InjectionSpec, RunConfig, WorldState
from world.services import auth, docs, inventory, meta, pricing, regions, repo, shipping

_MISSING = object()

# D8 ablation switch for analysis replays ONLY (the 2x2 would-catch table):
# True restores pre-D8 strict pointer semantics. Production runs never set it.
STRICT_POINTERS = False

@functools.lru_cache(maxsize=1)
def get_path_samples() -> tuple[str, ...]:
    """D13: the canonical concrete-path sample is derived MECHANICALLY from
    the world's own fixtures — routes from the OpenAPI spec, parameterized
    segments instantiated from the fixture keys they range over ({sku} ->
    catalog SKUs, {passage_id} -> corpus ids, {path} -> fixture repo files).
    No hand-listing: the previous hand-curated tuple misclassified three
    exact-path patterns as dead (false negatives in the mechanized observable
    bit AND a latent live-matcher detection loss, fixed prospectively here)."""
    from world.state import PASSAGES, REPO_FILES, SKUS
    from world.surface import _openapi_paths
    samples: set[str] = set()
    for path in _openapi_paths():
        if "{" not in path:
            samples.add(path)
            continue
        if "{sku}" in path:
            samples.update(path.replace("{sku}", sku) for sku in SKUS)
        if "{passage_id}" in path:
            samples.update(path.replace("{passage_id}", p["id"])
                           for p in PASSAGES)
        if "{path}" in path:
            samples.update(path.replace("{path}", f) for f in REPO_FILES)
    return tuple(sorted(samples))


def classify_url_pattern(pattern: str,
                         samples: Optional[tuple[str, ...]] = None) -> Optional[str]:
    """deviations.md D5: url_pattern is matched as a glob per the DSL comment,
    but the frozen compile prompt gives the model no way to know that, and
    compiled sets reliably emit regex-style patterns. Classification is static
    and deterministic, decided once at arm time against the derived sample
    (D13): glob if the pattern glob-matches any sample, else regex if it
    regex-matches any sample, else None (a dead pattern that never matches).

    `samples` defaults to the rev-1 derived sample (byte-identical Phase 1
    behavior for every existing caller); the v2 pattern-liveness sweep (D24,
    #7-class fix) passes rev-aware samples explicitly."""
    if samples is None:
        samples = get_path_samples()
    if any(fnmatchcase(p, pattern) for p in samples):
        return "glob"
    try:
        rx = re.compile(pattern)
    except re.error:
        return None
    if any(rx.search(p) for p in samples):
        return "regex"
    return None


def _pointer_lookup(body: Any, pointer: str) -> Any:
    """Resolve a JSON pointer (RFC6901-style '/a/b'; dotted 'a.b' and
    JSONPath-style '$.a.b' tolerated — deviations.md D8: the frozen prompt
    cannot transmit the pointer dialect, and compiled sets use all three)
    against a parsed response body. Returns _MISSING when unresolvable."""
    if pointer.startswith("$") and not STRICT_POINTERS:
        pointer = pointer[1:].lstrip(".")
        if not pointer:
            return body
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
        self.last_suppressed: list[Tripwire] = []
        # D11: tripwires in consecutive-NOISE cooldown -> the evidence
        # instances (status + declared-field null pattern) that were NOISE'd
        self.cooldowns: dict[str, list[dict]] = {}

    def arm(self, tripwire_set: TripwireSet) -> None:
        self.tripwires = list(tripwire_set.tripwires)
        self.suppressed.clear()
        self._touch_seen.clear()
        self._call_history.clear()
        self.cooldowns.clear()  # D11: a fresh set resets all cooldowns
        self._pattern_mode = {
            tw.id: classify_url_pattern(tw.signal.url_pattern)
            for tw in self.tripwires if tw.signal.url_pattern
        }

    def pattern_mode(self, tripwire_id: str) -> Optional[str]:
        return self._pattern_mode.get(tripwire_id)

    def suppress(self, tripwire_id: str) -> None:
        self.suppressed.add(tripwire_id)

    def install_cooldown(self, tripwire_id: str, instances: list[dict]) -> None:
        self.cooldowns[tripwire_id] = list(instances)

    def cooldown_check(self, tw: Tripwire, evidence: dict) -> bool:
        """D11 exit conditions. True -> still cooled (suppress, no control);
        False -> exited (cooldown removed; treat as a normal fire). Exit iff
        the new evidence differs in status-class from EVERY NOISE'd instance:
        different _status, or any declared field transitioning null<->non-null."""
        instances = self.cooldowns.get(tw.id)
        if instances is None:
            return False
        new_status = evidence.get("_status")
        new_nulls = sorted(f for f in tw.evidence_fields
                           if evidence.get(f) is None)

        def differs(instance: dict) -> bool:
            return (new_status != instance.get("status")
                    or new_nulls != sorted(instance.get("null_fields", [])))

        if all(differs(i) for i in instances):
            del self.cooldowns[tw.id]
            return False
        return True

    def get(self, tripwire_id: str) -> Optional[Tripwire]:
        return next((t for t in self.tripwires if t.id == tripwire_id), None)

    def evaluate(self, *, method: str, path: str, status: int,
                 body: Any) -> list[Tripwire]:
        matched, suppressed = [], []
        for tw in self.tripwires:
            if not self._matches(tw, method, path, status, body):
                continue
            (suppressed if tw.id in self.suppressed else matched).append(tw)
        # what the NOISE policy ate this call (D7); read by the middleware
        # right after evaluate() — single-threaded server, no races
        self.last_suppressed = suppressed
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


# D9: hard byte cap on the evidence excerpt floor (UTF-8 bytes, stated in
# deviations.md).
EXCERPT_CAP_BYTES = 600

# Compiled evidence_fields name the same observables under many spellings;
# a too-literal resolver hands the judge all-null evidence and every genuine
# escalation gets ruled NOISE (observed live, S5 attempt 4). D9: this table
# is a committed fixed artifact; the exact mapping is restated in
# deviations.md and must stay in sync.
_EVIDENCE_ALIASES = {
    "status": "status", "status_code": "status", "http_status": "status",
    "code": "status", "response_status": "status",
    "path": "path", "url": "path", "endpoint": "path", "request_url": "path",
    "method": "method", "http_method": "method",
    "counter": "counter",
    "body": "__body__", "response_body": "__body__", "raw_response": "__body__",
    "response": "__body__", "raw_response_body": "__body__",
    "passage_content": "__body__", "content": "__body__",
}


def build_control(tw: Tripwire, *, method: str, path: str, status: int,
                  counter: int, body: Any) -> dict:
    """The tripwire_control object embedded in the worker's tool response.
    Evidence is resolved here so the worker can copy it with zero reasoning.
    The judge's frozen prompt promises "actual tool response excerpts", so a
    response excerpt, status, and path are ALWAYS included as a floor even
    when the compiled evidence_fields resolve to nothing."""
    meta = {"status": status, "path": path, "method": method, "counter": counter}
    evidence: dict[str, Any] = {}
    for field in tw.evidence_fields:
        alias = _EVIDENCE_ALIASES.get(field.lower().lstrip("/_"))
        if alias == "__body__":
            evidence[field] = body
        elif alias is not None:
            evidence[field] = meta[alias]
        else:
            value = _pointer_lookup(body, field)
            evidence[field] = None if value is _MISSING else value
    excerpt = (body if isinstance(body, str)
               else json.dumps(body, ensure_ascii=False))
    evidence.setdefault("_status", status)
    evidence.setdefault("_path", path)
    evidence.setdefault("_response_excerpt",
                        (excerpt or "").encode("utf-8")[:EXCERPT_CAP_BYTES]
                        .decode("utf-8", errors="ignore"))
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

        # v2 probe side channel (v6.1 §11.9 amendment #1; archaeology_v2 G7):
        # probe traffic observes without perturbing — it must not advance the
        # injection-clock counter (vector 1), not enter the token stream
        # (vector 2), not touch the validated_docs sentinel (vector 3), and
        # mutate no world state at all; it never meets the matcher, controls,
        # or tripped-worker enforcement. Flag-gated: banked and pre-1b
        # configs default probe_channel=False, making the marker header
        # inert (the request counts as ordinary worker traffic), so Phase 1
        # behavior is byte-identical.
        if config.probe_channel:
            probe_headers = {k.decode("latin-1").lower(): v.decode("latin-1")
                             for k, v in scope.get("headers", [])}
            if "x-probe-channel" in probe_headers:
                await self._respond_probe(scope, receive, send)
                return

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

        # quota_cliff post-exhaustion: the recurring 429 is answered at the
        # boundary (endpoint_404 pattern) so the family never executes again
        # this run. 429s are not billable and never decrement.
        if state.quota_metered(path) and state.quota_remaining == 0:
            await self._respond(scope, receive, send, n, method, path, query,
                                worker_id, request_body=None, status=429,
                                body=dict(QUOTA_EXHAUSTED_BODY))
            return

        # A7 transient_500 benign noise (D36; gated on config.noise_profile). The
        # seed-derived trigger call 500s once at the boundary, then heals — a retry
        # dispatches normally. Benign: no state mutated; S1 recovers (qualification).
        # Off (no-op, no state change) for every non-A7 run → Phase-1 byte-identical.
        if noise.trip_transient_500(state, n, path):
            # Record WHICH call the transient landed on (token vs first surface call)
            # so FIR scoring can separate "monitor saw the anomaly and stayed calm"
            # from "anomaly never reached an observed surface" (author spec, A7).
            ctx.trace.emit(
                actor="world", event_type="noise_fired",
                payload={"noise_class": "transient_500", "counter": n, "path": path,
                         "landed_on": "token" if path == "/auth/token" else "surface"})
            await self._respond(scope, receive, send, n, method, path, query,
                                worker_id, request_body=None, status=500,
                                body=dict(noise.TRANSIENT_500_BODY))
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

    async def _respond_probe(self, scope: Scope, receive: Receive,
                             send: Send) -> None:
        """The perturbation-isolated probe path. READ-ONLY by construction:
        only GET/HEAD are dispatched (a state-mutating handler can therefore
        never execute on this channel — vectors 2 and 3 are closed at the
        transport, not by handler discipline); boundary checks and response
        transforms are pure reads; the only bookkeeping is the separate
        probe-metering sequence (probe_seq), which no worker-visible or
        Phase 1 code path consumes."""
        ctx = self.ctx
        state = ctx.state
        method = scope["method"]
        path = scope["path"]
        query = scope.get("query_string", b"").decode("utf-8", errors="replace")

        state.probe_seq += 1
        k = state.probe_seq
        ctx.trace.emit(actor="probe", event_type="probe_call",
                       payload={"probe_seq": k, "method": method, "path": path,
                                "query": query})

        async def finish(status: int, body: Any,
                         extra_headers: Optional[dict[str, str]] = None) -> None:
            # HEAD over the side channel = the GET's status and headers with
            # the body suppressed (FastAPI routes do not serve HEAD natively;
            # the probe transport provides the HEAD-equivalent read E.2 names).
            ctx.trace.emit(actor="probe", event_type="probe_response",
                           payload={"probe_seq": k, "status": status,
                                    "body": None if method == "HEAD" else body})
            if method == "HEAD":
                response = Response(content=b"", status_code=status,
                                    media_type="application/json",
                                    headers=extra_headers or None)
            elif isinstance(body, str):
                response = Response(content=body, status_code=status,
                                    media_type="text/plain",
                                    headers=extra_headers or None)
            else:
                response = Response(
                    content=json.dumps(body, separators=(",", ":"),
                                       ensure_ascii=False),
                    status_code=status, media_type="application/json",
                    headers=extra_headers or None)
            await response(scope, receive, send)

        if method not in ("GET", "HEAD"):
            await finish(405, {"error": "probe_channel_read_only",
                               "detail": "the probe side channel dispatches "
                                         "GET/HEAD only; state-mutating "
                                         "methods are refused at the "
                                         "transport boundary"})
            return

        # Boundary views the worker path also serves, replicated as pure
        # reads so probes observe the same broken world workers would.
        if state.route_removed(path):
            await finish(404, dict(DEPRECATION_BODY))
            return
        if state.quota_metered(path) and state.quota_remaining == 0:
            await finish(429, dict(QUOTA_EXHAUSTED_BODY))
            return

        start_message: dict = {}
        body_chunks: list[bytes] = []
        done = {"sent": False}

        async def send_buffered(message: dict) -> None:
            if message["type"] == "http.response.start":
                start_message.update(message)
                return
            if message["type"] == "http.response.body":
                body_chunks.append(message.get("body", b""))
                if not message.get("more_body", False) and not done["sent"]:
                    done["sent"] = True
                    body = _parse_json(b"".join(body_chunks))
                    extra: dict[str, str] = {}
                    if state.config.world_rev >= 2:
                        extra["X-API-Version"] = state.service_version(path)
                    if isinstance(body, dict) and TOTAL_COUNT_KEY in body:
                        extra["X-Total-Count"] = str(body.pop(TOTAL_COUNT_KEY))
                    if state.quota_metered(path):
                        # read-only view: NO decrement on the probe path
                        extra["X-Quota-Remaining"] = str(state.quota_remaining)
                    await finish(start_message["status"], body, extra)
                return
            await send(message)

        # HEAD dispatches as GET (routes serve GET only); finish() suppresses
        # the body, so the handler executes the identical pure read.
        dispatch_scope = (dict(scope, method="GET") if method == "HEAD"
                          else scope)
        await self.app(dispatch_scope, receive, send_buffered)

    async def _respond(self, scope: Scope, receive: Receive, send: Send, n: int,
                       method: str, path: str, query: str, worker_id: str, *,
                       request_body: Any, status: int, body: Any) -> None:
        ctx = self.ctx
        state = ctx.state

        # Held-out-category surface (rev >= 2; benchmark/holdouts/*.md),
        # applied BEFORE matching and tracing so the matcher and the trace
        # both see exactly what the worker sees.
        extra_headers: dict[str, str] = {}
        if state.config.world_rev >= 2:
            extra_headers["X-API-Version"] = state.service_version(path)
        # DV spec rev 2 (rev 3 worlds): list totals live in the X-Total-Count
        # header, never in the body — the route ships the count under a
        # reserved key that is popped here (race-free: it rides the response).
        if isinstance(body, dict) and TOTAL_COUNT_KEY in body:
            extra_headers["X-Total-Count"] = str(body.pop(TOTAL_COUNT_KEY))
        if state.quota_metered(path):
            if status < 400:  # billable call: 4xx/5xx (incl. the 429s) never bill
                state.quota_remaining = max(0, state.quota_remaining - 1)
            extra_headers["X-Quota-Remaining"] = str(state.quota_remaining)
            if isinstance(body, dict):
                body = {**body, "quota_remaining": state.quota_remaining}

        # A7 benign-noise response decoration (D36; gated on config.noise_profile). Adds
        # the constant elapsed_ms envelope on every A7 response (+ the latency spike at the
        # seed-derived call) and, for the additive_field class, one extra unused field.
        # Worker traffic only (the probe channel is _respond_probe, untouched). Off (no-op)
        # for every non-A7 run → byte-identical to Phase 1. Placed before the matcher and
        # the trace so the monitor and the worker both see exactly the same body.
        if noise.active(state):
            body = noise.decorate_body(state, n, body)

        ctx.trace.emit(
            actor=worker_id,
            event_type="tool_call",
            payload={"counter": n, "method": method, "path": path,
                     "query": query, "body": request_body},
        )

        # Pure predicate matching against the outgoing response.
        control: Optional[dict] = None
        matched = ctx.matcher.evaluate(method=method, path=path, status=status,
                                       body=body)
        for tw in getattr(ctx.matcher, "last_suppressed", []):
            ctx.trace.emit(
                actor="world", event_type="suppressed_refire",
                payload={"where": "matcher", "counter": n, "tripwire_id": tw.id,
                         "path": path, "status": status,
                         "worker_id": worker_id})
        for tw in matched:
            log_only = tw.action.on_trigger == "LOG"
            candidate: Optional[dict] = None
            if not log_only and tw.id in ctx.matcher.cooldowns:
                candidate = build_control(tw, method=method, path=path,
                                          status=status, counter=n, body=body)
                if ctx.matcher.cooldown_check(tw, candidate["evidence"]):
                    # D11: consecutive-NOISE cooldown eats the match, no judge
                    ctx.trace.emit(
                        actor="world", event_type="suppressed_refire",
                        payload={"where": "cooldown", "counter": n,
                                 "tripwire_id": tw.id, "path": path,
                                 "status": status, "worker_id": worker_id})
                    continue
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
                control = candidate or build_control(tw, method=method,
                                                     path=path, status=status,
                                                     counter=n, body=body)

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
                                media_type="text/plain",
                                headers=extra_headers or None)
        else:
            response = Response(
                content=json.dumps(body, separators=(",", ":"),
                                   ensure_ascii=False),
                status_code=status, media_type="application/json",
                headers=extra_headers or None)
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
    if config.world_rev >= 2:
        # rev-2-only surface: keeps rev-1 OpenAPI, D13 path samples, and
        # banked-trace replays byte-identical (benchmark/holdouts/*.md)
        app.include_router(meta.router)
    if config.n_regions:
        # benchmark_1c regions surface — registered ONLY when n_regions is set, so
        # every existing task's OpenAPI, D13 path samples, surface appendix, and
        # replays stay byte-identical (same discipline as the rev-2 meta router and
        # the probe-channel gate-shadow). Existing configs default n_regions=None.
        app.include_router(regions.router)
    if config.probe_channel:
        # v2 §4 gate-shadow surface (read-only enforcement re-read; build B5).
        # Registered ONLY on probe-channel worlds, so banked/Phase-1 OpenAPI,
        # D13 path samples, and replays stay byte-identical (probe_channel
        # defaults off, and every sample-derivation builds the app with it off).
        from world.services import gate_shadow
        app.include_router(gate_shadow.router)

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
        """Manual/diagnostic hard suppression. Comparative runs use the D11
        cooldown path instead."""
        ctx.matcher.suppress(body["tripwire_id"])
        return {"ok": True, "suppressed": sorted(ctx.matcher.suppressed)}

    @app.post("/admin/cooldown")
    def admin_cooldown(body: dict) -> dict:
        """D11: install a consecutive-NOISE cooldown with the NOISE'd evidence
        instances ({status, null_fields}); exits per cooldown_check."""
        ctx.matcher.install_cooldown(body["tripwire_id"],
                                     body.get("instances", []))
        return {"ok": True, "cooldowns": sorted(ctx.matcher.cooldowns)}

    @app.get("/admin/ground_truth")
    def admin_ground_truth() -> dict:
        """Programmatic success checkers compare final answers against this
        snapshot (admin path: never counted, never visible to workers)."""
        shipping_nested: dict[str, dict[str, Any]] = {}
        for (sku, dest), entry in state.shipping.items():
            shipping_nested.setdefault(sku, {})[dest] = entry
        gt = {
            "prices": state.prices,
            "inventory": state.inventory,
            "shipping": shipping_nested,
            "passages": {pid: {"title": p["title"], "content": p["content"]}
                         for pid, p in state.passages.items()},
            "repo_files": state.repo_files,
        }
        # benchmark_1c (additive, conditional on n_regions): the checker rebuilds the
        # canonical clean world from (n, seed) to validate the allocation packages.
        # Admin-path only (never counted / never in the worker traffic the byte-identity
        # replay checks); for existing tasks n_regions is None and nothing is added.
        if config.n_regions:
            gt["n"] = config.n_regions
            gt["seed"] = config.seed
        return gt

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
            # D31: the validated_docs sentinel exposed for the §4 non-perturbation
            # trapdoor's vector 3, read counter-neutrally (this endpoint is
            # middleware-excluded) instead of via a counting canary POST.
            "validated_docs": len(state.validated_docs),
            "quota_family": sorted(state.quota_family),
            "quota_remaining": state.quota_remaining,
            "bump_family": sorted(state.bump_family),
            "bumped_version": state.bumped_version,
            "bumped_page_size": state.bumped_page_size,
            "armed_tripwires": [t.id for t in ctx.matcher.tripwires],
            "suppressed_tripwires": sorted(ctx.matcher.suppressed),
            "cooldowns": sorted(ctx.matcher.cooldowns),
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
