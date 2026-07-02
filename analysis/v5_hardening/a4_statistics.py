"""A4 --- Statistical attachments (feeds Edit 8).

Read-only. Wilson 95% two-sided lower bounds (z=1.96, matching the frozen gate report's
`wilson95_lower`) and Fisher exact one-sided p-values. No external deps: Wilson is
closed-form; Fisher uses exact hypergeometric tails via math.comb.

Counts are the frozen confirmatory-verdict cells (gate_report_final.json):
  overall gated recall 10/15; detection inventory 24/31; S2 12/31;
  per-category (API_SURFACE 6/6, SCHEMA_DRIFT 3/3, PERMISSION_AUTH 6/6,
  TOOL_CONTRACT 3/3, RETRIEVAL_INTEGRITY 3/3);
  held-out RESOURCE_BUDGET transfer 3/5 vs pooled passive 0/5.
"""
from __future__ import annotations
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
Z = 1.959963984540054  # exact 0.975 standard-normal quantile (matches frozen gate report)

def wilson_lower(k, n, z=Z):
    if n == 0:
        return None
    p = k / n
    denom = 1 + z*z/n
    centre = p + z*z/(2*n)
    half = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n))
    return (centre - half) / denom

def fisher_one_sided_greater(a, b, c, d):
    """One-sided Fisher exact p that row-1 has a HIGHER success rate than row-2.
    2x2 table [[a,b],[c,d]]; p = sum of hypergeometric prob of tables at least as
    extreme (>= a successes in row 1) holding all margins fixed."""
    r1, r2 = a + b, c + d
    c1 = a + c            # total successes (column 1)
    N = a + b + c + d
    def hyp(x):           # P(row-1 successes == x) | margins
        return (math.comb(c1, x) * math.comb(N - c1, r1 - x)) / math.comb(N, r1)
    lo = max(0, r1 - (N - c1))
    hi = min(r1, c1)
    return sum(hyp(x) for x in range(a, hi + 1)), (lo, hi)

# ---- pull the frozen per-category cells to confirm counts ----
gr = json.loads((REPO / "runs/matrix_1b/gate_report_final.json").read_text(encoding="utf-8"))
kg1 = next(g for g in gr["gates"] if g["gate"] == "1bKG1")
percat_frozen = {c: (v["k"], v["n"], v.get("wilson95_lower"))
                 for c, v in kg1["categorical"]["per_category"].items()}

# ---- Wilson lower bounds ----
wilson = {
    "gated_recall_10_15": {"k": 10, "n": 15, "lower": wilson_lower(10, 15)},
    "detection_inventory_24_31": {"k": 24, "n": 31, "lower": wilson_lower(24, 31)},
    "s2_12_31": {"k": 12, "n": 31, "lower": wilson_lower(12, 31)},
    "rb_transfer_3_5": {"k": 3, "n": 5, "lower": wilson_lower(3, 5)},
}
percat = {}
for cat, (k, n, frozen_lo) in percat_frozen.items():
    lo = wilson_lower(k, n)
    percat[cat] = {"k": k, "n": n, "lower": lo, "frozen_lower": frozen_lo,
                   "matches_frozen": (frozen_lo is None) or abs(lo - frozen_lo) < 1e-9}

# ---- Fisher exact ----
# transfer: RESOURCE_BUDGET 3/5 detected vs pooled passive baseline 0/5 detected
p_transfer, rng_t = fisher_one_sided_greater(3, 2, 0, 5)
p_transfer_pooled10, _ = fisher_one_sided_greater(3, 2, 0, 10)  # sensitivity: pooled 0/10
# redesign 24/31 vs S2 12/31
p_redesign_vs_s2, rng_r = fisher_one_sided_greater(24, 7, 12, 19)

out = {
    "meta": {"read_only": True, "z": Z,
             "sources": "gate_report_final.json (counts); Wilson closed-form; Fisher exact hypergeometric"},
    "wilson_lower_bounds": wilson,
    "per_category_wilson": percat,
    "fisher": {
        "rb_transfer_3of5_vs_0of5": {"p_one_sided": p_transfer, "significant_05": p_transfer < 0.05,
                                     "note": "one-sided; transfer better than pooled passive"},
        "rb_transfer_3of5_vs_pooled_0of10": {"p_one_sided": p_transfer_pooled10,
                                             "significant_05": p_transfer_pooled10 < 0.05,
                                             "note": "sensitivity if passive pooled over two arms (0/10)"},
        "redesign_24of31_vs_s2_12of31": {"p_one_sided": p_redesign_vs_s2,
                                         "significant_05": p_redesign_vs_s2 < 0.05},
    },
}
(HERE / "a4_statistics.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")

def pc(x): return f"{x*100:.1f}%"
transfer_phrasing = ("significant" if p_transfer < 0.05
                     else "not significant at .05; state the transfer as directional with n=5")

md = f"""# A4 --- Statistical attachments (feeds Edit 8)

**Read-only.** Wilson 95% two-sided lower bounds (z=1.96, matching the frozen gate
report) and Fisher exact one-sided p-values (exact hypergeometric, no approximation).

## Wilson 95% lower bounds --- PASTE-READY strings
- Gated recall **10/15 = 66.7%** (Wilson 95% LB **{pc(wilson['gated_recall_10_15']['lower'])}**)
- Detection inventory **24/31 = 77.4%** (Wilson 95% LB **{pc(wilson['detection_inventory_24_31']['lower'])}**)
- S2 passive **12/31 = 38.7%** (Wilson 95% LB **{pc(wilson['s2_12_31']['lower'])}**)
- RESOURCE_BUDGET transfer **3/5 = 60.0%** (Wilson 95% LB **{pc(wilson['rb_transfer_3_5']['lower'])}**)

### Per-category confirmatory cells (all detected; small-n)
| category | cell | Wilson 95% LB | matches frozen gate |
|---|---|---|---|
""" + "\n".join(
    f"| {cat} | {v['k']}/{v['n']} | {pc(v['lower'])} | {v['matches_frozen']} |"
    for cat, v in percat.items()
) + f"""

Every seen category is {list(percat.values())[0]['k']}/{list(percat.values())[0]['n']}-style perfect but the
n=3 cells carry a Wilson 95% LB of only ~{pc(min(v['lower'] for v in percat.values()))}. The caveat must
travel with "perfect on the five seen fault types" wherever it appears outside the gate table.

## Fisher exact one-sided p-values --- PASTE-READY strings
- **RESOURCE_BUDGET transfer, 3/5 vs 0/5** (redesign vs pooled passive): one-sided Fisher
  exact **p = {p_transfer:.3f}** --- **{transfer_phrasing}**.
  *(Sensitivity: if the passive baseline is pooled over two arms, 3/5 vs 0/10, p = {p_transfer_pooled10:.3f}.)*
- **Redesign vs S2, 24/31 vs 12/31**: one-sided Fisher exact **p = {p_redesign_vs_s2:.4f}**
  ({'significant at .05' if p_redesign_vs_s2 < 0.05 else 'not significant at .05'}).

## Guidance for Edit 8
The transfer p ({p_transfer:.3f}) is **above 0.05**. Per the brief, the paper states the
transfer as **directional with n=5**, not as an established transfer; adjust any
"real transfer" phrasing accordingly. The 24/31 vs 12/31 separation is significant
(p = {p_redesign_vs_s2:.4f}) and can carry a definite claim.
"""
(HERE / "A4_statistics.md").write_text(md, encoding="utf-8")
print("A4 done")
for k, v in wilson.items():
    print(f"  {k}: {v['k']}/{v['n']} Wilson LB = {v['lower']*100:.2f}%")
for cat, v in percat.items():
    print(f"  {cat}: {v['k']}/{v['n']} LB={v['lower']*100:.2f}% frozen={v['frozen_lower']} match={v['matches_frozen']}")
print(f"  Fisher transfer 3/5 vs 0/5: p={p_transfer:.4f}  (pooled 0/10: p={p_transfer_pooled10:.4f})")
print(f"  Fisher 24/31 vs 12/31: p={p_redesign_vs_s2:.6f}")
