# Migration Notes — fse_draft5_wip.md → fse_focused_v1.md

The original `fse_draft5_wip.md` is preserved byte-for-byte. `fse_focused_v1.md`
is a clean rewrite, not an edit. Below: the one-page reframe plan + section
budget, then a section-by-section log of every move, cut, and relegation.

---

## Part 1 — Reframe plan + section budget

### The problem with the draft
The draft tries to be six papers at once — v1 pilot, v2 confirmatory, the
diagnosis battery, TripwireBench, the fan-out arm, and a v3 cost program — and
reports its economics as a *string of separate failures*, each softened in
turn: the v1 cost inversion, v2's 55.5% vs the 12% cap, the 1.09× waste-parity
miss, the fan-out extrapolations, the mock-floor caveat, and a visibly
*undecided* Phase-1c placeholder ("two framings pending author freeze"). It is
~18pp single-column `acmsmall`, layered with `[NEW · author review]` / changelog
scaffolding and `[PENDING]` markers. A reviewer bounces off page 2.

### The one thesis
> In budget-bounded multi-agent LLM execution, failure detection is
> OBSERVATION-bounded, not INTELLIGENCE-bounded — and because the mechanism that
> restores observation (per-plan compilation) is also the irreducible cost
> center, DETECTION AND ECONOMY ARE COUPLED: restoring observation fixes
> detection and eliminates false-interrupt self-harm, but does not yet pay for
> itself.

Everything serves that sentence. The negatives stop being missed targets and
become one converging **no-free-lunch finding**.

### The five moves that do the work
1. **Synthesize the economics (the core change).** The four cost negatives are
   recast as one fact in a dedicated payoff section (§8): the cost autopsy
   localizes *all* overhead to the per-plan compile, which is the
   capability-critical step → the cost cannot be cut without risking the
   detection → that mutual dependence IS the coupling. Stop softening; converge.
2. **The fan-out negative STRENGTHENS the claim.** The obvious rescue is
   amortizing a once-per-run compile over more workers; the CV pilot shows the
   gap *widens* with width — exactly what coupling predicts. Reported as a
   CLOSING NEGATIVE, decisively resolving the Phase-1c indecision toward
   "confirmatory not warranted." The ~$4,430-vs-$450 affordability gap is a
   secondary, incidental note — not the headline.
3. **Flip the mock-floor into a strength.** The mock gives the architecture the
   most generous cost environment (free re-observation) and it STILL fails the
   budget, on the one-time compile alone, structurally. "The floor still fails."
4. **Re-ground the value proposition on latency + correctness + partial
   generalization** so the paper never reads as "an architecture that failed at
   its only purpose": 3× detection latency where signals recur; zero clean false
   interrupts; held-out RESOURCE_BUDGET 3/5 where passive baselines score 0/5.
5. **Delete the scaffolding.** Every `[NEW · author review]`, changelog,
   `[PENDING]`, "results forthcoming," "two framings pending," and "PLACEHOLDER"
   is collapsed into finished prose. Visible indecision is a defect reviewers
   punish; the paper now reads as done.

### Hard constraints honored
- OVERALL FAIL stays — recharacterized, never walked back. No empirical number
  altered. Unreconciled numbers would be flagged `<!-- TODO[author] -->` and
  listed in OPEN_QUESTIONS; **none were needed — every number reconciled.**
- Provenance kept: `<!-- src: ... -->` on every number, epistemic labels travel,
  deviation IDs (D23/D24/D25/D27/D28–D34) carried where load-bearing.
- Double-anonymity preserved: no names, institutions, repo URLs, or venue name.
- Original file untouched.

### Format + page budget (two-column ACM sigconf; 10pp body + ≤2pp refs)
Recent FSE/ICSE research-track norm is 10pp main text (figures/tables inclusive)
+ ≤2pp references. EXACT current limit to be re-verified against the live CFP
(flagged in OPEN_QUESTIONS); budgeted to 10+2 in the meantime.

| § | Section | Budget |
|---|---|---|
| 1 | Introduction (hook + finding + value re-ground + contributions) | 1.25pp |
| 2 | Background / Related (RVPLAN confrontation kept; rest compressed) | 1.0pp |
| 3 | Sentinel Protocol **as instrument** | 1.25pp |
| 4 | TripwireBench + protocol | 1.0pp |
| 5 | Pre-registered pilot + verdict (v1) | 1.25pp |
| 6 | Failure archaeology + adjudicated diagnosis | 1.0pp |
| 7 | Confirmatory study (v2) | 1.25pp |
| 8 | **Coupling / no-free-lunch synthesis** (payoff) | 1.0pp |
| 9 | Threats to validity | 0.5pp |
| 10 | Conclusion | 0.5pp |
| — | **Body total** | **~10.0pp** |
| — | References | ≤2.0pp |
| — | Data Availability + Appendices A/B | supplementary, uncounted |

Net cut: ~18pp single-column `acmsmall` → ~10pp two-column `sigconf`, plus the
full removal of the editorial/changelog apparatus.

---

## Part 2 — Section-by-section log

### Header / changelog block (draft lines 1–14)
- **CUT** all five `CHANGELOG v0.2–v0.5` blocks and the format preamble. Replaced
  with one compact provenance header naming the source-of-truth files and the
  anonymity/provenance rules. *Rationale: editorial apparatus, not paper content.*

### Title (draft line 16)
- **CHANGED** "When the Monitor Blinds Itself: Observation-Bounded Failure
  Detection in Multi-Agent LLM Systems" → "…: Observation-Bounded, **Cost-Coupled**
  Failure Detection…". *Rationale: the title now signals the coupling, the actual
  finding. Alternatives in OPEN_QUESTIONS; original kept as an option.*

### Abstract (draft lines 18–23, plus the `[NEW]` proposed-close)
- **REWRITTEN.** The draft's ~60-word opening sentence is broken into short
  sentences. Leads with the finding (both halves), states the v1 kill, the
  diagnosis, the v2 detect-and-generalize win, the OVERALL FAIL on economics, and
  closes on the coupling + "does not yet pay for itself." The two-layer
  abstract-plus-`[NEW]`-proposed-close is collapsed into one finished abstract.

### §1 Introduction (draft 26–57)
- **KEPT** the "twelve seconds before the injection" specimen verbatim as the hook.
- **RESOLVED** the `[PENDING: Phase 1b confirmatory results…]` line and the two
  `[NEW · author review]` outcome/contribution blocks into clean prose: the
  confirmatory verdict is stated as in-hand, not pending.
- **ADDED** an explicit value-proposition paragraph ("not a tool that failed at
  its only purpose": latency + zero clean injury + partial generalization).
- **REWROTE contributions** from six overlapping items to five: the finding
  (incl. coupling) leads; methodology, diagnosis method, TripwireBench, and the
  surviving + naive-baseline results follow. *Rationale: the draft listed the
  finding plus a v1-style "pending redesign"; the finding now subsumes both.*

### §2 Background and Related Work (draft 60–78)
- **KEPT** the RVPLAN "nearest ancestor, three assumptions fail" confrontation
  near-verbatim (the load-bearing positioning).
- **COMPRESSED** self-adaptive systems, RV/guardrails/taxonomies/observability,
  and orchestration into two tight paragraphs from ~seven.
- **CUT** the standalone "Positioning in one sentence" paragraph and the v6.1
  "honest identity" addendum (folded into §3) and the `[AUTHOR: …]` anonymization
  note (moved to OPEN_QUESTIONS).

### §3 Sentinel Protocol (draft 81–127)
- **REFRAMED** as "Sentinel Protocol **as Instrument**" with an explicit opening:
  this is the thing we pre-registered, killed, diagnosed, and rebuilt.
- **COMPRESSED** the three tiers + six-phase cycle into one paragraph.
- **KEPT** the DSL, the compiled active probe + its three measurement-forced
  constraints, the judge removal, the category-blind compiler, and the
  observability-by-signal-shape lesson — all compressed.
- **FOLDED** the `[NEW]` arm-time-baseline (D30) and the v1-present-tense scoping
  `[NEW]` correction directly into the probe and category-blind paragraphs.
- **CUT** the `evidence_class`/`recovery_class`/priced-ABORT detail and the
  KG0-coverage 67%→89% mechanics (the latter survives once, in §6 Finding 1).

### §4 TripwireBench (draft 130–148)
- **COMPRESSED** to ~1pp. Kept manipulation qualification, the escrowed held-out
  categories, systems-under-test (now noting the four-arm confirmatory set, D33),
  metrics, and the integrity machinery.
- **CONDENSED** the held-out qualification texture (pre-armoring, single-visit
  immunization, competence-as-immunity/D23) from ~3 paragraphs to 2 sentences.
- **CUT** the per-archetype task descriptions and the "full study wraps GAIA/
  tau-bench/SWE-bench" sentence (the real-suite study is no longer a body section).

### §5 The Pre-Registered Pilot and Its Verdict (draft 151–179)
- **KEPT VERBATIM** the four-line KG1–KG4 gate block (sealed prose).
- **KEPT** the naive-baseline-beats-architecture result (S2 15/27, FIR 0.0,
  per-category) at full prominence, and the self-injury anatomy.
- **MADE THE BEHAVIORAL SENTENCE LAND**: "the frozen gates returned FAIL on the
  authors' own flagship, and the pre-committed branches executed as written."
- **FOLDED** the `[NEW]` Phase-1/Phase-1b scope block into one transition clause.
- **CUT** the compilation-quality-gate operational detail and the 9/26-vs-9/27
  denominator footnote (kept the load-bearing "real sensor silence" point).

### §6 Failure Archaeology and the Adjudicated Diagnosis (draft 181–214)
- **PULLED THE SAME-SEED RESULT FORWARD** and made it explicitly load-bearing:
  "the dumb baselines saw what the smart monitor missed (12/12)" — the strongest
  evidence for the not-intelligence-bounded half.
- **COMPRESSED** the rival-story adjudication table (4 rows) into one sentence of
  decisive discriminations.
- **KEPT** errata-visible (single-visit withdrawal; dead-pattern class/D24),
  compressed to one paragraph.
- **KEPT** the shadow replay as an explicit projected ceiling (18/18; 21/27),
  quoted as feasibility not result.
- **RELOCATED** the entire `[NEW]` confirmatory cost-autopsy block (draft 206–214,
  G2/G3/G4) OUT of §6 and INTO §8, where it does the coupling work. *Rationale:
  it concerns the v2 verdict and is the engine of the synthesis, not v1 archaeology.*

### §7 Confirmatory Study (draft 217–285)
- **DELETED** all scaffolding: the `was: **Results.** [PENDING…]` marker, the
  `[NEW · author review]` wrappers, the D33 pre-fire VERBATIM block, and the long
  inline `CC 2026-06-29 EDIT 1` correction comments.
- **KEPT** the gate block (reformatted, compressed) and the decomposed reporting
  of 1bKG1 (detection sub-terms PASS; folded Standing precondition / D34 prints
  composite FAIL; OVERALL FAIL rests on 1bKG3) — accurate and visible, ~2 sentences.
- **KEPT** the detection inventory (24/31; S1/S3 0/31; S2 12/31), the
  denominator reconciliation (24/31 vs 10/15 = definitional), per-category Wilson
  bounds, the held-out RESOURCE_BUDGET 3/5 vs 0/5 win, and the corrected
  DEPENDENCY_VERSION 0/5 read-side observation-bound mechanism.
- **KEPT** the 1bKG2 reversal and the FIR-0 robustness (settings.yaml write; S2
  false-fires 4 clean cells).
- **CUT** the integrity-rules paragraph to its load-bearing clauses; **MOVED** the
  v2 economics paragraphs (draft `[NEW]` 303–311) into §8; **CUT** §9.1 Phase-1c
  DESIGN prose and the CV-pilot PLACEHOLDER block from the body (synthesized into
  §8's closing negative); **CUT** the standalone holdout-qualification-complete
  paragraph (folded into §4).

### §8 (NEW) Coupling: A No-Free-Lunch Result
- **NEW SECTION** assembled from: the §6 `[NEW]` cost autopsy (G3 compile
  localization), the §9 `[NEW]` cost/capability-tradeoff and mock-floor blocks,
  the §9.1 fan-out rationale, and the CV-pilot result — recast as one converging
  argument under four headings (cost-is-capability; rescue-does-not-open;
  floor-still-fails; one-sentence synthesis). This is the payoff the draft
  scattered across §6, §9, and §9.1.

### §9 Threats to Validity (draft 335–375)
- **COMPRESSED** to 0.5pp under four headings (scope/findings-not-laws;
  mock-floor as strength-and-bound; benchmark-leak + held-out custody;
  builder-bias behavioral counterweight).
- **FOLDED IN** the D33 lens-extraction, projection-optimism, relation-detection,
  and write-surface-residual `[NEW]` blocks as brief named residuals (detail in
  Data Availability / Appendix A), rather than four separate blocks.
- **KILLED** law-like phrasing; kept "findings, not laws."

### §8 Real-Suite Study (draft 288–292) — **CUT from the body**
- The future real-suite study (schedule gate 3) is removed as a body section. Its
  one load-bearing point — that a deployment-efficiency claim remains the open
  question — is absorbed into §8 and §9. *Rationale: nothing in it exists yet; a
  `[PENDING]` future-work section is exactly the "six papers" sprawl to cut.*

### §9 Economics (draft 295–332) — **dissolved into §8 + Appendix B**
- Headline cost numbers, the break-even kill, and the v2 economics → §8.
- The N≈86/40/25 fan-out extrapolations → **Appendix B**, explicitly "predictions,
  not results" (per brief: appendix or one sentence).
- The v3 cost-levers `[NEW]` block → compressed into §8's "v3 problem" close.

### §11 Conclusion (draft 377–379) — **§10 here**
- **REWRITTEN** short, restating both halves of the finding and the coupling.
  Collapsed the `[NEW]` confirmatory-verdict-sentence into the body.

### Data Availability (draft 381–383)
- **KEPT**, updated to include the 172-cell matrix, cost autopsy, and fan-out
  sizing pilot.

### Per-deviation D-number relitigation (throughout draft) — **relegated**
- Heavy inline deviation argumentation (D23/D24/D25/D27/D28–D34) summarized in
  **Appendix A** and cited by ID in the body where load-bearing. *Per brief:
  summarize in body, push detail to a deviations appendix / Data Availability.*

### References (draft 386–424)
- **KEPT** as-is (re-verify-at-submission discipline preserved). Note: draft
  references [21], [33] are uncited in both draft and rewrite; [28]/[29] remain
  anonymized. Flagged in OPEN_QUESTIONS.
