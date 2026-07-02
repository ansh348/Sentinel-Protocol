#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dv_claim_verify.py -- ARCHAEOLOGY / VERIFICATION / NOT FROZEN / NOT CONFIRMATORY.  $0.

Read-only verification of the fse_draft4.md §7 DEPENDENCY_VERSION claim against the 20 banked
DV cells. Reproduces the per-sub-claim evidence in runs/matrix_1b/dv_claim_verification.md.
No new run, no spend, no treatment-code change.
"""
from __future__ import annotations
import json, glob, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
RUNS = ROOT / "runs" / "matrix_1b" / "runs"
SEEDS = ["s2088", "s2505", "s3191", "s3741", "s7101"]


def load(rd):
    out = []
    for fn in ("trace.jsonl", "trace_world.jsonl"):
        p = Path(rd) / fn
        if p.exists():
            for l in p.read_text(encoding="utf-8").splitlines():
                if l.strip(): out.append(json.loads(l))
    return out


def listing_count(b):
    if isinstance(b, dict):
        for k in ("files", "items", "entries", "results"):
            if isinstance(b.get(k), list): return len(b[k])
    return len(b) if isinstance(b, list) else None


def main():
    # clean reference
    clean = None
    for d in sorted(glob.glob(str(RUNS / "b1-*-clean-*"))):
        es = load(d); tc = {}
        for e in es:
            p = e.get("payload") or {}
            if e["event_type"] == "tool_call": tc[p.get("counter")] = (p.get("path"), p.get("query"))
        for e in es:
            p = e.get("payload") or {}
            if e["event_type"] == "tool_response":
                path, q = tc.get(p.get("counter"), (None, None))
                if path == "/repo/files" and not q:
                    clean = listing_count(p.get("body")); break
        if clean: break
    print(f"CLEAN /repo/files bare listing = {clean} files")

    print("\nQ1/Q3 — V2 arm-time baseline of /repo/files (count + pre/post injection):")
    for s in SEEDS:
        es = load(RUNS / f"b1-V2-silent_minor_bump-{s}")
        inj = next((e for e in es if e["event_type"] == "injection_fired"), None)
        psz = inj["payload"]["injection"].get("page_size_to"); inj_ts = inj.get("ts")
        fws = next((e.get("ts") for e in es if e["event_type"] == "worker_start"), None)
        pcall = {}
        for e in es:
            p = e.get("payload") or {}
            if e["event_type"] == "probe_call": pcall[p.get("probe_seq")] = (p.get("path"), e.get("ts"))
        base = None
        for e in es:
            p = e.get("payload") or {}
            if e["event_type"] == "probe_response":
                path, pts = pcall.get(p.get("probe_seq"), (None, None))
                if path == "/repo/files" and fws and pts and pts < fws:
                    base = (listing_count(p.get("body")), "POST-inj" if pts > inj_ts else "PRE-inj"); break
        print(f"  {s}: page_size_to={psz}  arm-baseline files={base[0]} ({base[1]})  "
              f"clean={clean} -> baseline {'DIRTY (truncated)' if base[0]!=clean else 'clean'}")

    print("\nQ2 — version token in any observed payload:")
    hits = sum(1 for d in glob.glob(str(RUNS / "b1-*-silent_minor_bump-*"))
               for e in load(d) if e["event_type"] in ("tool_response", "probe_response")
               and any(t in json.dumps(e.get("payload", {}).get("body")) for t in ('"version"', "version_to", "2.0.0")))
    print(f"  version-token hits across 20 DV cells = {hits}")

    print("\nQ4 — /repo/files re-read post-worker (V2):")
    for s in SEEDS:
        es = load(RUNS / f"b1-V2-silent_minor_bump-{s}")
        fws = next((e.get("ts") for e in es if e["event_type"] == "worker_start"), None)
        pcall = {}
        for e in es:
            p = e.get("payload") or {}
            if e["event_type"] == "probe_call": pcall[p.get("probe_seq")] = (p.get("path"), e.get("ts"))
        n = sum(1 for e in es if e["event_type"] == "probe_response"
                and (pcall.get(e["payload"].get("probe_seq"), (None, None))[0] == "/repo/files")
                and (pcall.get(e["payload"].get("probe_seq"), (None, None))[1] or 0) > (fws or 0))
        print(f"  {s}: /repo/files re-read {n}x post-worker")

    print("\nQ5 — S2 escalations on DV:")
    for s in SEEDS:
        es = load(RUNS / f"b1-S2-silent_minor_bump-{s}")
        ints = [e for e in es if e["event_type"] in ("interrupt", "escalation")]
        if ints:
            d = (ints[0].get("payload") or {}).get("evidence", {})
            print(f"  S2 {s}: FIRED on {d.get('path')} (false interrupt; not the DV)")
        else:
            print(f"  S2 {s}: no escalation")
    print("\nARCHAEOLOGY / VERIFICATION / NOT FROZEN / NOT CONFIRMATORY")


if __name__ == "__main__":
    main()
