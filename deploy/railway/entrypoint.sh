#!/usr/bin/env bash
# Phase-1c Railway B2 entrypoint  --  FEASIBILITY / NOT FROZEN
# MODE: persist (HARD GATE) | equiv (STEP 3, vs 2.1.177 refs) | probe (STEP 4, real worker)
set -uo pipefail
DATA=/data
MODE="${MODE:-persist}"
mkdir -p "$DATA" 2>/dev/null || { echo "FATAL: cannot mkdir $DATA (volume not mounted / not root? set RAILWAY_RUN_UID=0)"; exit 2; }

echo "=== Railway B2 entrypoint  MODE=$MODE  $(date -u) ==="
echo "claude CLI: $(claude --version 2>&1 | head -1)   (MUST be 2.1.177 == real Phase-1b SUT)"
echo "ANTHROPIC_API_KEY: $([ -n "${ANTHROPIC_API_KEY:-}" ] && echo set || echo MISSING)   writable($DATA): $( ([ -w "$DATA" ] && echo yes) || echo NO )"

# ---------------- STEP 2: persistence proof (HARD GATE) ----------------
prior=$(ls "$DATA"/_persist_*.txt 2>/dev/null | head -1 || true)
if [ -n "$prior" ]; then
  echo "PERSIST: found prior -> $(cat "$prior")  => VOLUME SURVIVED REDEPLOY (PASS)"
else
  echo "PERSIST: no prior marker (first deploy) -- redeploy and re-check for SURVIVED"
fi
NEW="$DATA/_persist_$(cat /proc/sys/kernel/random/uuid).txt"
echo "uuid written $(date -u)" > "$NEW" && sync
echo "PERSIST: wrote $NEW"
[ "$MODE" = "persist" ] && { echo "=== persist-proof done; redeploy to confirm SURVIVED, then MODE=equiv ==="; exit 0; }

# ---------------- STEP 3: in-container equivalence vs 2.1.177 refs ----------------
if [ "$MODE" = "equiv" ]; then
  echo "=== STEP 3: capture in-container 2.1.177 requests, diff vs deploy/railway/refs (the saved 2.1.177) ==="
  python3 analysis/_capture_proxy.py 8799 "$DATA/incontainer_compile.jsonl" & PA=$!; sleep 1
  CAP_CLAUDE_BIN="$(command -v claude)" python3 analysis/_capture_pathA.py compile 8799 || true; kill $PA 2>/dev/null; sleep 0.3
  python3 analysis/_capture_proxy.py 8798 "$DATA/incontainer_worker.jsonl" & PB=$!; sleep 1
  CAP_CLAUDE_BIN="$(command -v claude)" python3 analysis/_capture_pathA.py worker 8798 || true; kill $PB 2>/dev/null
  python3 - "$DATA" <<'PY'
import json,sys
D=sys.argv[1]
def tset(path,pred):
    for l in open(path,encoding="utf-8"):
        if not l.strip():continue
        b=json.loads(l).get("body") or {}
        if pred(b): return sorted([t.get('name') or t.get('type') for t in (b.get('tools') or [])])
    return None
son=lambda b:b.get("model","").startswith("claude-sonnet")
agent=lambda b:b.get("model","").startswith("claude-haiku") and len(b.get("tools") or [])>0
ref_c=tset("deploy/railway/refs/pathA_capture_177.jsonl",son)
ref_w=tset("deploy/railway/refs/pathA_worker_capture_177.jsonl",agent)
new_c=tset(f"{D}/incontainer_compile.jsonl",son)
new_w=tset(f"{D}/incontainer_worker.jsonl",agent)
ok = (ref_c==new_c) and (ref_w==new_w)
print(f"compile tools  ref(177)={ref_c}  container={new_c}  MATCH={ref_c==new_c}")
print(f"worker  tools  ref(177)={len(ref_w) if ref_w else '?'}  container={len(new_w) if new_w else '?'}  MATCH={ref_w==new_w}")
print(f"EQUIVALENCE (modulo auth): {'PASS' if ok else 'FAIL -- container CLI is NOT the 2.1.177 1b SUT, STOP'}")
open(f"{D}/equiv_result.json","w").write(json.dumps({"compile_match":ref_c==new_c,"worker_match":ref_w==new_w,"pass":ok}))
PY
  exit 0
fi

# ---------------- STEP 4: real multi-turn worker concurrency probe ----------------
if [ "$MODE" = "probe" ]; then
  echo "=== STEP 4: REAL multi-turn worker ramp (B2); each rung append+flush to $DATA ==="
  python3 analysis/benchmark_1c_railway_probe.py --data "$DATA/railway_concurrency" --ramp "${RAMP:-16,32,64}"
  exit 0
fi
# ---------------- MODE=qual: V2 + V2nc §9 right-reason qualification ----------------
# Phase-1c. PREPARED (not deployed) so the §9 graded matrix can be re-run on the pinned
# Railway-Linux 2.1.177 SUT when authorized (qualification itself is OS/version-invariant
# and was first run locally; platform parity is REQUIRED for the CV pilot / confirmatory).
# Each cell = (arm, N, seed, condition) through the FULL conductor v2 loop; records
# append+flush to $DATA so a mid-run kill loses nothing. Pull $DATA afterwards.
if [ "$MODE" = "qual" ]; then
  echo "=== MODE=qual: V2/V2nc §9 right-reason qualification on Railway-Linux ==="
  export TRIPWIRE_V2=1
  # DEFAULTS = the deferred cell (V2 N=32, 1 seed, clean+injected). Override via env for
  # the full matrix. n_inject=2 fires at the first worker curl (token POST is counter-
  # advancing; arm-time baseline is side-channel/counter-neutral -> clean baseline).
  ARMS="${ARMS:-V2}"; NS="${NS:-32}"; SEEDS="${SEEDS:-9132}"
  CONDS="${CONDS:-clean,injected}"; NINJECT="${NINJECT:-2}"; CAP="${CAP:-10}"
  OUT="$DATA/v2_qualification/cells.jsonl"

  # (a) HARD version gate: the pinned 1b SUT is 2.1.177.
  VER="$(claude --version 2>&1 | head -1)"
  echo "claude CLI: $VER"
  if ! printf '%s' "$VER" | grep -q "2.1.177"; then
    echo "FATAL: in-container claude is not 2.1.177 (got: $VER) — STOP (pin parity required)"; exit 2
  fi
  # (b) /data persistence (the top-of-script persist marker already proved writability)
  echo "persistence: $(ls "$DATA"/_persist_*.txt 2>/dev/null | wc -l) marker(s) on $DATA (writable=$([ -w "$DATA" ] && echo yes || echo NO))"

  echo "--- cost estimate (no spend) ---"
  EST_OUT="$(python3 analysis/benchmark_1c_v2_qual.py --estimate --arms "$ARMS" --ns "$NS" \
      --seeds "$SEEDS" --conditions "$CONDS" --n-inject "$NINJECT")"
  echo "$EST_OUT"
  # (c) HARD COST CAP: parse projected total, abort if over CAP.
  EST=$(printf '%s\n' "$EST_OUT" | sed -n 's/.*projected ~\$\([0-9.]*\).*/\1/p' | head -1)
  echo "projected=\$$EST  cap=\$$CAP"
  if [ -z "$EST" ]; then
    echo "FATAL: cost estimate produced no number (harness import/error above) — abort before any spend"; exit 5
  fi
  if awk "BEGIN{exit !($EST > $CAP)}"; then
    echo "FATAL: estimate \$$EST exceeds CAP \$$CAP — abort before any spend"; exit 4
  fi

  echo "--- graded run (real LLM) ---"
  python3 analysis/benchmark_1c_v2_qual.py --arms "$ARMS" --ns "$NS" \
      --seeds "$SEEDS" --conditions "$CONDS" --n-inject "$NINJECT" \
      --out "$OUT" --runs-root "$DATA/v2_qual_runs"

  # (d) dump cell records + right-reason TRACE evidence to STDOUT, so the result returns
  #     via `railway logs` without pulling the volume (full traces persist under $DATA).
  echo "=== RESULT EVIDENCE (copy these logs back) ==="
  python3 - "$OUT" "$DATA/v2_qual_runs" <<'PY'
import json, sys, glob
cells_path, runs_root = sys.argv[1], sys.argv[2]
rows=[json.loads(l) for l in open(cells_path,encoding="utf-8") if l.strip()] if __import__("os").path.exists(cells_path) else []
print("CELLS_JSONL:")
for r in rows:
    print("  "+json.dumps(r))
def ev(rd):
    out=[]
    for f in glob.glob(rd+"/*.jsonl"):
        for l in open(f,encoding="utf-8"):
            if l.strip(): out.append(json.loads(l))
    out.sort(key=lambda e:e.get("ts",0)); return out
for r in rows:
    if "error" in r: continue
    rd=r.get("run_dir")
    if not rd: continue
    print(f"\nTRACE_EVIDENCE [{r['arm']} N={r['N']} {r['condition']}] {rd}")
    for e in ev(rd):
        et=e["event_type"]; p=e.get("payload") or {}
        if et=="injection_fired": print("  injection_fired:", json.dumps(p)[:200])
        elif et=="corroboration" and p.get("layer")=="v2_arm_baseline": print("  arm_baseline: capture_counter=",p.get("capture_counter")," n_captured=",len(p.get("captured",[])))
        elif et=="escalation": print("  escalation: _path=",(p.get('evidence') or {}).get('_path')," fault_shape=",p.get("fault_shape")," grade=",(p.get('evidence') or {}).get('grade')," counter=",p.get("counter"))
        elif et=="tripwire_set" and p.get("layer")=="v2_probes":
            mut=r.get("mutated_surface")
            for pr in p.get("probes",[]):
                if pr["target"]==mut: print("  armed_on_mutated:", json.dumps(pr))
        elif et=="success_check": print("  success_check:", json.dumps(p))
PY
  echo "=== qual done; durable records -> $OUT  (pull \$DATA or copy the logs above) ==="
  exit 0
fi
# ---------------- MODE=pilot: net-cost CV pilot (S1 + V2 + V2nc) ----------------
# Phase-1c CV pilot — sizes the confirmatory via the FROZEN blind resize formula. Measurement
# run (treatment code BYTE-IDENTICAL). Primary N=8 x5 seeds first; N=32 x3 spot-check trimmed
# from that end by the --budget guard. After the cells, runs the sign-blind CV/resize compute.
if [ "$MODE" = "pilot" ]; then
  echo "=== MODE=pilot: net-cost CV pilot (S1+V2+V2nc) on benchmark_1c (Railway-Linux) ==="
  export TRIPWIRE_V2=1
  PSEEDS="${PSEEDS:-7101,7102,7103,7104,7105}"; SSEEDS="${SSEEDS:-7201,7202,7203}"
  PN="${PN:-8}"; SN="${SN:-32}"; NINJECT="${NINJECT:-2}"; CAP="${CAP:-50}"
  OUT="$DATA/cv_pilot/cells.jsonl"

  VER="$(claude --version 2>&1 | head -1)"; echo "claude CLI: $VER"
  printf '%s' "$VER" | grep -q "2.1.177" || { echo "FATAL: not 2.1.177 ($VER) — STOP"; exit 2; }
  echo "persistence: $(ls "$DATA"/_persist_*.txt 2>/dev/null | wc -l) marker(s) on $DATA (writable=$([ -w "$DATA" ] && echo yes || echo NO))"

  echo "--- cost estimate BEFORE spend ---"
  EST_OUT="$(python3 analysis/benchmark_1c_cv_pilot.py --estimate --primary-n "$PN" \
      --primary-seeds "$PSEEDS" --spot-n "$SN" --spot-seeds "$SSEEDS" --n-inject "$NINJECT" --budget "$CAP")"
  echo "$EST_OUT"
  EST=$(printf '%s\n' "$EST_OUT" | sed -n 's/.*TOTAL ~\$\([0-9.]*\).*/\1/p' | head -1)
  echo "projected_total=\$$EST  cap=\$$CAP"
  [ -z "$EST" ] && { echo "FATAL: estimate produced no number — abort"; exit 5; }
  if awk "BEGIN{exit !($EST > $CAP)}"; then
    echo "FATAL: estimate \$$EST exceeds CAP \$$CAP — abort (trim SSEEDS/SN and redeploy)"; exit 4
  fi

  echo "--- pilot run (budget-guarded; N=$PN primary preserved, N=$SN trimmed first) ---"
  python3 analysis/benchmark_1c_cv_pilot.py --primary-n "$PN" --primary-seeds "$PSEEDS" \
      --spot-n "$SN" --spot-seeds "$SSEEDS" --n-inject "$NINJECT" --budget "$CAP" \
      --out "$OUT" --runs-root "$DATA/cv_pilot/runs"

  echo "=== CV COMPUTE (sign-blind resize) ==="
  python3 analysis/benchmark_1c_cv_compute.py "$OUT" || echo "(compute failed; cells are durable on $DATA)"
  echo "=== CELLS_JSONL (copy back) ==="; cat "$OUT" 2>/dev/null | sed 's/^/  /'
  echo "=== pilot done; durable -> $OUT ==="
  exit 0
fi
echo "unknown MODE=$MODE"; exit 3
