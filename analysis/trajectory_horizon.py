"""TASKS B + D (archaeology v2). EXPLORATORY — recomputes no gate quantity.

TASK B — trajectory distortion (Rival Story B, GPT-5.5): per L2 cell, the
timeline of first false (unattributable) interrupt, first replan, and
injected-surface visits before/after; cross-system same-seed check (did
S1/S2/S4 observe the injected surface at/after the injection counter where
S5 did not?). Classification rules, fixed a priori:

  - cells with post-injection surface observations are N/A-OBSERVED here
    (Task A adjudicated them; B asks why a surface was never RE-observed);
  - pre=0, post=0: NOISE-CONSUMED if the run died in the noise machinery
    (run_end reason escalation_loop/replan_loop, with >=1 false interrupt or
    an escalation grind); else UPSTREAM-COLLAPSE;
  - pre>0, post=0: REPLANNED-AWAY if a replan followed a false interrupt AND
    >=1 same-seed baseline (S1/S2/S4) visited the surface at/after the
    injection counter while S5 post-replan did not; TRUE-SINGLE-VISIT if no
    same-seed baseline re-visited the surface at/after the counter either
    (the surface is structurally single-visit); NOISE-CONSUMED if the run
    died in the noise machinery before any re-visit could happen.

TASK D — horizon confound (Rival Story D, GPT-5.5): per missed injected cell
(17 = 18 misses minus the L0 cell b1+gate_skip_trap/s1, which died before its
injection counter was ever reached and is horizon-unanalyzable by
construction — excluded with this note). Oracle visit index = first counter
at/after the injection at which the same-seed S1 run observed the injected
surface; death point = S5's last counter + run_end reason. Split, fixed a
priori with precedence NOISE-INDUCED > INJECTION-CAUSED > BASE-RATE:

  - RUN-COMPLETED: the run produced a final aggregate (no collapse at all;
    the miss is observational, not horizon) — checked first;
  - NOISE-INDUCED: run_end reason in (escalation_loop, replan_loop) and >=1
    false interrupt or >=20 post-injection non-surface fires;
  - INJECTION-CAUSED: >=3 of the last 10 tool responses carry the injected
    surface symptom under a NARROW evidence-bearing predicate (the broad 6.1
    predicate is degenerate for b1 schema_drift where every call is /repo):
    endpoint_404 -> 404 on the injected pattern; token_expiry -> 401;
    gate_skip_trap -> gate-path response with checks_run == 0;
    schema_drift(pricing) -> /pricing body with the renamed field;
    schema_drift(repo_config) -> settings.yaml content carrying the drifted
    key;
  - BASE-RATE: the same-seed S1 cell also failed its checker (agent-class
    failure present without any sentinel);
  - else UNCLEAR (hand-ruled in the document with a pointer).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from analysis.gates import cell_run_dir  # noqa: E402
from analysis.metrics import (_attributable, injection_info,  # noqa: E402
                              surface_predicate)
from trace import read_run  # noqa: E402

RUNS = REPO_ROOT / "runs"
OUT_DIR = RUNS / "archaeology_v2"

L2_CELLS = [
    ("a1", "endpoint_404", 1), ("a1", "endpoint_404", 2),
    ("a1", "schema_drift", 1), ("a1", "schema_drift", 3),
    ("a1", "token_expiry", 1),
    ("b1", "schema_drift", 2),
    ("b1", "gate_skip_trap", 2), ("b1", "gate_skip_trap", 3),
    ("c1", "doc_contradiction", 2),
    ("d1", "gate_skip_trap", 1),
    ("d1", "endpoint_404", 1), ("d1", "endpoint_404", 2),
]
OTHER_MISSES = [  # L1, L3, L4 rows from the v1 chain-of-death table
    ("a1", "schema_drift", 2),        # L1
    ("c1", "doc_contradiction", 3),   # L3
    ("d1", "gate_skip_trap", 3),      # L3
    ("b1", "schema_drift", 1),        # L4
    ("c1", "doc_contradiction", 1),   # L4
]
L0_EXCLUDED = ("b1", "gate_skip_trap", 1)


def load(task: str, system: str, injection: str, seed: int):
    cell = {"task": task, "system": system, "injection": injection,
            "seed": seed}
    rd = cell_run_dir(RUNS, cell)
    if rd is None:
        return None, None, None
    events = read_run(rd)
    return rd, events, injection_info(events)


def call_pairs(events) -> dict[int, dict]:
    """counter -> {path, method, status, body, ts} from paired call/response."""
    pairs: dict[int, dict] = {}
    for e in events:
        p = e.get("payload") or {}
        n = p.get("counter")
        if not isinstance(n, int):
            continue
        d = pairs.setdefault(n, {})
        if e["event_type"] == "tool_call":
            d["path"] = p.get("path") or ""
            d["method"] = p.get("method")
            d["ts"] = e["ts"]
        elif e["event_type"] == "tool_response":
            d["status"] = p.get("status")
            d["body"] = p.get("body")
    return pairs


def narrow_symptom(inj) -> "callable":
    """Evidence-bearing symptom predicate over (path, status, body)."""
    from fnmatch import fnmatchcase
    t, params = inj["type"], inj["params"]
    if t == "endpoint_404":
        pat = params.get("path", "*")
        return lambda p, s, b: fnmatchcase(p, pat) and s == 404
    if t == "token_expiry":
        return lambda p, s, b: s == 401
    if t == "gate_skip_trap":
        pat = params.get("path", "*")
        return lambda p, s, b: (fnmatchcase(p, pat) and isinstance(b, dict)
                                and b.get("checks_run") == 0)
    if t == "schema_drift":
        if params.get("target") == "repo_config":
            return lambda p, s, b: (p.endswith("config/settings.yaml")
                                    and isinstance(b, dict)
                                    and "price_field" in str(b.get("content", "")))
        return lambda p, s, b: (p.startswith("/pricing")
                                and isinstance(b, dict)
                                and "unit_price" not in b and "price" in b)
    return lambda p, s, b: False


def run_completed(events) -> bool:
    return any(e["event_type"] == "aggregate"
               and (e.get("payload") or {}).get("final_report") is not None
               for e in events)


def surface_visits(pairs, pred) -> list[int]:
    return sorted(n for n, d in pairs.items()
                  if pred(d.get("path", ""), d.get("status")))


def run_end_reason(events) -> Optional[str]:
    return next((e["payload"].get("reason") for e in events
                 if e["event_type"] == "run_end"), None)


def task_b() -> list[dict]:
    rows = []
    for task, injection, seed in L2_CELLS:
        rd, events, inj = load(task, "S5", injection, seed)
        pred = surface_predicate(inj["type"], inj["params"])
        pairs = call_pairs(events)
        visits = surface_visits(pairs, pred)
        pre = [n for n in visits if n < inj["counter"]]
        post = [n for n in visits if n >= inj["counter"]]

        interrupts = [e for e in events if e["event_type"] == "interrupt"]
        false_ints = [e for e in interrupts
                      if not _attributable(events, inj, e)]
        replans = [e for e in events if e["event_type"] == "replan"]
        first_false = false_ints[0]["ts"] if false_ints else None
        first_replan = replans[0]["ts"] if replans else None
        post_replan_visits = ([n for n in visits
                               if (pairs[n].get("ts") or "") >= first_replan]
                              if first_replan else [])

        base = {}
        for system in ("S1", "S2", "S4"):
            brd, bev, binj = load(task, system, injection, seed)
            if bev is None or binj is None:
                base[system] = None
                continue
            bpred = surface_predicate(binj["type"], binj["params"])
            bvisits = surface_visits(call_pairs(bev), bpred)
            base[system] = {
                "n_inject": binj["counter"],
                "post_visits": [n for n in bvisits if n >= binj["counter"]],
                "dir": brd.name,
            }
        baseline_revisits = any(b and b["post_visits"] for b in base.values())

        reason = run_end_reason(events)
        noise_death = (reason in ("escalation_loop", "replan_loop")
                       and (false_ints or reason == "escalation_loop"))

        if post:
            cls = "N/A-OBSERVED (Task A adjudicates)"
        elif not pre:
            cls = "NOISE-CONSUMED" if noise_death else "UPSTREAM-COLLAPSE"
        else:  # pre>0, post==0
            if (first_replan and first_false and first_false <= first_replan
                    and baseline_revisits and not post_replan_visits):
                cls = "REPLANNED-AWAY"
            elif not baseline_revisits:
                cls = "TRUE-SINGLE-VISIT"
            elif noise_death:
                cls = "NOISE-CONSUMED"
            else:
                cls = "TRUE-SINGLE-VISIT (baseline revisits exist; no replan-"
                cls += "false-fire link)"
        rows.append({
            "cell": f"{task}+{injection}/s{seed}", "dir": rd.name,
            "n_inject": inj["counter"],
            "pre_visits": pre, "post_visits": post,
            "n_false_interrupts": len(false_ints),
            "first_false_interrupt_ts": first_false,
            "first_replan_ts": first_replan,
            "post_replan_visits": post_replan_visits,
            "run_end": reason,
            "baselines": base,
            "baseline_revisits_post_counter": baseline_revisits,
            "class": cls,
        })
    return rows


def task_d() -> list[dict]:
    rows = []
    for task, injection, seed in L2_CELLS + OTHER_MISSES:
        rd, events, inj = load(task, "S5", injection, seed)
        pred = surface_predicate(inj["type"], inj["params"])
        pairs = call_pairs(events)
        last_counter = max(pairs, default=0)
        reason = run_end_reason(events)

        srd, sev, sinj = load(task, "S1", injection, seed)
        s1 = {"dir": srd.name if srd else None}
        oracle = None
        if sev is not None and sinj is not None:
            spred = surface_predicate(sinj["type"], sinj["params"])
            spairs = call_pairs(sev)
            svisits = [n for n in surface_visits(spairs, spred)
                       if n >= sinj["counter"]]
            oracle = svisits[0] if svisits else None
            sc = [e for e in sev if e["event_type"] == "success_check"]
            s1.update(n_inject=sinj["counter"], oracle_visit=oracle,
                      post_visits=len(svisits),
                      last_counter=max(spairs, default=0),
                      success=bool(sc[-1]["payload"]["success"]) if sc
                      else None)

        interrupts = [e for e in events if e["event_type"] == "interrupt"]
        false_ints = [e for e in interrupts
                      if not _attributable(events, inj, e)]
        fires = [e["payload"] for e in events
                 if e["event_type"] == "tripwire_fire"
                 and e["payload"].get("counter", -1) >= inj["counter"]]
        nonsurface_fires = [f for f in fires
                            if not pred(f.get("path", ""), f.get("status"))]
        symptom = narrow_symptom(inj)
        tail = [pairs[n] for n in sorted(pairs)[-10:]]
        tail_symptoms = sum(1 for d in tail
                            if symptom(d.get("path", ""), d.get("status"),
                                       d.get("body")))

        if run_completed(events):
            split = "RUN-COMPLETED"
        elif (reason in ("escalation_loop", "replan_loop")
                and (false_ints or len(nonsurface_fires) >= 20)):
            split = "NOISE-INDUCED"
        elif tail_symptoms >= 3:
            split = "INJECTION-CAUSED"
        elif s1.get("success") is False:
            split = "BASE-RATE"
        else:
            split = "UNCLEAR"

        rows.append({
            "cell": f"{task}+{injection}/s{seed}", "dir": rd.name,
            "n_inject": inj["counter"],
            "s5_last_counter": last_counter, "s5_run_end": reason,
            "s5_died_before_oracle": (oracle is not None
                                      and last_counter < oracle),
            "oracle_reachable_for_S1": oracle is not None,
            "s1": s1,
            "n_false_interrupts": len(false_ints),
            "post_inj_nonsurface_fires": len(nonsurface_fires),
            "tail_symptom_responses": tail_symptoms,
            "split": split,
        })
    return rows


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    b = task_b()
    d = task_d()
    (OUT_DIR / "trajectory_horizon.json").write_text(
        json.dumps({"task_b": b, "task_d": d,
                    "l0_excluded": "b1+gate_skip_trap/s1 — died before its "
                    "injection counter; horizon-unanalyzable by construction"},
                   indent=1), encoding="utf-8")

    print("TASK B — trajectory classification (12 L2 cells)")
    print(f"{'cell':28s} {'pre':>4s} {'post':>4s} {'falseInt':>8s} "
          f"{'replan':>6s} {'baseRevisit':>11s}  class")
    for r in b:
        print(f"{r['cell']:28s} {len(r['pre_visits']):4d} "
              f"{len(r['post_visits']):4d} {r['n_false_interrupts']:8d} "
              f"{'Y' if r['first_replan_ts'] else 'n':>6s} "
              f"{'Y' if r['baseline_revisits_post_counter'] else 'n':>11s}  "
              f"{r['class']}")

    print("\nTASK D — horizon split (17 missed cells; L0 excluded)")
    print(f"{'cell':28s} {'nInj':>4s} {'last':>5s} {'oracle':>6s} "
          f"{'dieB4':>5s} {'S1ok':>4s} {'end':>16s}  split")
    for r in d:
        o = r["s1"].get("oracle_visit")
        print(f"{r['cell']:28s} {r['n_inject']:4d} {r['s5_last_counter']:5d} "
              f"{str(o) if o is not None else '-':>6s} "
              f"{'Y' if r['s5_died_before_oracle'] else 'n':>5s} "
              f"{str(r['s1'].get('success')):>4s} "
              f"{str(r['s5_run_end']):>16s}  {r['split']}")
    print(f"\ndetail -> {OUT_DIR / 'trajectory_horizon.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
