# A4 --- Statistical attachments (feeds Edit 8)

**Read-only.** Wilson 95% two-sided lower bounds (z=1.96, matching the frozen gate
report) and Fisher exact one-sided p-values (exact hypergeometric, no approximation).

## Wilson 95% lower bounds --- PASTE-READY strings
- Gated recall **10/15 = 66.7%** (Wilson 95% LB **41.7%**)
- Detection inventory **24/31 = 77.4%** (Wilson 95% LB **60.2%**)
- S2 passive **12/31 = 38.7%** (Wilson 95% LB **23.7%**)
- RESOURCE_BUDGET transfer **3/5 = 60.0%** (Wilson 95% LB **23.1%**)

### Per-category confirmatory cells (all detected; small-n)
| category | cell | Wilson 95% LB | matches frozen gate |
|---|---|---|---|
| API_SURFACE | 6/6 | 61.0% | True |
| SCHEMA_DRIFT | 3/3 | 43.9% | True |
| PERMISSION_AUTH | 6/6 | 61.0% | True |
| TOOL_CONTRACT | 3/3 | 43.9% | True |
| RETRIEVAL_INTEGRITY | 3/3 | 43.9% | True |

Every seen category is 6/6-style perfect but the
n=3 cells carry a Wilson 95% LB of only ~43.9%. The caveat must
travel with "perfect on the five seen fault types" wherever it appears outside the gate table.

## Fisher exact one-sided p-values --- PASTE-READY strings
- **RESOURCE_BUDGET transfer, 3/5 vs 0/5** (redesign vs pooled passive): one-sided Fisher
  exact **p = 0.083** --- **not significant at .05; state the transfer as directional with n=5**.
  *(Sensitivity: if the passive baseline is pooled over two arms, 3/5 vs 0/10, p = 0.022.)*
- **Redesign vs S2, 24/31 vs 12/31**: one-sided Fisher exact **p = 0.0021**
  (significant at .05).

## Guidance for Edit 8
The transfer p (0.083) is **above 0.05**. Per the brief, the paper states the
transfer as **directional with n=5**, not as an established transfer; adjust any
"real transfer" phrasing accordingly. The 24/31 vs 12/31 separation is significant
(p = 0.0021) and can carry a definite claim.
