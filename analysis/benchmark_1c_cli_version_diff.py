#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
benchmark_1c_cli_version_diff.py  --  FEASIBILITY / NOT FROZEN

Diffs the CLI 2.1.170 (Phase-1b SUT) vs 2.1.193 (last-task / current) /v1/messages
request SHAPE, auth held constant (ANTHROPIC_API_KEY), inputs fixed.  Answers: does
the 23-patch drift change what the API sees?  Separates version-tag-only deltas
(billing cc_version string) from real structural deltas.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PAIRS = {
    "compile": ("runs/matrix_1c/pathA_capture.jsonl", "runs/matrix_1c/pathA_capture_170.jsonl"),
    "worker":  ("runs/matrix_1c/pathA_worker_capture.jsonl", "runs/matrix_1c/pathA_worker_capture_170.jsonl"),
}


def load(p):
    return [json.loads(l) for l in open(ROOT / p, encoding="utf-8") if l.strip()]


def classify(rec):
    b = rec.get("body") or {}
    oc = b.get("output_config") or {}
    if b.get("model", "").startswith("claude-haiku") and isinstance(oc.get("format"), dict):
        return "title"          # CLI auto-title call
    if b.get("tools"):
        return "agent"          # tool-bearing worker turn
    if b.get("model", "").startswith("claude-sonnet"):
        return "compile"        # the Sonnet compile
    return "other"


def norm_billing(text):
    # strip the version token so we can tell version-tag-only from structural diffs
    return re.sub(r"cc_version=[0-9.]+(\.[a-z0-9]+)?", "cc_version=<VER>", text or "")


def beta_set(rec):
    hb = rec.get("headers", {}).get("anthropic-beta", "")
    return set(s.strip() for s in hb.split(",") if s.strip())


def shape(rec):
    b = rec.get("body") or {}
    sysb = b.get("system") or []
    blocks = []
    for blk in (sysb if isinstance(sysb, list) else []):
        t = blk.get("text", "") if isinstance(blk, dict) else str(blk)
        blocks.append({"len": len(t), "norm_len": len(norm_billing(t)),
                       "cache_control": bool(isinstance(blk, dict) and blk.get("cache_control")),
                       "head": norm_billing(t)[:40]})
    tools = b.get("tools") or []
    tool_sig = sorted([(t.get("name") or t.get("type") or "?",
                        hashlib.sha256(json.dumps(t.get("input_schema") or t.get("schema") or {}, sort_keys=True).encode()).hexdigest()[:8])
                       for t in tools])
    return {
        "model": b.get("model"), "max_tokens": b.get("max_tokens"),
        "temperature": b.get("temperature"), "thinking": b.get("thinking"),
        "output_config": b.get("output_config"),
        "has_context_management": "context_management" in b,
        "top_keys": sorted(b.keys()),
        "n_system_blocks": len(sysb) if isinstance(sysb, list) else 0,
        "system_blocks": blocks,
        "n_tools": len(tools), "tool_names": [n for n, _ in tool_sig], "tool_sig": tool_sig,
        "path": rec.get("path"),
        "beta": sorted(beta_set(rec)),
    }


def diff_shapes(a, b):
    diffs = []
    for k in ("model", "max_tokens", "temperature", "thinking", "output_config",
              "has_context_management", "n_system_blocks", "n_tools", "path", "top_keys"):
        if a.get(k) != b.get(k):
            diffs.append((k, a.get(k), b.get(k)))
    # beta flags (set diff)
    if a["beta"] != b["beta"]:
        only193 = sorted(set(a["beta"]) - set(b["beta"]))
        only170 = sorted(set(b["beta"]) - set(a["beta"]))
        diffs.append(("anthropic_beta", f"only-193:{only193}", f"only-170:{only170}"))
    # system blocks: compare normalized lengths + cache_control
    for i in range(max(len(a["system_blocks"]), len(b["system_blocks"]))):
        ba = a["system_blocks"][i] if i < len(a["system_blocks"]) else None
        bb = b["system_blocks"][i] if i < len(b["system_blocks"]) else None
        if ba is None or bb is None:
            diffs.append((f"system[{i}]", ba, bb)); continue
        if ba["norm_len"] != bb["norm_len"] or ba["cache_control"] != bb["cache_control"]:
            diffs.append((f"system[{i}]_norm", f"len={ba['norm_len']},cc={ba['cache_control']}",
                          f"len={bb['norm_len']},cc={bb['cache_control']}"))
        elif ba["len"] != bb["len"]:
            diffs.append((f"system[{i}]_VERSIONTAGONLY", f"raw_len={ba['len']}", f"raw_len={bb['len']}"))
    # tool catalog
    if a["tool_names"] != b["tool_names"]:
        diffs.append(("tool_names", set(a["tool_names"]) ^ set(b["tool_names"]), "symmetric-diff"))
    elif a["tool_sig"] != b["tool_sig"]:
        changed = [n for (n, h1), (_, h2) in zip(a["tool_sig"], b["tool_sig"]) if h1 != h2]
        diffs.append(("tool_schemas_changed", changed, ""))
    return diffs


def main():
    report = {"FEASIBILITY": True, "FROZEN": False,
              "auth_held_constant": "ANTHROPIC_API_KEY (same harness as the saved 2.1.193 capture)",
              "v193": "saved pathA_capture (native claude.exe 2.1.193)",
              "v170": "pathA_capture_170 (npm-bundled native claude.exe 2.1.170, Phase-1b SUT)",
              "sites": {}}
    P = print
    P("=" * 92)
    P("CLI VERSION DIFF  2.1.170 (Phase-1b) vs 2.1.193 (current)  --  FEASIBILITY / NOT FROZEN")
    P("=" * 92)
    overall_structural = 0
    for site, (p193, p170) in PAIRS.items():
        a_all, b_all = load(p193), load(p170)
        a_by = {classify(r): shape(r) for r in a_all}
        b_by = {classify(r): shape(r) for r in b_all}
        roles = [r for r in ("compile", "agent", "title", "other") if r in a_by or r in b_by]
        P(f"\n### site={site}  (193 roles={sorted(a_by)} | 170 roles={sorted(b_by)})")
        report["sites"][site] = {}
        for role in roles:
            if role not in a_by or role not in b_by:
                P(f"  [{role}] present in only one version: 193={role in a_by} 170={role in b_by}")
                report["sites"][site][role] = {"present_193": role in a_by, "present_170": role in b_by}
                continue
            d = diff_shapes(a_by[role], b_by[role])
            structural = [x for x in d if "VERSIONTAGONLY" not in x[0]]
            overall_structural += len(structural)
            report["sites"][site][role] = {
                "n_diffs": len(d), "n_structural": len(structural),
                "diffs": [{"field": f, "v193": str(x)[:120], "v170": str(y)[:120]} for f, x, y in d],
                "v193_shape": {k: a_by[role][k] for k in ("model", "n_system_blocks", "n_tools", "thinking", "output_config", "max_tokens")},
                "v170_shape": {k: b_by[role][k] for k in ("model", "n_system_blocks", "n_tools", "thinking", "output_config", "max_tokens")},
            }
            tag = "IDENTICAL" if not d else (f"{len(structural)} STRUCTURAL + {len(d)-len(structural)} version-tag-only" if structural else f"{len(d)} version-tag-only (behavior-neutral)")
            P(f"  [{role}] {tag}")
            for f, x, y in d:
                mark = "  ~tag " if "VERSIONTAGONLY" in f else "  !!   "
                P(f"{mark}{f}:  193={str(x)[:80]}   170={str(y)[:80]}")
    report["overall_structural_diffs"] = overall_structural
    verdict = ("IDENTICAL modulo auth+version-tag -> drift MOOT; 1c can run on either; 1b-comparability holds"
               if overall_structural == 0 else
               "STRUCTURAL DIFFERENCES -> 1c MUST pin 2.1.170 to match 1b (see diffs)")
    report["verdict"] = verdict
    P(f"\n=== VERDICT: {verdict} ===")
    P(f"    total structural diffs across sites: {overall_structural}")

    out = ROOT / "runs/matrix_1c/cli_version_diff.json"
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    P(f"[written] {out}")
    return report


if __name__ == "__main__":
    main()
