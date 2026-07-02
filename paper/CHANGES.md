# CHANGES.md --- fse_focused_v4.tex -> fse_focused_v5.tex

v5 is the FSE 2027 hardening pass. `fse_focused_v4.tex` is preserved byte-for-byte;
v5 is a copy with the edits below. **No measured number, verdict line, pre-registered
threshold, or frozen fact was changed.** Verified programmatically: both verbatim
`lstlisting` verdict blocks (pilot KG1--KG4 and confirmatory 1bKG1--1bKG4) and both §9
tables (`tab:v3-overhead`, `tab:v3-detection`) are byte-identical between v4 and v5. Every
post-hoc analysis inserted (A1--A6) is labeled post-hoc in the text. Numbers inserted come
from `analysis/v5_hardening/` (Prompt A), which reads only banked data.

Per author instruction during the pass, the **anonymity sweep** (constraint 5) and the
**page-limit / FSE 2027 CFP format check** were deferred and NOT performed; see AUTHOR_TODO.

Paper compiles clean (pdflatex, 17 pages, no undefined refs/citations, no errors).

---

## Edit 1 --- The 12% cap: disclose the judgment, prove invariance, locate post-hoc
- **§7, new paragraph** after the verdict/D34 discussion (before "Detection, in plain
  numbers"). *Before:* nothing. *After:* "The 12% cost cap was a judgment call, and it is
  not load-bearing." Discloses the cap was a pre-committed judgment, not derived
  (`[AUTHOR-INPUT]` re: any recorded rationale); states invariance (A1: fails any cap below
  55.5%; second-family floor fails any cap below 17%); locates 12% post-hoc on the
  break-even curve (A2: p*≈41% under a generous reading). *Rationale: Edit 1a/1b/1c ---
  disclose, then show the choice is not load-bearing.*
- **§10 (Threats), one sentence** appended to "The free-looking mock cuts both ways":
  the 12% bar was a disclosed judgment and the verdict does not turn on it. *Edit 1 (§10).*
- **Appendix B, extension** (`tab:breakeven-locate` + paragraph "Locating the 12% cap on
  this curve (post-hoc)"): the frozen model admits no positive break-even at the measured
  fan-out (R=$0.221 > ΔW=$0.068; free monitor cost-negative until ~10 workers); the
  generous waste-recovery locator table (max clean overhead 1.5/2.9/7.3/14.6% at
  p=0.05/0.10/0.25/0.50) and p*≈41%. *Edit 1c; A2. Honest non-inversion, not forced.*

## Edit 2 --- Preempt the triviality attack; unify the coupling; resolve §8/§9 tension
- **§8 opening, new paragraph** "Start with the prediction economics makes.": states the
  naive amortization prediction (a once-per-run cost should vanish per worker at fan-out)
  BEFORE the results, then says the measurement returned the opposite direction. *Edit 2a
  --- §8 now kills a prediction.*
- **§8 "Putting it together", new paragraph** "The coupling has one root, on both model
  families.": the unifying statement --- you cannot monitor a plan without reading it;
  reading the plan is the irreducible cost; incumbent = reasoning step, GPT-5.5 = input
  tokens via coverage; "coverage of the plan's assumptions has a floor cost proportional
  to the plan." *Edit 2b.*
- **§8, forward reference** added after "that step *is* the reasoning that produces the
  detection": "(§9 sharpens this: ... the load-bearing content ... is its *coverage* ...
  not its reasoning effort.)" §8's incumbent-writer claim is left intact. *Edit 2c ---
  resolves the latent §8/§9 tension by reference, not rewrite.*
- **§1 clause** ("Section 8 shows ...") rewritten to add the irreducible-cost unification
  and the check-writer-seam qualifier; **Contributions bullet 1** rewritten to say the
  finding reproduces "with a second vendor's model in the check-writer's seat ... through a
  different mechanism (checklist coverage, not reasoning effort)." *Edit 2b echoes.*
- **Edit 2d gate:** A8 (warm-cache writer floor) was NOT run, so no wording change was
  triggered. Flagged in AUTHOR_TODO: if A8 is later run and cached full coverage clears
  12%, Edit 2(b)/(d) must be re-scoped to uncached writers.

## Edit 3 --- The noiseless-world asymmetry
- **§10 (Threats), new paragraph** "The mock generates no benign noise, and that bounds the
  other verdict." after "The free-looking mock cuts both ways": the mock emits no benign
  anomalies, so the zero-false-alarm results are upper bounds; real noise could re-open the
  §6 self-starvation mechanism, so the confirmatory detection numbers inherit the
  qualification; probe side-effect point (a probe on a metered surface spends the quota it
  checks --- RESOURCE_BUDGET probe potentially self-defeating live); symmetry sentence.
  A7 not run, so this is a pure concession with an `[AUTHOR-INPUT]` pointer to the A7
  pre-registration. *Rationale: Edit 3.*

## Edit 4 --- Scope the amortization claim to the tested axis
- **§8 "The obvious fix doesn't open", new paragraph** "That closes the width escape; a
  depth escape we do not close.": names the depth escape (longer tasks), and concedes it
  using the A5-returned sentence (ii) --- proportionality is untestable here (execution
  depth ~constant across archetypes, plan/execution weakly coupled, Pearson 0.30,
  post-hoc), so we scope the coupling to runs whose plan is a non-trivial fraction of
  execution (0.32--0.86 of worker tokens), the fan-out regime the paper targets. *Rationale:
  Edit 4; A5 returned (ii), not (i).*

## Edit 5 --- The value model: make the verdict's conditionality explicit
- **§8 "Putting it together", new paragraph** "The verdict is conditional on how value is
  priced.": the coupling holds under any value model; "does not yet pay for itself" is
  token-denominated; the 14 detect-and-justified-stop runs each prevented a
  confidently-wrong deliverable (the opening run's outcome), priced at zero by every bar;
  correctness-denominated economics are open; insurance framing ("no one buys insurance for
  the refund"). **§11 (Conclusion), echo** paragraph added. *Rationale: Edit 5.*

## Edit 6 --- Promote the fault-timing scope condition
- **§7 DEPENDENCY_VERSION paragraph** tail rewritten: the read-side miss is elevated from
  an account of one miss into a scope statement over ALL detections --- a
  reference-comparison monitor catches a fault only if it lands after its opening reading
  and before its last look; the benchmark's main faults fire at the halfway point (inside
  the window by construction); DEPENDENCY_VERSION fires before the window opens, walling
  every comparison-based system. *Edit 6a.*
- **§1** "a limit of the benchmark, not of our design" removed; replaced with the
  observation-bound framing ("the same observation bound met on the read side ... by any
  system"). *Edit 6b --- defensive phrasing out, thesis-instance in.*
- §4 optional sentence: not added (optional; the §7 scope statement carries it).

## Edit 7 --- The waste-parity autopsy
- **§7, new paragraph** "Why the redesign wastes more than the do-nothing heartbeat (a
  post-hoc autopsy)." placed beside the KG4 verdict (choice: §7, so the autopsy sits next
  to the 7008/6404 gate it explains). Inserts the A3 result: the entire mean gap (+807) is
  re-dispatch rework (bucket c, +1,055 mean, 8/31 cells; heartbeat discards nothing); it is
  NOT sunk pre-fault cost (redesign books less of that than the heartbeat, 2,278 vs 2,806);
  excluding re-dispatch rework the redesign's median waste falls to 6,117, below 6,404. The
  frozen 1.09x line is unchanged. *Rationale: Edit 7. NOTE: the data did not support the
  brief's floated "sunk-cost double-punishment" story; the autopsy reports the actual driver
  (recovery cost), labeled post-hoc.*

## Edit 8 --- Global claim audit
- **Abstract** rewritten from ~490 words (an introduction) to ~270. Preserved: two-halves
  finding, three FAIL verdicts ("failed---three times"), second-family result,
  destabilization finding. Cut: opening-anecdote and run-level detail (12-second story, 3x
  speed, 12/12 same-seed, the 3/5 transfer number). *Edit 8 (abstract owned).*
- **"3x faster" carries "where signals recur"** at all occurrences (verified): §1 pilot
  result ("where a fault keeps showing up on a surface someone watches"), §1 value
  paragraph ("Where signals recur"), Contributions ("3x speed edge where signals recur").
  The abstract no longer states 3x, so no side-by-side with S3 0/31 there.
- **"Second model family" qualified to the check-writer seam** in abstract ("a second
  vendor's model (GPT-5.5) in the check-writer's seat"), §1, and Contributions.
- **Transfer stated as directional (n=5)** wherever it travels: §7 header/paragraph
  ("It transferred, directionally ..."; Wilson LB 23%; one-sided Fisher p=0.08, "not an
  established effect") and §1 ("a directional edge at n=5, not yet a significant one").
  *A4: transfer p=0.083 > 0.05.*
- **A4 Wilson/Fisher inline** at the headline numbers: §7 detection paragraph --- 24/31
  (Wilson 95% LB 60.2%), redesign vs S2 24/31 vs 12/31 (one-sided Fisher p=0.002); 3/5
  transfer (Wilson 23%, Fisher p=0.08); per-category n=3 cells carry the ~44% Wilson bound.
- **10/15 vs 24/31**: added the gated-subset definition + freeze provenance
  (`[AUTHOR-INPUT]`) and the note that 24/31 (77%) also clears the 60% bar so the gate
  choice is not outcome-determining (`[AUTHOR-INPUT]` to verify the arithmetic claim).
- **Per-category "perfect on the five seen fault types"** now travels with the n=3 / Wilson
  caveat (§7); it does not appear in the abstract.
- **A6 sentence** on the residual clean-failure gap added to §7 ("clean-run success 8 of 12
  trails batch's 9 of 12 by a single run ... all four clean failures at zero interrupts ...
  worker-deliverable shortfalls the no-monitor baseline shows too").
- **KG / FIR / TTD expanded at first use**: §4 "What we measure" (time to detection, TTD;
  false-interrupt rate, FIR); §5 bars sentence (the kill gates, KG1--KG4).
  `[AUTHOR-INPUT]` in AUTHOR_TODO to confirm expansions match the pre-reg's terms.
- **15x stakes [ref27]** hedged: "on the order of 15x ... as one production report puts it."
  Second-source option noted in AUTHOR_TODO.
- **References [1], [16], [22], [27]** incomplete --- listed in AUTHOR_TODO, NOT filled.
- **Anonymity ([28]/[29], author block) and page count**: deferred per author instruction;
  see AUTHOR_TODO.
