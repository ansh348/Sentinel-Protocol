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


# -- order-sensitive and relational/join reads (B1; design v0.4 §1.1/§2.1) -----
#
# Two GENERIC lenses (Rule Zero: ontology-general, no category) that the
# value-blind schema fingerprint and the single-surface value read cannot
# express:
#   * ORDER/SEQUENCE — schema_fingerprint is a SORTED SET, so a reorder of a
#     load-bearing array is invisible to it; ordered_subarray / ordered_digest
#     are order-sensitive by construction. (The position-pinned read is the
#     other order flavor and is already expressible as read_field on an indexed
#     pointer, e.g. read_field(r, "/results/0/sku").)
#   * RELATIONAL/JOIN — a relation that holds ACROSS surfaces (referential
#     coverage / foreign-key / set equality). It has no single-surface clean
#     baseline, so the typing engine treats RELATION_BROKEN as fire-on-its-own,
#     exempt from transition-typing (design v0.4 §2.1).
#
# All four accept either a ProbeResult or an already-parsed body, so the lenses
# work on live probe observations and on pure synthetic fixtures alike.


def _body_of(observation: Any) -> Any:
    return observation.body if isinstance(observation, ProbeResult) else observation


def _canonical(value: Any) -> Any:
    """Hashable, order-faithful rendering: containers canonicalize to
    sorted-key JSON (element equality is value-based); scalars pass through."""
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False)
    return value


def _array_at(observation: Any, pointer: str) -> list:
    arr = _pointer_lookup(_body_of(observation), pointer)
    if arr is _MISSING or not isinstance(arr, list):
        raise KeyError(f"pointer {pointer!r} does not resolve to a list")
    return arr


def _project(arr: list, pointer: str, field: Optional[str]):
    if field is None:
        for item in arr:
            yield _canonical(item)
        return
    for i, item in enumerate(arr):
        value = _pointer_lookup(item, field)
        if value is _MISSING:
            raise KeyError(f"field {field!r} unresolvable in element {i} "
                           f"of {pointer!r}")
        yield _canonical(value)


def ordered_subarray(observation: Any, pointer: str, *,
                     field: Optional[str] = None) -> tuple:
    """The ORDERED sequence of the array at `pointer` (optionally projecting
    each element to `field`, in the pointer dialect). Order-SENSITIVE: a reorder
    changes the result, unlike schema_fingerprint (a value-blind sorted set).
    Raises KeyError if the pointer is not a list or `field` is unresolvable in
    an element (a shape problem, surfaced loudly, not silently dropped)."""
    arr = _array_at(observation, pointer)
    return tuple(_project(arr, pointer, field))


def ordered_digest(observation: Any, pointer: str, *,
                   field: Optional[str] = None) -> str:
    """SHA-256 of the ordered sub-array (the 'sub-array hash' order lens):
    a compact, deterministic, order-sensitive comparable for ORDER_CHANGED."""
    seq = ordered_subarray(observation, pointer, field=field)
    raw = json.dumps(list(seq), separators=(",", ":"),
                     ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def project_keys(observation: Any, pointer: str, *,
                 field: Optional[str] = None) -> frozenset:
    """The SET of values at array `pointer` (optionally projected to `field`).
    Set semantics — the building block for cross-surface coverage relations
    (use ordered_subarray when ORDER, not membership, is load-bearing)."""
    arr = _array_at(observation, pointer)
    return frozenset(_project(arr, pointer, field))


@dataclass(frozen=True)
class JoinResult:
    """Outcome of a cross-surface relation check. `holds` is the verdict;
    `left_only`/`right_only` are the witnessing keys (RELATION_BROKEN evidence)."""
    relation: str
    holds: bool
    left_only: tuple
    right_only: tuple


def relation_holds(left: Any, left_pointer: str, right: Any, right_pointer: str,
                   *, left_field: Optional[str] = None,
                   right_field: Optional[str] = None,
                   relation: str = "subset") -> JoinResult:
    """Evaluate a GENERIC relation ACROSS two surfaces (the RELATION_BROKEN
    lens). relation='subset': referential coverage — every key on the left must
    resolve on the right (foreign-key / coverage). relation='equal': the two
    key sets must match (bijective coverage). No single-surface baseline is
    involved; the verdict is the relation predicate evaluated directly."""
    left_keys = project_keys(left, left_pointer, field=left_field)
    right_keys = project_keys(right, right_pointer, field=right_field)
    left_only = tuple(sorted(left_keys - right_keys, key=repr))
    right_only = tuple(sorted(right_keys - left_keys, key=repr))
    if relation == "subset":
        holds = not left_only
    elif relation == "equal":
        holds = not left_only and not right_only
    else:
        raise ValueError(f"unknown relation {relation!r} (subset|equal)")
    return JoinResult(relation=relation, holds=holds,
                      left_only=left_only, right_only=right_only)
