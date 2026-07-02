"""Dump what each A7 false-interrupt actually fired on (noise-attribution + 500-landing story)."""
import json, os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROWS = [json.loads(l) for l in open(os.path.join(REPO, "runs", "a7", "a7_results.jsonl"), encoding="utf-8") if l.strip()]


def trace(rd, which):
    p = os.path.join(REPO, rd, which)
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()] if os.path.exists(p) else []


# every FIR cell that had ANY interrupt / escalation
for r in [x for x in ROWS if x["phase"] == "fir" and x["status"] == "ran"]:
    ev = trace(r["run_dir"], "trace.jsonl")
    wev = trace(r["run_dir"], "trace_world.jsonl")
    esc = [e for e in ev if e["event_type"] in ("escalation", "interrupt", "dismissal")]
    fires = [e["payload"] for e in wev if e["event_type"] == "tripwire_fire"]
    if not esc and not fires:
        continue
    print(f"\n### {r['key']}  success={r['success']}  landing={r.get('noise_landed_on')}")
    for e in esc:
        p = e["payload"]
        if e["event_type"] == "escalation":
            tw = p.get("tripwire_id") or p.get("tripwire", {})
            evd = p.get("evidence", {})
            keys = list(evd.keys()) if isinstance(evd, dict) else evd
            print(f"   ESCALATION tw={tw} evidence_keys={keys} "
                  f"status={evd.get('_status') if isinstance(evd,dict) else '?'} "
                  f"path={evd.get('_path') if isinstance(evd,dict) else '?'}")
        elif e["event_type"] == "interrupt":
            tw = p.get("tripwire", {})
            print(f"   INTERRUPT tw_id={tw.get('id') if isinstance(tw,dict) else tw} "
                  f"verdict={(p.get('verdict') or {}).get('verdict') if p.get('verdict') else None}")
        else:
            print(f"   DISMISSAL reason={p.get('reason','')[:80]}")
    for f in fires:
        print(f"   world tripwire_fire: tw={f.get('tripwire_id')} path={f.get('path')} status={f.get('status')}")
