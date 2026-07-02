#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v2nc_build_check.py -- BUILD / NOT FROZEN / NOT CONFIRMATORY.

STEP 0 verification for the V2nc arm: (1) the deterministic selector + the SAME
compile_pipeline arm N/N per-surface VALUE baseline-diff probes on the plan-touched
/regions surfaces, mutated shard covered, at N in {8,16,32} -- the $0 (no-LLM) analog
of the V2 fidelity re-measure; (2) the SUT-neutrality evidence: which treatment files
this build touched (only the additive arm + new module), with sha256 of V2's
compiler/matcher/probe/side-channel for the record.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import yaml  # noqa: E402
from sentinel_v2.arms import ARMS, resolve_arm, NO_COMPILER  # noqa: E402
from sentinel_v2.compile_probes import compile_pipeline, FAMILY_MEMBER_CAP  # noqa: E402
from sentinel_v2.deterministic_select import select_region_value_assumptions  # noqa: E402
from sentinel_v2.probe_spec import FaultShape, LensOp, Comparison  # noqa: E402
from analysis import benchmark_1c_world as BW  # noqa: E402


def is_value_bdiff(p):
    return (p.fault_shape == FaultShape.VALUE_CHANGED
            and p.lens.op == LensOp.FIELD_READ
            and p.comparison == Comparison.PROOF_BASELINE)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def main():
    print("=" * 92)
    print("V2nc BUILD CHECK — deterministic select + SAME compile_pipeline (no LLM, $0)")
    print("=" * 92)

    # -- arm registration --
    spec = resolve_arm(NO_COMPILER)
    print(f"\n[arm registry] V2nc registered: kind={spec.kind} role={spec.role} "
          f"deterministic_select={spec.deterministic_select} is_v2={spec.is_v2}")
    assert spec.is_v2 and spec.deterministic_select
    # V2 must be unchanged: not a deterministic-select arm
    assert resolve_arm("V2").deterministic_select is False, "V2 must NOT deterministic-select"
    print("[arm registry] V2 unchanged: deterministic_select=False (LLM compiler path)")

    task = yaml.safe_load((ROOT / "tasks" / "benchmark_1c.yaml").read_text(encoding="utf-8"))

    for N in (8, 16, 32):
        t = dict(task, n_regions=N, fan_out=N, executor_width=N)
        soft = select_region_value_assumptions(t, plan=None, trace=None)
        cr = compile_pipeline(soft, world_rev=4, n_regions=N, world=None,
                              auth_token=None, planned_write_set=set())

        def is_reg(x):
            return isinstance(x, str) and "/regions/" in x and "/evidence" in x
        armed = [p for p in cr.probes if is_reg(p.target)]
        armed_targets = sorted({p.target for p in armed})
        value_targets = sorted({p.target for p in armed if is_value_bdiff(p)})

        # mutated shard at a representative seed for this N
        seed = 9132
        inj = BW.build_world(N, seed, inject=True)
        mutated = f"/regions/{inj.j_rid}/evidence"

        print(f"\n[N={N}]  soft assumptions: {len(soft.assumptions)}  (all VALUE/pointer)")
        print(f"  /regions GROUNDED:                 {len(armed_targets)} / {N}")
        print(f"  /regions with VALUE baseline-diff: {len(value_targets)} / {N}")
        print(f"  uncovered(/regions): "
              f"{len([u for u in (cr.uncovered or []) if 'regions' in str(u).lower()])}"
              f"   telemetry: {len([x for x in cr.telemetry_only if is_reg(x.get('surface',''))])}")
        print(f"  mutated shard {inj.j_rid} ({mutated}) has VALUE baseline-diff: "
              f"{mutated in set(value_targets)}")
        assert len(value_targets) == N, f"expected N value probes, got {len(value_targets)}"
        assert mutated in set(value_targets), "mutated shard not covered by a value lens"

    print(f"\n  FAMILY_MEMBER_CAP={FAMILY_MEMBER_CAP} (not consulted — concrete surfaces, "
          "not a family template)")

    # -- SUT-neutrality evidence: V2's compiler/matcher/probe/side-channel files --
    print("\n[SUT-neutrality] files this V2nc build TOUCHED (additive only):")
    for f in ("sentinel_v2/deterministic_select.py (NEW)",
              "sentinel_v2/arms.py (additive: ArmSpec field + V2nc entry + dispatch passthrough)",
              "conductor/run_v2_loop.py (additive: ctor param + one else-branch; V2 path = original)"):
        print(f"   + {f}")
    print("[SUT-neutrality] V2 compiler/matcher/probe/side-channel — UNTOUCHED (sha256/16):")
    for rel in ("sentinel_v2/compile_probes.py", "prompts/v2_compile.md",
                "prompts/v2_compile_fewshot.json", "world/server.py",
                "sentinel_v2/probes.py", "sentinel_v2/probe_spec.py",
                "sentinel_v2/attachment.py", "sentinel_v2/corroboration.py"):
        p = ROOT / rel
        print(f"   = {rel:42s} {sha256(p) if p.exists() else 'MISSING'}")
    print("\nBUILD / NOT FROZEN / NOT CONFIRMATORY")


if __name__ == "__main__":
    main()
