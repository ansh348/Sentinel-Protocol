# Open Questions — fse_focused_v1.md

Author decisions flagged during the rewrite, unreconciled numbers, and title
options. Nothing here blocks reading the paper; each item is a call only the
author can make.

---

## A. Title options
Keep one, or mix. All three signal the coupling; (1) keeps the requested hook.

1. **When the Monitor Blinds Itself: Observation-Bounded, Cost-Coupled Failure
   Detection in Multi-Agent LLM Systems** *(working title in the rewrite — keeps
   the original hook, adds the coupling)*
2. **No Free Lunch in Plan-Compiled Monitoring: Failure Detection Is
   Observation-Bounded and Coupled to Cost**
3. **Restoring Observation Is Not Free: Observation-Bounded Detection and Its
   Coupling to Cost in Budget-Bounded Multi-Agent LLM Systems**

Original draft title (preserved as an option): "When the Monitor Blinds Itself:
Observation-Bounded Failure Detection in Multi-Agent LLM Systems."

---

## B. Decisions I made that the author should ratify

1. **Phase-1c freeze decision resolved to "confirmatory NOT warranted."**
   The draft's CV-pilot block (`fse_draft5_wip.md` line 330) explicitly parked
   two framings — (a) closing negative vs (b) confirmatory pending at
   re-specified H — and said "Do NOT finalize until the freeze decision is made."
   Per the brief's instruction, I resolved it to **(a) closing negative** in §8.
   This *strengthens* the OVERALL FAIL (it does not touch it) and is consistent
   with `decision_memo_phase1.md §2` (any v2 efficiency claim must be earned, not
   assumed). **The author must formally ratify this freeze**, since the pilot
   artifacts are marked "NOT FROZEN." If the author instead wants framing (b), §8's
   "closing negative" paragraph becomes a "sizing pilot / confirmatory deferred"
   paragraph; the coupling argument is unaffected either way.

2. **CV-pilot point estimate carried as NON-DETERMINATIVE.** §8 reports "v2
   costlier than batch at every width, gap widening with width" with the explicit
   label that this is the sizing pilot's *point estimate, excluded from the
   sizing arithmetic* — not a powered result (per `cv_result.json`,
   `CV_PILOT_SUMMARY.md`, E4 firewall). Confirm this epistemic labeling is how you
   want the closing negative stated. It is the honest reading and it converges
   with every other cost result, but it is not an inferential verdict.

3. **V2nc used as a cost-isolation in §8, with a caveat.** §8 cites the no-compile
   variant (near cost-neutral clean → the compile *is* the cost center) but flags
   that its detection-equivalence is established only on its single-surface home
   case (`CV_PILOT_SUMMARY.md`; the §10 language-pass TODO at draft line 345 flags
   the same: "reconcile V2nc framing as cost-isolating-not-detection-equivalence").
   Decide whether to keep this sentence, cut it, or expand V2nc into a named arm.
   I kept it minimal and caveated.

4. **Real-suite study (draft §8) cut from the body.** Removed as a `[PENDING]`
   future section; its one live point (deployment efficiency remains open) is
   absorbed into §8/§9. Confirm you do not want a short "Future Work" stub.

5. **Fan-out N≈86/40/25 extrapolations → Appendix B**, labeled "predictions, not
   results." The brief allowed "appendix or one sentence"; I chose the appendix so
   the body stays clean. Move to a single §8 sentence if you prefer zero appendix.

6. **1bKG1 reported decomposed.** §7 states detection sub-terms PASS while the
   composite prints FAIL due to the folded Standing precondition (D34), OVERALL
   FAIL resting on 1bKG3. This is faithful to `gate_report_final.json` (which lists
   `1bKG1: FAIL`, `instrumentation_replay: FAIL`, `verdict: FAIL`). Confirm you are
   comfortable presenting the gate-folding/prereg divergence in the body (it is
   load-bearing for honesty and is logged as D34); the alternative is to relegate
   the decomposition to Appendix A and print only the composite + OVERALL.

7. **Anonymized prior work (draft line 78 `[AUTHOR: …]`).** v6.1 §9.8 cites two
   identity-revealing unpublished prior systems ([28]/[29]). The rewrite omits the
   paragraph from §2 and leaves [28]/[29] anonymized in references. Decide at
   submission: omit, or cite via an anonymized supplement.

8. **Format is Markdown, not LaTeX sigconf.** The deliverable mirrors the source
   format (`.md` with HTML-comment provenance) and carries per-section page
   budgets as comments. Final typesetting into the ACM `sigconf` two-column
   template, and a true page count, are an author step. Budgets are estimates.

---

## C. Numbers — all reconciled; verification notes only

No number required a `<!-- TODO[author] -->`. Every figure in the rewrite was
checked against a source-of-truth file. Notes on the few worth a second look:

1. **v1 KG3 cost figures.** The draft and `kill_gates_final.md` differ in
   rounding: kill gates print `S5 med $1.178952 vs S1 med $0.340831`; draft §9
   rounds to `$1.179 / $0.341`. The rewrite keeps the verbatim gate block
   ($1.178952 / $0.340831) in §5 and Appendix B's break-even uses the
   `archaeology_v2.md §F` fitted parameters. Consistent; no discrepancy.

2. **172 vs 215 cells.** `gate_report_final.json` has `n_records: 172`. The 215
   figure in earlier deviation prose (D23) was the *five-arm* plan; the
   confirmatory fired *four* arms (V2J deferred, D33), so 43 × 4 = 172. The
   rewrite uses 172 with the four-arm composition stated. Reconciled.

3. **DEPENDENCY_VERSION mechanism.** The rewrite uses the *corrected* read-side
   observation-bound account (injection at counter 1 precedes the arm-time sweep →
   dirty baseline; no version field in any payload → harness-wide 0/5), per
   `runs/matrix_1b/dv_claim_verification.md` and the draft's `CC 2026-06-29 EDIT 1`
   correction. The pre-correction "lone s2505 5→3 truncation" reading is NOT used.
   Confirm `dv_claim_verification.md` is the final word (it is the most recent
   read-only verification in the corpus).

4. **3× latency, twice.** v1 KG4 TTD (median 3 vs 9) in §5 and the v2 TTD (median
   9.5; S3 0/31) in §7 are distinct numbers from distinct studies. The §1/§3 "3×
   faster where signals recur" refers to the v1 KG4 surviving result. Kept
   distinct; no conflation.

5. **Held-out qualification "third revision."** §4 says DEPENDENCY_VERSION
   qualified only at its third specification revision. `holdout_qualification_
   2026-06-12.md` shows: rev-2 NOT qualified → author ruling → rev-3
   re-qualification FAILED → author ruling #2 → rev-3/rev-4 (page_limit) QUALIFIED.
   "Third revision" is a fair summary of a 3-attempt qualification; verify the
   exact rev label (the final qualifying world is `world_rev 4`, spec "rev 3") if
   you want the precise wording in §4.

---

## D. Things to verify before submission (not blocking)

1. **Exact FSE page limit.** I budgeted 10pp body + ≤2pp references (recent
   FSE/ICSE research-track norm) but could not verify the *current* edition's CFP
   in this environment. **Re-check the live Call for Papers** — some editions
   state "10 pages including everything but references"; a few allow 11. Adjust
   §-budgets in MIGRATION_NOTES if it differs.

2. **References hygiene.** [21] (Learning to Interrupt) and [33] (Karnofsky) are
   uncited in both the draft and the rewrite — cite them or drop them. [16] needs
   its arXiv ID confirmed; [37] needs final venue/pages; [1] needs verification.
   The draft's standing related-work sweep note (draft lines 426–430: Watson/ASE
   2025, ABRV/NuRV, Cohen & Peled, nl2spec, NL2TL, the unconfirmed "LLMon") is
   carried forward as a submission-time task, not into the body.

3. **Anonymization sweep.** Re-scan for any institution/repo/venue leak before
   submission; the rewrite body contains none, but the references and any final
   acknowledgments are the usual leak sites.

4. **"Findings, not laws" register.** §9 keeps this explicitly. If a reviewer
   reads the coupling as over-claimed, the fallback is to qualify §8's final
   sentence to "in this setting" — already scoped in §9, but the author may want
   it doubled in §8.
