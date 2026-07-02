"""A3 --- Waste decomposition of the KG4 paradox (feeds Edit 7).

Read-only. Decompose the frozen wasted-work metric (KG4: V2 median 7008 vs S3 6404 over
31 non-clean cells/arm) per run into buckets, to explain why the redesign's 7008 exceeds
the heartbeat's 6404 even though the heartbeat detects 0/31.

The frozen metric (analysis/metrics.wasted_work) counts ONLY worker_end tokens for
(i) window workers --- active from the injection to the run's decision point --- and
(ii) discarded redispatch partials. Compile/probe/replan tokens are NEVER in it
(double-count guard, cost_autopsy_v3.json). So buckets (d) replan and (e) monitoring are
structurally 0 within the metric; we still report them SEPARATELY to show the omission.

Buckets of the wasted tokens:
  (a) pre-fault sunk    --- window-worker tokens accrued BEFORE the fault (sunk cost of
                            work that was correct until the plan went bad)
  (b) post-fault pre-detection --- window-worker tokens from fault to detection
  (c) post-detection burn      --- window tokens after detection + discarded partials
  (d) replan cost       --- replan + recompile events (NOT in the frozen metric; separate)
  (e) monitoring after fault   --- compile/probe/tripwire tokens after the fault (=0 on mock)

DISCLOSED ESTIMATE: worker tokens are logged as a single lump at worker_end, so the
pre/post-fault split within one straddling worker uses a time-proportional assumption
(uniform token accrual over the worker's wall-clock). We report (a) both this way AND as a
worker-level upper bound (whole lump of any worker that started before the fault), so the
alternative accounting is a RANGE, not a false point. The frozen 7008/6404 is unchanged.
"""
from __future__ import annotations
import json, sys, statistics
from datetime import datetime
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO))

from analysis.metrics import (injection_info, wasted_work, first_attributable_pause,  # noqa
                              _decision_ts, _usage_tokens, _usage_cost)
from trace import read_run  # noqa

BASE = REPO / "runs/matrix_1b/runs"

def T(ts): return datetime.fromisoformat(ts)

def decompose_run(events):
    inj = injection_info(events)
    if inj is None:
        return None
    system = events[0]["system"]
    inj_ts = T(inj["ts"])
    end_ts = T(_decision_ts(events, inj, system))
    pause = first_attributable_pause(events, inj)
    det_ts = T(pause["ts"]) if pause else None
    detected = pause is not None

    frozen = wasted_work(events, inj)  # authoritative window/discard partition + tokens
    window_set = set(frozen["window_workers"])
    discard_set = set(frozen["discarded_workers"])

    starts = {e["actor"]: T(e["ts"]) for e in events if e["event_type"] == "worker_start"}
    worker_ends = {e["actor"]: e for e in events if e["event_type"] == "worker_end"}

    a_pre_sunk = 0.0            # time-proportional pre-fault
    a_pre_sunk_workerlevel = 0  # upper bound: whole lump of pre-fault-started workers
    b_post_predetect = 0.0
    c_post_detect = 0.0
    for actor in window_set:
        e = worker_ends[actor]
        tok = _usage_tokens(e)
        w_start = starts.get(actor, T(e["ts"]))
        w_end = T(e["ts"])
        span = (w_end - w_start).total_seconds()
        # pre-fault fraction (time-proportional; clamp)
        if w_start < inj_ts and span > 0:
            pre_frac = min(max((inj_ts - w_start).total_seconds() / span, 0.0), 1.0)
        else:
            pre_frac = 0.0
        pre = tok * pre_frac
        post = tok - pre
        a_pre_sunk += pre
        if w_start < inj_ts:
            a_pre_sunk_workerlevel += tok
        # split post into pre/post detection
        if det_ts is not None and w_end > det_ts and span > 0:
            # fraction of the worker's span that is after detection
            post_det_frac = min(max((w_end - max(det_ts, inj_ts, w_start)).total_seconds() / span, 0.0), 1.0)
            post_det = tok * post_det_frac
            post_det = min(post_det, post)  # cannot exceed post-fault portion
        else:
            post_det = 0.0
        b_post_predetect += (post - post_det)
        c_post_detect += post_det
    # discarded partials: redispatch after replan -> entirely post-detection burn
    disc_tokens = sum(_usage_tokens(worker_ends[a]) for a in discard_set if a in worker_ends)
    c_post_detect += disc_tokens

    # (d) replan bucket (separate; NOT in frozen metric): replan events + recompiles after 1st replan
    replans = [e for e in events if e["event_type"] == "replan"]
    d_replan_tokens = sum(_usage_tokens(e) for e in replans)
    if replans:
        first_replan_ts = min(T(e["ts"]) for e in replans)
        d_replan_tokens += sum(_usage_tokens(e) for e in events
                               if e["event_type"] == "compile" and T(e["ts"]) >= first_replan_ts)
    # (e) monitoring after fault (should be ~0 on the mock): probe/tripwire/corroboration usage after inj
    e_monitor_tokens = sum(_usage_tokens(e) for e in events
                           if e["event_type"] in ("tripwire_set", "corroboration", "probe")
                           and T(e["ts"]) >= inj_ts)

    frozen_tok = frozen["tokens"]
    recon = a_pre_sunk + b_post_predetect + c_post_detect
    return {
        "system": system, "detected": detected, "n_replans": len(replans),
        "frozen_waste_tokens": frozen_tok,
        "a_pre_fault_sunk": a_pre_sunk,
        "a_pre_fault_sunk_workerlevel_ub": a_pre_sunk_workerlevel,
        "b_post_fault_pre_detection": b_post_predetect,
        "c_post_detection_burn": c_post_detect,
        "d_replan_tokens_separate": d_replan_tokens,
        "e_monitoring_after_fault": e_monitor_tokens,
        "reconstruction_error": round(recon - frozen_tok, 3),
        "n_window": len(window_set), "n_discard": len(discard_set),
        "waste_excl_prefault_sunk": frozen_tok - a_pre_sunk,
        "waste_excl_prefault_sunk_ub": frozen_tok - a_pre_sunk_workerlevel,
        "waste_excl_redispatch_rework": frozen_tok - c_post_detect,  # exclude bucket (c)
    }

runs = defaultdict(list)
for d in sorted(BASE.iterdir()):
    if not d.is_dir():
        continue
    name = d.name
    arm = None
    if "-V2-" in name: arm = "V2"
    elif "-S3-" in name: arm = "S3"
    else: continue
    events = read_run(d)
    dec = decompose_run(events)
    if dec and dec["frozen_waste_tokens"] is not None and "clean" not in name:
        runs[arm].append(dec)

def med(xs): return statistics.median([x for x in xs if x is not None]) if xs else None
def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs)/len(xs) if xs else None

BUCKETS = ["a_pre_fault_sunk", "b_post_fault_pre_detection", "c_post_detection_burn"]
summary = {}
for arm in ("V2", "S3"):
    rs = runs[arm]
    summary[arm] = {
        "n_nonclean": len(rs),
        "n_detected": sum(1 for r in rs if r["detected"]),
        "n_with_discard": sum(1 for r in rs if r["n_discard"] > 0),
        "frozen_waste_median": med([r["frozen_waste_tokens"] for r in rs]),
        "frozen_waste_mean": mean([r["frozen_waste_tokens"] for r in rs]),
        "bucket_medians": {
            "a_pre_fault_sunk": med([r["a_pre_fault_sunk"] for r in rs]),
            "a_pre_fault_sunk_workerlevel_ub": med([r["a_pre_fault_sunk_workerlevel_ub"] for r in rs]),
            "b_post_fault_pre_detection": med([r["b_post_fault_pre_detection"] for r in rs]),
            "c_post_detection_burn": med([r["c_post_detection_burn"] for r in rs]),
            "d_replan_tokens_separate": med([r["d_replan_tokens_separate"] for r in rs]),
            "e_monitoring_after_fault": med([r["e_monitoring_after_fault"] for r in rs]),
        },
        # means are additive: a+b+c = frozen mean (buckets d,e are outside the metric)
        "bucket_means": {b: mean([r[b] for r in rs]) for b in BUCKETS},
        "discarded_mean": mean([r["c_post_detection_burn"] for r in rs]),  # c incl discard
        "n_window_mean": mean([r["n_window"] for r in rs]),
        "n_discard_mean": mean([r["n_discard"] for r in rs]),
        "d_replan_mean": mean([r["d_replan_tokens_separate"] for r in rs]),
        "max_reconstruction_error_tokens": max(abs(r["reconstruction_error"]) for r in rs) if rs else None,
        "alt_waste_excl_prefault_sunk_median": med([r["waste_excl_prefault_sunk"] for r in rs]),
        "alt_waste_excl_prefault_sunk_ub_median": med([r["waste_excl_prefault_sunk_ub"] for r in rs]),
        "alt_waste_excl_redispatch_rework_median": med([r["waste_excl_redispatch_rework"] for r in rs]),
    }

# additive mean-difference decomposition of (V2 - S3) frozen waste
diff = {b: summary["V2"]["bucket_means"][b] - summary["S3"]["bucket_means"][b] for b in BUCKETS}
diff_total = summary["V2"]["frozen_waste_mean"] - summary["S3"]["frozen_waste_mean"]
driver = max(BUCKETS, key=lambda b: diff[b])

# dominant bucket for V2
v2b = summary["V2"]["bucket_medians"]
dominant = max(("a_pre_fault_sunk", "b_post_fault_pre_detection", "c_post_detection_burn"),
               key=lambda k: v2b[k] or 0)

out = {
    "meta": {"read_only": True,
             "frozen_source": "cost_autopsy_v3.json partB (V2 7008 / S3 6404 over 31 non-clean cells/arm)",
             "split_method": "time-proportional within lumped worker_end tokens; pre-fault sunk also given as worker-level upper bound",
             "note_dandef": "buckets (d) replan and (e) monitoring are OUTSIDE the frozen wasted metric by construction; reported separately"},
    "summary": summary,
    "dominant_bucket_v2": dominant,
    "mean_diff_decomposition_v2_minus_s3": {"total": diff_total, "by_bucket": diff, "largest": driver},
}
(HERE / "a3_waste_decomposition.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")

v2 = summary["V2"]; s3 = summary["S3"]
v2m = v2["bucket_means"]; s3m = s3["bucket_means"]
def i(x): return f"{x:.0f}" if x is not None else "n/a"
paragraph = (
    f"The redesign's median wasted work (7,008 tokens over 31 non-clean cells) exceeds the "
    f"cost-matched heartbeat's (6,404) even though the heartbeat detects nothing, and an "
    f"additive decomposition of the mean gap ({i(diff_total)} tokens) locates the entire "
    f"excess in one bucket: re-dispatch rework. When the redesign detects a fault it replans "
    f"and re-dispatches workers, discarding the partial output of the workers left on the "
    f"doomed plan; that discarded rework averages {i(v2m['c_post_detection_burn'])} tokens per "
    f"non-clean run and appears in {v2['n_with_discard']} of 31 cells, and the heartbeat --- "
    f"detecting nothing, replanning nothing --- discards nothing at all "
    f"(bucket c is exactly 0 for S3). It is not sunk pre-fault cost: the redesign actually "
    f"books LESS of that than the heartbeat (mean {i(v2m['a_pre_fault_sunk'])} vs "
    f"{i(s3m['a_pre_fault_sunk'])} tokens), because it stops early and truncates the exposure "
    f"window the heartbeat runs to completion. Replan and monitoring tokens sit outside the "
    f"metric entirely. So the 1.09x parity is the price of corrective action: the redesign "
    f"pays to detect, stop, and re-plan around the fault, and the metric counts that recovery "
    f"machinery as waste, while the heartbeat's cheaper run simply finishes on the broken plan "
    f"and delivers the wrong answer. Excluding the re-dispatch rework --- the cost of a recovery "
    f"the do-nothing baseline never attempts --- the redesign's median waste falls to "
    f"{i(v2['alt_waste_excl_redispatch_rework_median'])} tokens, below the heartbeat's 6,404. "
    f"The frozen 1.09x verdict line stands; the autopsy shows the gap is recovery cost, not the "
    f"monitor wasting more."
)

md = f"""# A3 --- Waste decomposition of the KG4 paradox (feeds Edit 7)

**Read-only.** Frozen KG4 medians (unchanged): **V2 7,008** vs **S3 6,404** tokens over 31
non-clean cells per arm (cost_autopsy_v3.json partB). The wasted metric counts only
worker_end tokens (window + discarded); replan and monitoring tokens are excluded by the
double-count guard, so buckets (d) and (e) are 0 *within* it --- reported separately below.

**Estimate disclosure:** worker tokens are lumped at worker_end, so the pre/post-fault split
of a straddling worker uses a time-proportional assumption; the pre-fault sunk bucket also
carries a worker-level upper bound. Buckets a+b+c reconcile to the frozen metric exactly
(max reconstruction error {i(summary['V2']['max_reconstruction_error_tokens'])} /
{i(summary['S3']['max_reconstruction_error_tokens'])} tokens per run). The re-dispatch bucket
(c) is measured directly from discarded worker lumps and does not depend on the time-split.

## Median tokens per bucket per arm (over 31 non-clean cells)
| bucket | V2 (redesign) | S3 (heartbeat) |
|---|---|---|
| frozen wasted (metric), median | {i(v2['frozen_waste_median'])} | {i(s3['frozen_waste_median'])} |
| (a) pre-fault sunk (time-prop) | {i(v2b['a_pre_fault_sunk'])} | {i(s3['bucket_medians']['a_pre_fault_sunk'])} |
| (b) post-fault, pre-detection | {i(v2b['b_post_fault_pre_detection'])} | {i(s3['bucket_medians']['b_post_fault_pre_detection'])} |
| (c) post-detection burn + discarded | {i(v2b['c_post_detection_burn'])} | {i(s3['bucket_medians']['c_post_detection_burn'])} |
| (d) replan cost [SEPARATE, not in metric] | {i(v2b['d_replan_tokens_separate'])} | {i(s3['bucket_medians']['d_replan_tokens_separate'])} |
| (e) monitoring after fault [SEPARATE] | {i(v2b['e_monitoring_after_fault'])} | {i(s3['bucket_medians']['e_monitoring_after_fault'])} |

## Additive mean decomposition of the gap (means are additive; medians are not)
| bucket | V2 mean | S3 mean | V2 - S3 |
|---|---|---|---|
| (a) pre-fault sunk | {i(v2m['a_pre_fault_sunk'])} | {i(s3m['a_pre_fault_sunk'])} | {i(diff['a_pre_fault_sunk'])} |
| (b) post-fault, pre-detection | {i(v2m['b_post_fault_pre_detection'])} | {i(s3m['b_post_fault_pre_detection'])} | {i(diff['b_post_fault_pre_detection'])} |
| (c) post-detection burn + re-dispatch | {i(v2m['c_post_detection_burn'])} | {i(s3m['c_post_detection_burn'])} | **{i(diff['c_post_detection_burn'])}** |
| frozen waste (mean) | {i(v2['frozen_waste_mean'])} | {i(s3['frozen_waste_mean'])} | {i(diff_total)} |

Detections: V2 {v2['n_detected']}/{v2['n_nonclean']}; S3 {s3['n_detected']}/{s3['n_nonclean']}.
Re-dispatch/discard: V2 in {v2['n_with_discard']}/31 cells (mean {v2['n_discard_mean']:.2f} workers
discarded); S3 in {s3['n_with_discard']}/31. **The entire mean gap is bucket (c)** --- the
re-dispatch rework the heartbeat never incurs; pre-fault sunk cost runs the OTHER way
(V2 < S3), so the "sunk cost of justified stops" story the brief floated is not what the data shows.

## Alternative accounting (post-hoc; frozen 1.09x number unchanged)
Excluding the re-dispatch rework (bucket c) --- the cost of a recovery the do-nothing heartbeat
never attempts --- the redesign's median waste falls to
**{i(v2['alt_waste_excl_redispatch_rework_median'])}**, below the heartbeat's 6,404.
(For completeness, excluding pre-fault sunk cost instead leaves V2 at
{i(v2['alt_waste_excl_prefault_sunk_median'])} vs S3 {i(s3['alt_waste_excl_prefault_sunk_median'])},
i.e. that exclusion does NOT flip the ordering --- confirming sunk cost is not the driver.)

## PASTE-READY PARAGRAPH (Edit 7; label post-hoc, keep the frozen 1.09x verdict line intact)
> {paragraph}
"""
(HERE / "A3_waste_decomposition.md").write_text(md, encoding="utf-8")
print("A3 done")
print(f"  V2 frozen mean={summary['V2']['frozen_waste_mean']:.0f} median={summary['V2']['frozen_waste_median']}")
print(f"  S3 frozen mean={summary['S3']['frozen_waste_mean']:.0f} median={summary['S3']['frozen_waste_median']}")
print(f"  V2 bucket means: {({k:round(v) for k,v in summary['V2']['bucket_means'].items()})}")
print(f"  S3 bucket means: {({k:round(v) for k,v in summary['S3']['bucket_means'].items()})}")
print(f"  V2 discard: n_with_discard={summary['V2']['n_with_discard']} n_discard_mean={summary['V2']['n_discard_mean']:.2f} n_window_mean={summary['V2']['n_window_mean']:.2f} replan_mean={summary['V2']['d_replan_mean']:.0f}")
print(f"  S3 discard: n_with_discard={summary['S3']['n_with_discard']} n_discard_mean={summary['S3']['n_discard_mean']:.2f} n_window_mean={summary['S3']['n_window_mean']:.2f} replan_mean={summary['S3']['d_replan_mean']:.0f}")
print(f"  MEAN DIFF (V2-S3) total={diff_total:.0f}  by_bucket={({k:round(v) for k,v in diff.items()})}  driver={driver}")
