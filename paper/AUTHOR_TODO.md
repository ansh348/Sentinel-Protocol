# AUTHOR_TODO.md --- fse_focused_v5.tex

Every item below is a decision, value, or verification I was not authorized to make or
could not source without risking fabrication. Nothing here was guessed or filled in.

## A. `[AUTHOR-INPUT]` placeholders in the source (4)
1. **§7, line ~552 --- rationale for the 12% cap.** "confirm whether the frozen
   pre-registration records any informal rationale for the 12% figure; if it records none,
   state that none existed." The disclosure paragraph asserts the cap was a pre-committed
   judgment, not derived; if the pre-reg contains a recorded informal rationale, quote it
   verbatim and cite the pre-reg. If none, replace the placeholder with "the
   pre-registration records no rationale for the figure."
2. **§7, line ~588 --- gated-subset (10/15) rule + freeze provenance.** "confirm the
   gated-subset rule and its freeze provenance." The text says the 10/15 subset is
   "restricted to cells that admit a recovery path, a rule frozen in the pre-registration."
   Confirm the exact rule and when it was frozen; supply the citation.
3. **§7, line ~591 --- 24/31 clears the 60% bar (arithmetic claim).** "verify the author
   endorses this arithmetic claim." The text says the gate choice is not outcome-determining
   because 24/31 (77%) also clears the 60% detection bar. Confirm this is a claim you
   endorse (24/31 = 77.4% >= 60%; it is arithmetically true, but confirm it is the framing
   you want).
4. **§10, line ~935 --- A7 status.** "A7 (benign-noise smoke) is pre-registered but not yet
   run; if run, replace this concession with the measured bound and cite the A7 mini
   pre-registration." See section D below.

## B. Incomplete references (NOT filled --- do not fabricate)
- **[ref1]** "Execution monitoring survey (Dunlap et al.)." --- missing venue, year, full
  author list, DOI/arXiv.
- **[ref16]** "Wasted-computation diagnosis in multi-agent systems." --- missing authors,
  venue, year, arXiv id. (Cited at §1 stakes and §2.)
- **[ref22]** "LangGraph interrupt documentation." --- missing URL and access date.
- **[ref27]** "Anthropic Engineering. How we built our multi-agent research system." ---
  missing URL and access date. **This is the sole source for the 15x token multiplier**
  (§1 stakes); a second source would strengthen it (see item C4).
- Pre-existing (carried from OPEN_QUESTIONS, not introduced here): [21] and [33] are
  uncited; [16] arXiv id; [37] venue/pages; [1] verification.

## C. Verifications and small judgments to confirm
1. **Abstract length.** Now ~270 prose words (down from ~490). Standard FSE length. Trim to
   a hard ~250 if you prefer; the required elements (two-halves finding, three FAILs,
   second-family, destabilization) are all present and must be preserved in any trim.
2. **KG / FIR / TTD expansions.** I expanded FIR = false-interrupt rate, TTD = time to
   detection (§4), and KG = kill gate (§5, "KG1--KG4"). Confirm these expansions match the
   exact terms used in the frozen pre-registration.
3. **"3x faster" reconciliation with S3 0/31.** The 3x-faster claim (v1 pilot KG4, where S3
   detected) now always carries the "where signals recur" qualifier; S3's 0/31 is the v2
   confirmatory result (quiet, seen-once faults, no recurrence). These are distinct studies;
   confirm you are comfortable that the qualifier is sufficient reconciliation, or add a
   one-clause footnote.
4. **15x hedge.** I added "as one production report puts it." If a second independent source
   for the multiplier exists, add it; do not fabricate one.
5. **Edit 7 placement + framing.** The waste-parity autopsy went in §7 (beside the KG4
   gate). It reports the *actual* driver (re-dispatch recovery cost), which is NOT the
   "sunk-cost double-punishment" story the brief floated --- the data did not support that
   story (the redesign books *less* pre-fault sunk cost than the heartbeat). Confirm you are
   comfortable with the corrected framing. Underlying numbers: `analysis/v5_hardening/A3_*`.

## D. Spend-gated analyses NOT run (require your explicit go-ahead)
- **A7 (benign-noise smoke, ~$5--15).** Mini pre-registration written and staged at
  `analysis/v5_hardening/A7_benign_noise_smoke_PREREG.md` --- NOT executed. If you approve:
  ratify + commit the pre-reg with a real timestamp BEFORE running, then run and replace the
  §10 concession (Edit 3) with the measured FIR bound.
- **A8 (warm-cache writer floor, ~$2--5).** Mini pre-registration at
  `analysis/v5_hardening/A8_warm_cache_writer_floor_PREREG.md` --- NOT executed.
  **Edit 2d gate:** if A8 is run and cached full coverage clears the 12% cap, the coupling
  claim must be scoped to *uncached* writers and Edit 2(b)/(d) reworded. Until then §8/§9
  wording assumes the uncached floor, consistent with §9's caution (2).

## E. Deferred at your instruction during this pass (NOT done)
- **Anonymity sweep (constraint 5).** NOT performed. The paper is still the named version:
  author block (Mullick, Tuzun; Bilkent University; emails), the header comment "Named
  (non-anonymous) version," and refs [28]/[29] ("Mullick, Tuzun") remain. For a
  double-anonymous FSE submission these must be neutralized and [28]/[29] anonymized.
- **Page limit / FSE 2027 CFP format.** NOT checked or changed. The source is `acmsmall`
  (PACMSE / FSE 2026 journal style), `\acmYear{2026}`; it currently typesets to 17 pages
  single-column. Verify the FSE 2027 CFP format and page budget and reformat as needed
  before submission.

## F. Provenance
All inserted numbers trace to `analysis/v5_hardening/` (Prompt A, read-only over banked
data): A1 (bar robustness), A2 (break-even location), A3 (waste decomposition), A4
(Wilson/Fisher), A5 (plan-size vs depth), A6 (clean-failure gap). Each script writes a
paste-ready `.md` and a raw `.json`; re-run with `python analysis/v5_hardening/aN_*.py`.
