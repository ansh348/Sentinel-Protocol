"""Read-only probe executor primitives (v6.1 §11.9 amendment #1; the
pre-holdout mechanical probe designs of phase1b_precommitments.md E.2).

GENERIC primitives only (Rule Zero): HTTP reads over the perturbation-
isolated side channel plus deterministic extraction helpers — pointer
field reads (the matcher's own D8 dialect tolerance, so probes and
predicates can never disagree on a pointer), case-insensitive header
reads, content hashes, and the E.2 schema fingerprint (the sorted
key:type set of a JSON payload). No category-specific probe types exist
here, and none may be added without the author present.

The executor's API surface is read-only BY CONSTRUCTION: it exposes get()
and head() and nothing else, and every request carries the side-channel
marker, so the world's transport guarantees (no counter advance, no
state mutation; world/server.py) apply to everything this module can do.

What this module deliberately does NOT contain (night-shift hard stops):
probe COMPILATION (what to probe, from which tripwire), corroboration
(what an ANOMALOUS read means for interrupts), and cadence semantics
(when to sweep) — see sentinel_v2.scheduler for the cadence interface.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from world.server import _MISSING, _pointer_lookup

PROBE_MARKER = {"X-Probe-Channel": "1"}
PROBE_ACTOR_HEADER = {"X-Worker-Id": "probe"}

_SENTINEL = object()


@dataclass(frozen=True)
class ProbeResult:
    """One side-channel observation: status, headers (lower-cased keys),
    parsed body. Deterministic value object; no clocks, no run state."""
    method: str
    path: str
    status: int
    headers: Mapping[str, str]
    body: Any


class ProbeExecutor:
    """Thin read-only client over the probe side channel. `client` is any
    object with .get()/.head() returning status_code/headers/content
    (httpx.Client against a live world, or the test client)."""

    def __init__(self, client, *, auth_token: Optional[str] = None) -> None:
        self._client = client
        # E.2's auth posture: probes RE-USE the most recently observed
        # bearer token; they never obtain one (the transport refuses
        # issuance anyway). The token is supplied, never minted here.
        self._auth_token = auth_token

    def _headers(self, extra: Optional[Mapping[str, str]] = None) -> dict:
        headers = {**PROBE_MARKER, **PROBE_ACTOR_HEADER}
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"
        if extra:
            headers.update(extra)
        return headers

    def _wrap(self, method: str, path: str, response) -> ProbeResult:
        raw = response.content
        try:
            body = json.loads(raw) if raw else None
        except ValueError:
            body = raw.decode("utf-8", errors="replace")
        return ProbeResult(method=method, path=path,
                           status=response.status_code,
                           headers={k.lower(): v
                                    for k, v in response.headers.items()},
                           body=body)

    def get(self, path: str, *, params: Optional[Mapping[str, str]] = None,
            headers: Optional[Mapping[str, str]] = None) -> ProbeResult:
        response = self._client.get(path, params=params,
                                    headers=self._headers(headers))
        return self._wrap("GET", path, response)

    def head(self, path: str, *,
             headers: Optional[Mapping[str, str]] = None) -> ProbeResult:
        response = self._client.head(path, headers=self._headers(headers))
        return self._wrap("HEAD", path, response)


# -- deterministic extraction helpers (zero-LLM, value-pure) -------------------

def read_field(result: ProbeResult, pointer: str, default: Any = _SENTINEL) -> Any:
    """Pointer read over the probe body using the matcher's own D8-tolerant
    lookup (RFC6901 / dotted / JSONPath-prefixed)."""
    value = _pointer_lookup(result.body, pointer)
    if value is _MISSING:
        if default is _SENTINEL:
            raise KeyError(f"pointer {pointer!r} unresolvable in probe body")
        return default
    return value


def read_header(result: ProbeResult, name: str,
                default: Optional[str] = None) -> Optional[str]:
    return result.headers.get(name.lower(), default)


def content_sha256(result: ProbeResult) -> str:
    """Anchored-content fingerprint (E.2): the hash of the canonicalized
    body — deterministic across runs because world payloads carry no
    wall-clock values."""
    if isinstance(result.body, (bytes, bytearray)):
        raw = bytes(result.body)
    elif isinstance(result.body, str):
        raw = result.body.encode("utf-8")
    else:
        raw = json.dumps(result.body, sort_keys=True,
                         separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def schema_fingerprint(payload: Any) -> tuple[str, ...]:
    """E.2's schema fingerprint: the sorted (key:type) set of a JSON
    payload. Lists fingerprint their element-key union, so a payload's
    shape — not its values — is what compares."""
    pairs: set[str] = set()

    def visit(node: Any, prefix: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                pairs.add(f"{prefix}{key}:{type(value).__name__}")
                visit(value, f"{prefix}{key}.")
        elif isinstance(node, list):
            for item in node:
                visit(item, prefix)

    visit(payload, "")
    return tuple(sorted(pairs))
