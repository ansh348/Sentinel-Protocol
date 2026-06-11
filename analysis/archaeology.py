"""POST-VERDICT ARCHAEOLOGY extraction (EXPLORATORY — the 2026-06-11 KG1-KG4
verdict stands as computed; nothing here recomputes, re-scores, or
reinterprets any gate quantity). Feeds analysis/archaeology_v1.md.

Reads traces only, via the instrument's own helpers (analysis.metrics), so
strict detection/attribution here is the gate's own rule applied per cell —
mirrored for diagnosis, never re-derived differently.
"""
from __future__ import annotations

import json
import random
import sys
from fnmatch import fnmatchcase
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from analysis.gates import INJECTION_CATEGORY, cell_run_dir  # noqa: E402
from analysis.metrics import (_attributable, _touch_events,  # noqa: E402
                              first_attributable_pause, injection_info,
                              surface_predicate)
from trace import read_run  # noqa: E402

RUNS = REPO_ROOT / "runs"
CELLS = json.loads((REPO_ROOT / "analysis" / "matrix_manifest.json")
                   .read_text(encoding="utf-8"))

CANONICAL_STATUS = {"endpoint_404": 404, "token_expiry": 401}


def latest_run(cell):
    return cell_run_dir(RUNS, cell)


def armed_tripwires(events):
    """All tripwires ever armed in the run (initial compile + recompiles)."""
    tws = []
    for e in events:
        if e["event_type"] == "tripwire_set":
            tws.extend((e["payload"] or {}).get("tripwires") or [])
    return tws


def covers_on_paper(tw, inj):
    """Heuristic paper-coverage check (EXPLORATORY, mirrors KG0's
    would-catch spirit): a tripwire covers the injection if its signal's
    status_in contains the canonical status, or its url_pattern glob-matches
    the injected surface, or (doc_contradiction) it is a contradicts_assumption
    tripwire whose pattern touches the passage path."""
    sig = tw.get("signal") or {}
    pattern = sig.get("url_pattern") or ""
    status_in = sig.get("status_in") or []
    t = inj["type"]
    if t in CANONICAL_STATUS and CANONICAL_STATUS[t] in status_in:
        return True
    pred = surface_predicate(t, inj["params"])
    # test the pattern against canonical surface paths
    paths = []
    if t in ("endpoint_404", "gate_skip_trap"):
        paths = [inj["params"].get("path", "").replace("*", "x")]
        if pattern and inj["params"].get("path"):
            # glob-vs-glob intersection heuristic: identical or one matches
            # the other with wildcards collapsed
            p_inj = inj["params"]["path"]
            if (fnmatchcase(p_inj.replace("*", "x"), pattern)
                    or fnmatchcase(pattern.replace("*", "x"), p_inj)):
                return True
    elif t == "schema_drift":
        prefix = ("/repo" if inj["params"].get("target") == "repo_config"
                  else "/pricing")
        if pattern.startswith(prefix) or pattern.startswith("*"):
            return True
    elif t == "doc_contradiction":
        target = f"/docs/passages/{inj['params'].get('passage_id', 'pol-returns')}"
        if pattern and (fnmatchcase(target, pattern) or pattern == target):
            return True
        if (tw.get("signal") or {}).get("type") == "contradicts_assumption":
            return True
    for p in paths:
        if p and pattern and fnmatchcase(p, pattern):
            return True
    return False


def chain_of_death(events, inj):
    """Assign DETECTED or the link of death for one injected S5 cell."""
    if inj is None:
        reason = next((e["payload"].get("reason") for e in events
                       if e["event_type"] == "run_end"), None)
        return "L0", f"injection never fired (run_end reason={reason})"
    if first_attributable_pause(events, inj) is not None:
        return "DETECTED", ""
    touches = _touch_events(events, inj)
    fire_touches = [e for e in touches if e["event_type"] == "tripwire_fire"]
    esc_touches = [e for e in touches if e["event_type"] == "escalation"]
    tws = armed_tripwires(events)
    if not fire_touches and not esc_touches:
        covering = [tw for tw in tws if covers_on_paper(tw, inj)]
        if not covering:
            return "L1", f"{len(tws)} tripwires armed, none cover the surface"
        ids = ",".join(tw.get("id", "?") for tw in covering[:3])
        return "L2", f"covered on paper ({ids}) but zero live surface fires"
    if fire_touches and not esc_touches:
        fire_ids = {e["payload"].get("tripwire_id") or
                    (e["payload"].get("tripwire") or {}).get("id", "?")
                    for e in fire_touches}
        supp = sum(1 for e in events if e["event_type"] == "suppressed_refire")
        cooldowns = sum(1 for e in events if e["event_type"] == "redispatch"
                        and (e["payload"] or {}).get("cooldown_installed"))
        return "L3", (f"{len(fire_touches)} surface fires ({','.join(sorted(fire_ids))})"
                      f" never escalated; {supp} suppressed_refires,"
                      f" {cooldowns} cooldown installs in run")
    # surface-touching escalations exist: judged?
    verdicts = []
    for e in events:
        if e["event_type"] == "judge_verdict":
            verdicts.append((e["payload"] or {}).get("verdict"))
    genuine = [v for v in verdicts if v in ("GENUINE", "WARNING")]
    pauses = [e for e in events if e["event_type"] == "pause"]
    if not genuine:
        return "L4", (f"{len(esc_touches)} surface escalations, judge verdicts="
                      f"{verdicts[:6]}{'...' if len(verdicts) > 6 else ''}, no GENUINE")
    if not [p for p in pauses if p["ts"] >= inj["ts"]]:
        return "L5", (f"GENUINE/WARNING present ({len(genuine)}) but no pause"
                      f" event at/after injection")
    return "L6", (f"{len(pauses)} pause(s) exist but none attributable"
                  f" (no surface touch precedes any pause)")


def soft_detected(events, inj):
    """EXPLORATORY generous reading: the injected surface produced at least
    one touch (tripwire_fire/escalation/tool_response 4xx per the 6.1
    predicate) AND the orchestrator took any interrupt-class action
    (interrupt/pause/replan) at or after the injection ts."""
    if inj is None:
        return False
    if not _touch_events(events, inj):
        return False
    return any(e["event_type"] in ("interrupt", "pause", "replan")
               and e["ts"] >= inj["ts"] for e in events)


def interrupt_anatomy(events, inj, cell):
    rows = []
    for e in events:
        if e["event_type"] != "interrupt":
            continue
        p = e["payload"] or {}
        tw = (p.get("tripwire") or {})
        ev = (p.get("evidence") or {})
        verdict = (p.get("verdict") or {}).get("verdict") if p.get("verdict") else None
        status = ev.get("_status") or ev.get("status")
        path = ev.get("_path") or ev.get("path") or ""
        ev_class = (f"status={status}" if status else
                    ("all-null" if not any(v for k, v in ev.items()
                                           if not k.startswith("_")) else "field"))
        rows.append({
            "cell": f"{cell['task']}/{cell['injection'] or 'clean'}/s{cell['seed']}",
            "clean": cell["injection"] is None,
            "tripwire": tw.get("id") or "(raw-anomaly)",
            "evidence": f"{ev_class} {path}".strip(),
            "verdict": verdict or "(unjudged)",
            "attributable": _attributable(events, inj, e),
        })
    return rows


def main():
    s5_cells = [c for c in CELLS if c["system"] == "S5"]
    chain_rows, anatomy, soft_flags, strict_flags = [], [], {}, {}
    for cell in s5_cells:
        rd = latest_run(cell)
        events = read_run(rd)
        inj = injection_info(events)
        key = (cell["task"], cell["injection"], cell["seed"])
        if cell["injection"] is not None:
            link, evidence = chain_of_death(events, inj)
            strict_flags[key] = (link == "DETECTED")
            soft_flags[key] = soft_detected(events, inj)
            chain_rows.append({
                "cell": f"{cell['task']}+{cell['injection']}/s{cell['seed']}",
                "category": INJECTION_CATEGORY[cell["injection"]],
                "link": link, "evidence": evidence, "dir": rd.name,
            })
        anatomy.extend(interrupt_anatomy(events, inj, cell))

    # pauses across ALL injected cells (all systems) for the 6.1 audit domain
    audit_domain = []
    for cell in CELLS:
        if cell["injection"] is None:
            continue
        rd = latest_run(cell)
        events = read_run(rd)
        inj = injection_info(events)
        pauses = [e for e in events if e["event_type"] == "pause"]
        if pauses:
            audit_domain.append({
                "cell": f"{cell['task']}/{cell['system']}/{cell['injection']}/s{cell['seed']}",
                "dir": rd.name, "n_pauses": len(pauses),
                "attributed": first_attributable_pause(events, inj) is not None,
                "injected_fired": inj is not None,
            })
    rng = random.Random(11)  # seed 11: the project's audit-sampling precedent
    sample = rng.sample(audit_domain, max(1, round(0.2 * len(audit_domain))))

    # self-injury: S1 vs S5 success splits + failed S5 clean cell facts
    def cell_facts(cell):
        rd = latest_run(cell)
        events = read_run(rd)
        sc = [e for e in events if e["event_type"] == "success_check"]
        success = bool(sc[-1]["payload"]["success"]) if sc else False
        return rd, events, success

    splits = {}
    for system in ("S1", "S5"):
        for injected in (False, True):
            sel = [c for c in CELLS if c["system"] == system
                   and (c["injection"] is not None) == injected]
            n_ok = sum(1 for c in sel if cell_facts(c)[2])
            splits[f"{system}/{'injected' if injected else 'clean'}"] = \
                f"{n_ok}/{len(sel)}"

    injury = []
    for cell in [c for c in CELLS if c["system"] == "S5"
                 and c["injection"] is None]:
        rd, events, success = cell_facts(cell)
        if success:
            continue
        first_int = next((e for e in events if e["event_type"] == "interrupt"), None)
        replans = [e for e in events if e["event_type"] == "replan"]
        carrym = [len((e["payload"] or {}).get("completed_results") or [])
                  for e in events if e["event_type"] == "interrupt"]
        agg = next((e for e in reversed(events)
                    if e["event_type"] == "aggregate"
                    and "final_report" in (e["payload"] or {})), None)
        used = (agg["payload"].get("used") if agg else None)
        disc = (agg["payload"].get("discarded") if agg else None)
        run_end = next((e["payload"] for e in events
                        if e["event_type"] == "run_end"), {})
        sc = [e for e in events if e["event_type"] == "success_check"]
        injury.append({
            "cell": f"{cell['task']}/clean/s{cell['seed']}", "dir": rd.name,
            "interrupt_before_end": first_int is not None,
            "n_replans": len(replans),
            "carryover_sizes": carrym,
            "used": used, "discarded": disc,
            "run_end_reason": run_end.get("reason"),
            "checker_detail": (sc[-1]["payload"]["detail"][:90] if sc else None),
        })

    # per-category strict recall + soft recall (mirrored grouping)
    per_cat = {}
    for key, det in strict_flags.items():
        cat = INJECTION_CATEGORY[key[1]]
        d = per_cat.setdefault(cat, {"strict": 0, "soft": 0, "n": 0})
        d["n"] += 1
        d["strict"] += 1 if det else 0
        d["soft"] += 1 if soft_flags[key] else 0

    out = {
        "chain": chain_rows,
        "per_category": per_cat,
        "strict_total": f"{sum(strict_flags.values())}/{len(strict_flags)}",
        "soft_total": f"{sum(soft_flags.values())}/{len(soft_flags)}",
        "anatomy": anatomy,
        "audit_domain": audit_domain,
        "audit_sample_seed11": sample,
        "success_splits": splits,
        "self_injury": injury,
    }
    (RUNS / "archaeology_data.json").write_text(
        json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items()
                      if k in ("strict_total", "soft_total", "per_category",
                               "success_splits")}, indent=1))
    print("\nchain-of-death links:")
    from collections import Counter
    print(dict(Counter(r["link"] for r in chain_rows)))
    print(f"\nanatomy rows: {len(anatomy)} | audit domain: {len(audit_domain)}"
          f" | sample: {len(sample)} | injury cells: {len(injury)}")
    print("full data -> runs/archaeology_data.json")


if __name__ == "__main__":
    main()
