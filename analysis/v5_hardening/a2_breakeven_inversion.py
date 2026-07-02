"""A2 --- Break-even curve and post-hoc location of the 12% cap (feeds Edit 1c).

Read-only. Uses the REDESIGN (v2) fitted parameters from the frozen fan-out model
inputs (runs/matrix_1b/fanout_model_inputs.json, v2_estimated_from_1b) --- the same
parameters behind Appendix B's 86/40/25 crossover. No refit; no new measurement.

The pre-committed cost-positivity model (phase1b_precommitments SS F.1) is:
    monitoring pays  iff  C + J + p*R < p*(W_batch(n) - W_sent(n)),  W_x(n)=W_x(n0)*n/n0
with J=0 for the redesign. Writing the per-run clean monitoring overhead as M (the
quantity the 12% cap bounds, in dollars), the inversion for the maximum tolerable M is:
    M*(p, n) = p*(W_batch(n) - W_sent(n)) - p*R
and, as a fraction of the S1 clean baseline B, f*(p,n) = M*(p,n)/B.

At the MEASURED fan-out n0=3 the per-replan cost R exceeds the per-run waste gap dW,
so M*(p,3) < 0 for every p: the frozen model does not admit a positive clean-overhead
break-even at the measured scale. We report that honestly, then give the nearest
meaningful statement: a simplified waste-recovery locator that drops the replan term
(monitoring pays iff M < p*dW), which DOES invert and locates the 12% cap on a curve.
Both are reported; neither is forced.
"""
from __future__ import annotations
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent

fm = json.loads((REPO / "runs/matrix_1b/fanout_model_inputs.json").read_text(encoding="utf-8"))
v2 = fm["param_table"]["v2_estimated_from_1b"]
ca = json.loads((REPO / "runs/matrix_1b/cost_autopsy_v3.json").read_text(encoding="utf-8"))

C = v2["C"]                      # 0.171401 per-run check-writing (clean+injected mix)
R = v2["R"]                      # 0.2210485 per replan
dW = v2["dW_injected"]           # 0.068172 measured per-run waste gap (batch - sentinel)
N0 = fm["meta"]["n0"]            # 3 (model n0; v2 block inherits it)
B = ca["partA_1bKG3_clean_overhead"]["s1_clean_median_total"]  # 0.234246 baseline
CAP = 0.12

P_TABLE = [0.05, 0.10, 0.25, 0.50]

def dW_at(n):
    return dW * (n / N0)

# --- Frozen model (includes replan term R), evaluated at the measured fan-out n0=3 ---
def M_frozen(p, n=N0):
    return p * dW_at(n) - p * R          # max tolerable clean overhead in dollars

frozen_at_n0 = {p: M_frozen(p) for p in P_TABLE}
frozen_admits = any(v > 0 for v in frozen_at_n0.values())
# fan-out at which frozen model turns cost-positive for a *free* monitor (M=0): dW(n) > R
n_free_positive = None
for n in range(1, 512):
    if dW_at(n) > R:
        n_free_positive = n
        break

# --- Simplified waste-recovery locator (drops R): monitoring pays iff M < p*dW ---
def f_recovery(p):
    return p * dW / B                    # max clean overhead as fraction of baseline
recovery = {p: f_recovery(p) for p in P_TABLE}
# p* at which a 12% cap is exactly break-even:  CAP = p* * dW / B
p_star = CAP * B / dW

out = {
    "meta": {"read_only": True, "model": "phase1b_precommitments SSF.1 (redesign, J=0)",
             "params_source": "runs/matrix_1b/fanout_model_inputs.json v2_estimated_from_1b",
             "baseline_B_source": "cost_autopsy_v3.json partA s1_clean_median_total"},
    "params": {"C": C, "R": R, "dW_injected": dW, "n0": N0, "B_baseline": B, "cap": CAP},
    "frozen_model_at_n0": {
        "note": "At measured fan-out n0=3, R (%.4f) > dW (%.4f); max tolerable clean overhead M*(p,3) is NEGATIVE for all p." % (R, dW),
        "M_star_usd_by_p": frozen_at_n0,
        "admits_positive_breakeven_at_n0": frozen_admits,
        "free_monitor_turns_positive_at_fanout_n": n_free_positive,
        "appendix_b_crossover": v2["crossover_v2_injected"],
    },
    "recovery_locator": {
        "note": "Drops the replan term; monitoring pays iff clean overhead M < p*dW. Post-hoc, generous to the monitor.",
        "max_clean_overhead_fraction_by_p": recovery,
        "p_star_for_12pct_cap": p_star,
    },
}
(HERE / "a2_breakeven_inversion.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")

# paste-ready
paste = (
    "Locating the 12\\% cap on the fitted break-even curve (post-hoc): at the measured "
    f"fan-out the redesign's per-replan cost (\\${R:.2f}) exceeds its per-run waste gap "
    f"(\\${dW:.2f}), so the pre-committed model is cost-negative at every clean overhead---"
    "even a free monitor does not pay until fan-out grows past "
    f"{n_free_positive} workers. Setting the replan term aside and asking only whether "
    "the clean overhead is recovered by expected saved waste, a 12\\% cap breaks even at a "
    f"fault rate of {p_star*100:.0f}\\%; at plausible fault rates (5--25\\%) the tolerable "
    f"overhead is {recovery[0.05]*100:.1f}--{recovery[0.25]*100:.1f}\\%, so 12\\% was, if "
    "anything, generous to the monitor."
)

def pct(x): return f"{x*100:.1f}%"
md = f"""# A2 --- Break-even curve and post-hoc location of the 12% cap (feeds Edit 1c)

**Read-only.** Redesign (v2) fitted parameters, no refit: C=\\${C:.4f} (per-run
check-writing), R=\\${R:.4f} (per replan), measured per-run waste gap
dW=\\${dW:.4f} (W_batch-W_sent, injected, n0=3), baseline B=\\${B:.4f}
(S1 clean median). Source: `fanout_model_inputs.json` v2_estimated_from_1b (the same
parameters behind Appendix B's 86/40/25 crossover).

## Does the frozen model admit a clean inversion? **No, at the measured fan-out.**
The pre-committed condition is `C + J + p*R < p*(W_batch(n) - W_sent(n))`, J=0.
Solving for the maximum tolerable clean overhead M at fan-out n:
`M*(p,n) = p*(dW*(n/3)) - p*R`. At the measured n0=3, R (\\${R:.4f}) already exceeds
dW (\\${dW:.4f}), so **M*(p,3) is negative for every fault rate** --- monitoring is
cost-negative at n=3 even for a *free* monitor, because the replan a detection triggers
costs more than the waste it saves. A free monitor first turns cost-positive only at
fan-out **n = {n_free_positive}** workers; the paper's Appendix B crossover for the
*measured* clean overhead is {v2['crossover_v2_injected']} workers at p = 0.10 / 0.25 / 0.50.
This is the "does not admit a clean inversion" case A2 anticipated: we do not force it.

| p (fault rate) | M*(p,3) frozen, incl. replan | verdict at n0=3 |
|---|---|---|
| 0.05 | \\${frozen_at_n0[0.05]:+.4f} | no break-even |
| 0.10 | \\${frozen_at_n0[0.10]:+.4f} | no break-even |
| 0.25 | \\${frozen_at_n0[0.25]:+.4f} | no break-even |
| 0.50 | \\${frozen_at_n0[0.50]:+.4f} | no break-even |

## Nearest meaningful statement: a waste-recovery locator (post-hoc, drops R)
Dropping the replan term (i.e. asking only whether the clean monitoring overhead is
recovered by the expected saved waste, `M < p*dW`) *does* invert and puts 12% on a curve.
This is **generous to the monitor** --- including replan only makes 12% look worse.

| p (fault rate) | max tolerable clean overhead f*(p)=p*dW/B |
|---|---|
| 0.05 | {pct(recovery[0.05])} |
| 0.10 | {pct(recovery[0.10])} |
| 0.25 | {pct(recovery[0.25])} |
| 0.50 | {pct(recovery[0.50])} |

**Fault rate at which a 12% cap is exactly break-even: p\\* = {p_star*100:.1f}%.**
So 12% corresponds to a ~{p_star*100:.0f}% fault rate under the generous model; at
plausible fault rates it sits well above the tolerable overhead. Either way the measured
55.5% overhead is far outside break-even.

## PASTE-READY SENTENCE (Edit 1c, label post-hoc; put the tables in a footnote/Appendix B extension)
> {paste}
"""
(HERE / "A2_breakeven_inversion.md").write_text(md, encoding="utf-8")
print("A2 done")
print(f"  C={C} R={R} dW={dW} B={B}")
print(f"  frozen model at n0=3: M*(p) = {frozen_at_n0}  admits_positive={frozen_admits}")
print(f"  free monitor turns positive at fanout n={n_free_positive}")
print(f"  recovery locator f*(p): {recovery}")
print(f"  p* for 12% cap = {p_star*100:.2f}%")
print("  PASTE:", paste)
