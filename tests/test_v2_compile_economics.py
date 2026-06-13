"""C5 acceptance: compile cost discipline. One bounded compile call per run (+
one per replan), booked as overhead against the 12% clean cap."""
from __future__ import annotations

from conductor.sessions import SessionResult
from sentinel_v2.compile_probes import account_compile


def _r(cost: float) -> SessionResult:
    s = SessionResult(model="claude-sonnet-4-6", exit_code=0, stdout="", stderr="",
                      timed_out=False, duration_s=0.0)
    s.total_cost_usd_reported = cost
    return s


def test_one_bounded_call_per_run():
    econ = account_compile([[_r(0.20)]], worker_cost_usd=2.00)
    assert econ.n_compiles == 1 and econ.n_attempts == 1
    assert econ.compile_cost_usd == 0.20 and econ.bounded is True


def test_replan_adds_a_compile_call_booked_on_the_run():
    # run compile + one replan compile (keep-not-flush, D2): both booked
    econ = account_compile([[_r(0.20)], [_r(0.15)]], worker_cost_usd=4.00)
    assert econ.n_compiles == 2
    assert econ.compile_cost_usd == 0.35
    assert econ.overhead_usd == 0.35


def test_overhead_fraction_and_clean_cap():
    under = account_compile([[_r(0.06)]], worker_cost_usd=1.00)
    assert abs(under.overhead_fraction - 0.06) < 1e-9
    assert under.within_clean_cap() is True
    over = account_compile([[_r(0.20)]], worker_cost_usd=1.00)
    assert over.within_clean_cap() is False     # 20% > 12% — flagged, not blocked


def test_retry_counts_attempts_but_stays_bounded():
    econ = account_compile([[_r(0.10), _r(0.10)]], worker_cost_usd=2.00)
    assert econ.n_attempts == 2 and econ.n_compiles == 1 and econ.bounded is True


def test_unbounded_compile_is_flagged():
    econ = account_compile([[_r(0.1), _r(0.1), _r(0.1)]], worker_cost_usd=2.00)
    assert econ.bounded is False                # 3 attempts > 1 compile * MAX_ATTEMPTS


def test_probe_traffic_is_booked_as_overhead():
    econ = account_compile([[_r(0.05)]], worker_cost_usd=1.00, probe_cost_usd=0.03)
    assert econ.overhead_usd == 0.08
    assert abs(econ.overhead_fraction - 0.08) < 1e-9


def test_zero_worker_cost_is_infinite_overhead():
    econ = account_compile([[_r(0.05)]], worker_cost_usd=0.0)
    assert econ.overhead_fraction == float("inf") and econ.within_clean_cap() is False
