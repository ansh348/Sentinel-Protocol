"""tau-bench fault-injection harness (infrastructure only).

Deterministic, zero-LLM substrate for porting the TripwireBench fault-injection pattern
to tau-bench's retail domain. See docs/taubench_scoping_memo.md and PORT_NOTES.md.

This package contains: fault primitives (faults.py), the FaultedEnv wrapper
(faulted_env.py), instrumentation (instrumentation.py), and a NullUser stub (nulluser.py).
It deliberately contains NO check-writer, NO bars/thresholds, and NO comparative runs --
those are gated to the August pre-registration window.
"""
