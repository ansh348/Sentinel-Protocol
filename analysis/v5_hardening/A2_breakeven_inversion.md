# A2 --- Break-even curve and post-hoc location of the 12% cap (feeds Edit 1c)

**Read-only.** Redesign (v2) fitted parameters, no refit: C=\$0.1714 (per-run
check-writing), R=\$0.2210 (per replan), measured per-run waste gap
dW=\$0.0682 (W_batch-W_sent, injected, n0=3), baseline B=\$0.2342
(S1 clean median). Source: `fanout_model_inputs.json` v2_estimated_from_1b (the same
parameters behind Appendix B's 86/40/25 crossover).

## Does the frozen model admit a clean inversion? **No, at the measured fan-out.**
The pre-committed condition is `C + J + p*R < p*(W_batch(n) - W_sent(n))`, J=0.
Solving for the maximum tolerable clean overhead M at fan-out n:
`M*(p,n) = p*(dW*(n/3)) - p*R`. At the measured n0=3, R (\$0.2210) already exceeds
dW (\$0.0682), so **M*(p,3) is negative for every fault rate** --- monitoring is
cost-negative at n=3 even for a *free* monitor, because the replan a detection triggers
costs more than the waste it saves. A free monitor first turns cost-positive only at
fan-out **n = 10** workers; the paper's Appendix B crossover for the
*measured* clean overhead is {'0.1': 86, '0.25': 40, '0.5': 25} workers at p = 0.10 / 0.25 / 0.50.
This is the "does not admit a clean inversion" case A2 anticipated: we do not force it.

| p (fault rate) | M*(p,3) frozen, incl. replan | verdict at n0=3 |
|---|---|---|
| 0.05 | \$-0.0076 | no break-even |
| 0.10 | \$-0.0153 | no break-even |
| 0.25 | \$-0.0382 | no break-even |
| 0.50 | \$-0.0764 | no break-even |

## Nearest meaningful statement: a waste-recovery locator (post-hoc, drops R)
Dropping the replan term (i.e. asking only whether the clean monitoring overhead is
recovered by the expected saved waste, `M < p*dW`) *does* invert and puts 12% on a curve.
This is **generous to the monitor** --- including replan only makes 12% look worse.

| p (fault rate) | max tolerable clean overhead f*(p)=p*dW/B |
|---|---|
| 0.05 | 1.5% |
| 0.10 | 2.9% |
| 0.25 | 7.3% |
| 0.50 | 14.6% |

**Fault rate at which a 12% cap is exactly break-even: p\* = 41.2%.**
So 12% corresponds to a ~41% fault rate under the generous model; at
plausible fault rates it sits well above the tolerable overhead. Either way the measured
55.5% overhead is far outside break-even.

## PASTE-READY SENTENCE (Edit 1c, label post-hoc; put the tables in a footnote/Appendix B extension)
> Locating the 12\% cap on the fitted break-even curve (post-hoc): at the measured fan-out the redesign's per-replan cost (\$0.22) exceeds its per-run waste gap (\$0.07), so the pre-committed model is cost-negative at every clean overhead---even a free monitor does not pay until fan-out grows past 10 workers. Setting the replan term aside and asking only whether the clean overhead is recovered by expected saved waste, a 12\% cap breaks even at a fault rate of 41\%; at plausible fault rates (5--25\%) the tolerable overhead is 1.5--7.3\%, so 12\% was, if anything, generous to the monitor.
