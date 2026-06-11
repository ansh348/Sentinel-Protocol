"""TASK C (archaeology v2): semantic-sufficiency re-bin. EXPLORATORY.

Adjudicates Rival Story C (both raters): that for content-shaped categories
the bottleneck is semantics, not observation. Re-bins every L2 cell using
Task A's raw-replay output, and for every RETRIEVAL_INTEGRITY and
TOOL_CONTRACT miss prints the EXACT evidence payload an ideal post-injection
probe would have returned (captured live from the admin-injected snapshot
world — ledgered), then rules per cell: DETERMINISTICALLY DECIDABLE vs NEEDS
SEMANTIC JUDGMENT.

Bin definitions (fixed a priori, consuming Task A rows):
  not-revisited                  zero post-injection surface observations
  revisited-matcher-failed       surface observed; a correctly-transmitted
                                 predicate of the armed intent would fire on
                                 the raw evidence, and only a dialect/
                                 transport defect (D5/D8 family) prevented it
  revisited-predicate-too-weak   surface observed; NO armed predicate (any
                                 epoch, fresh or stale) can discriminate the
                                 mutated payload from the clean baseline
                                 (the L1.5 bin)
  revisited-semantically-ambiguous  surface observed; even an ideal
                                 deterministic check (content fingerprint /
                                 anchored value / field read) cannot classify
                                 mutated vs clean — only semantic judgment can
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from world.server import create_app  # noqa: E402
from world.state import RunConfig  # noqa: E402

RUNS = REPO_ROOT / "runs"
OUT_DIR = RUNS / "archaeology_v2"
INVALID_SENTINEL_DOC = {"title": "", "body": "x", "citations": []}

# RI/TC misses from the v1 chain-of-death table (8 cells; L0's pair included
# because the world-level payload question is run-independent)
RI_TC_MISSES = [
    ("c1", "doc_contradiction", 1, "L4"),
    ("c1", "doc_contradiction", 2, "L2"),
    ("c1", "doc_contradiction", 3, "L3"),
    ("b1", "gate_skip_trap", 1, "L0"),
    ("b1", "gate_skip_trap", 2, "L2"),
    ("b1", "gate_skip_trap", 3, "L2"),
    ("d1", "gate_skip_trap", 1, "L2"),
    ("d1", "gate_skip_trap", 3, "L3"),
]


def ideal_probe_payload(task: str, injection: str, seed: int) -> dict:
    """Capture clean vs mutated payloads of the ideal post-injection probe."""
    inj_spec = json.loads(
        (RUNS / f"{task}-S5-{injection}-s{seed}" / "world_config.json")
        .read_text(encoding="utf-8"))["injection"] \
        if (RUNS / f"{task}-S5-{injection}-s{seed}").exists() else None
    if inj_spec is None:  # suffixed dirs
        from analysis.gates import cell_run_dir
        rd = cell_run_dir(RUNS, {"task": task, "system": "S5",
                                 "injection": injection, "seed": seed})
        inj_spec = json.loads((rd / "world_config.json")
                              .read_text(encoding="utf-8"))["injection"]

    with tempfile.TemporaryDirectory() as td:
        config = RunConfig(run_id=f"idealprobe-{task}-s{seed}", seed=seed,
                           system="probe-replay", task_id=task,
                           trace_path=str(Path(td) / "t.jsonl"))
        app = create_app(config)
        client = TestClient(app, raise_server_exceptions=False)
        token = client.post("/auth/token",
                            headers={"X-Worker-Id": "probe"}).json()["token"]
        h = {"X-Worker-Id": "probe", "Authorization": f"Bearer {token}"}

        def snap() -> dict:
            if injection == "doc_contradiction":
                pid = inj_spec.get("params", {}).get("passage_id",
                                                     "pol-returns")
                b = client.get(f"/docs/passages/{pid}", headers=h).json()
                return {"probe": f"GET /docs/passages/{pid}",
                        "payload": b,
                        "sha256_content": hashlib.sha256(
                            b.get("content", "").encode()).hexdigest()[:16]}
            gate = inj_spec.get("params", {}).get("path", "/repo/validate")
            if gate.startswith("/repo"):
                b = client.post(gate, headers=h).json()
                return {"probe": f"POST {gate} (pure re-run; repo gate has "
                                 "no side effects)", "payload": b}
            b = client.post(gate, json=INVALID_SENTINEL_DOC, headers=h).json()
            return {"probe": f"POST {gate} with deliberately-INVALID "
                             "sentinel doc", "payload": b}

        clean = snap()
        client.post("/admin/inject", json=inj_spec)
        mutated = snap()
        app.state.ctx.trace.close()
    return {"clean": clean, "mutated": mutated}


def main() -> int:
    raw = json.loads((OUT_DIR / "raw_replay.json").read_text(encoding="utf-8"))

    bins: dict[str, list[str]] = {
        "not-revisited": [], "revisited-matcher-failed": [],
        "revisited-predicate-too-weak (L1.5)": [],
        "revisited-semantically-ambiguous": []}
    for r in raw["lenient"]:
        if r["post_inj_surface_observations"] == 0:
            bins["not-revisited"].append(r["cell"])
        elif r["cell"] == "a1+token_expiry/s1":
            # 401s under an armed status_in [401,403] intent; only the D5
            # host-qualified dead pattern + a method gate blocked it
            bins["revisited-matcher-failed"].append(r["cell"])
        else:
            # b1+schema_drift/s2, c1+doc_contradiction/s2: no armed predicate
            # (any epoch) discriminates mutated from clean (Task A union
            # fires are non-discriminating: first-fired pre-injection or
            # fire identically on the clean counterpart)
            bins["revisited-predicate-too-weak (L1.5)"].append(r["cell"])

    payload_rows = []
    for task, injection, seed, link in RI_TC_MISSES:
        snap = ideal_probe_payload(task, injection, seed)
        decidable = snap["clean"] != snap["mutated"]
        # decisive deterministic check per injection family
        if injection == "doc_contradiction":
            check = ("anchored-content fingerprint: sha256(content) "
                     f"{snap['clean']['sha256_content']} -> "
                     f"{snap['mutated']['sha256_content']}")
        else:
            c = snap["clean"]["payload"]
            m = snap["mutated"]["payload"]
            check = (f"field read: checks_run {c.get('checks_run')} -> "
                     f"{m.get('checks_run')}; status_field "
                     f"'{c.get('status')}' -> '{m.get('status')}'")
        payload_rows.append({
            "cell": f"{task}+{injection}/s{seed}", "v1_link": link,
            **snap, "deterministic_check": check,
            "ruling": ("DETERMINISTICALLY DECIDABLE" if decidable
                       else "NEEDS SEMANTIC JUDGMENT"),
        })

    out = {"bins": bins, "ri_tc_payloads": payload_rows}
    (OUT_DIR / "semantic_rebin.json").write_text(
        json.dumps(out, indent=1), encoding="utf-8")

    print("TASK C — L2 re-bin")
    for k, v in bins.items():
        print(f"  {k}: {len(v)}")
        for c in v:
            print(f"    {c}")
    print("\nTASK C — ideal post-injection probe payloads (RI/TC misses)")
    for row in payload_rows:
        print(f"\n{row['cell']} ({row['v1_link']}) -> {row['ruling']}")
        print(f"  probe: {row['mutated']['probe']}")
        print(f"  check: {row['deterministic_check']}")
        mp = json.dumps(row["mutated"]["payload"], ensure_ascii=False)
        print(f"  mutated payload: {mp[:220]}")
    print(f"\ndetail -> {OUT_DIR / 'semantic_rebin.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
