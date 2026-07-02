"""A7 benign-noise decoration (harness-only, seed-derived, deterministic, benign).

Gated behind RunConfig.noise_profile (default None -> off -> byte-identical to Phase 1;
deviations D36). Three frozen classes (A7 pre-reg + addendum 2026-07-02):

  transient_500  -- the seed-derived trigger call 500s once, then heals (a retry succeeds).
  latency_spike  -- elapsed_ms spikes on the seed-derived call; otherwise the baseline.
  additive_field -- one extra, unused field ("advisory") on dict responses.

elapsed_ms is a CONSTANT ENVELOPE present on every A7 response (all classes), value
seed-derived, spiking only in a latency_spike run (D36 constant-envelope mitigation).
Applied to WORKER traffic only (the perturbation-isolated probe channel, _respond_probe,
is untouched). Benign by construction: transients heal, the additive field is unused, and
latency is a value only -- no real delay, no sleep, no wall-clock, no world-state mutation.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from world.state import WorldState

# Served (status 500) for the single transient_500 trigger call. Authored constant.
TRANSIENT_500_BODY = {
    "error": "internal_error",
    "detail": "A transient upstream error occurred; retry the request.",
}


def active(state: "WorldState") -> bool:
    """True only on an A7 run (noise_profile set). False -> the caller no-ops, so every
    non-A7 run takes the identical Phase-1 code path."""
    return state.config.noise_profile is not None


def trip_transient_500(state: "WorldState", n: int, path: str) -> bool:
    """True exactly once, then the retry heals. Default (noise_500_target is None): fires at
    the seed-derived trigger call, whatever surface that is (A7 behavior). A7b: when a target
    surface glob is set, fires on the FIRST worker call whose path matches it (monitored-surface
    placement). Always False for every other class and for non-A7 runs (trigger is None), with
    no state mutation, so those runs stay byte-identical."""
    if state.noise_500_trigger is None or state.noise_500_fired:
        return False
    target = state.noise_500_target
    if target is not None:
        from fnmatch import fnmatchcase
        if fnmatchcase(path, target):
            state.noise_500_fired = True
            return True
        return False
    if n >= state.noise_500_trigger:
        state.noise_500_fired = True
        return True
    return False


def decorate_body(state: "WorldState", n: int, body: Any) -> Any:
    """Add the constant elapsed_ms envelope (+ the latency spike at the seed-derived call)
    and, for the additive_field class, one extra unused field. Only dict bodies are
    decorated (a value field cannot be added to a string/None body). No required field is
    changed -- backward-compatible, benign. Caller gates on active(state)."""
    if not isinstance(body, dict):
        return body
    elapsed = state.noise_elapsed_base_ms
    if state.noise_latency_trigger is not None and n == state.noise_latency_trigger:
        elapsed = state.noise_elapsed_spike_ms
    out = {**body, "elapsed_ms": elapsed}
    if state.noise_additive_value is not None:
        out["advisory"] = state.noise_additive_value
    return out
