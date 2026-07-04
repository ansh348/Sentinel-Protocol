# fse_focused v5 → v6 change log

v5 is frozen; all edits applied to `fse_focused_v6.tex` only. Every edit traces to an
artifact or an explicit author ruling. Frozen gate/verdict blocks (KG0–KG4, 1bKG1/2/3)
verified **byte-identical** v5↔v6; no measured number changed. v6 compiles (exit 0, PDF
586 KB); only pre-existing undefined-citation warnings remain (bibliography = submission-time).

*(Already in v5 from the prior commit `a7264db`, not v6 changes: the §10 consolidated A7/A7b
paragraph, the §1 "in the noiseless mock (Section~10…)" qualifier, and the §7
"(no benignly volatile fields; \S10)" qualifier.)*

| # | Location | Edit | Motivating artifact / ruling |
|---|---|---|---|
| 1 | §7 (12% cap) | Resolved `[AUTHOR-INPUT]` → "records no rationale for the number…KG3 clean-overhead threshold…pre-committed authors' judgment, disclosed as such." | Phase-1 evidence: 12% appears only as the KG3 threshold (`prereg.md:41`, `pilot_protocol.md:161`), no recorded rationale. **Author ruling ① (verbatim wording).** |
| 2 | §7 (gated subset) | Resolved `[AUTHOR-INPUT]` → "frozen in the Phase-1b pre-registration (prereg\_1b.md, commit `6c8cc47`, 2026-06-12), which labels each injected cell recoverable iff it admits a recovery path." | Freeze pins (`decisions/prereg_1b_freeze_pins.md`): prereg_1b.md @ 6c8cc47, 2026-06-12; recoverable-class rule (prereg_1b.md §2/§11.10). **Author ruling ② (approved).** |
| 3 | §7 (arithmetic) | Resolved `[AUTHOR-INPUT]` → "clears the 60\% detection bar (24 of 31 $=$ 77.4\%)." | `runs/matrix_1b/gate_report_final.json`: `n_detections=24`; 24/31 = 77.42% ≥ 60%. **Author ruling ③ (endorsed the arithmetic).** Frozen 24, 31 unchanged; ratio added. |
| 4 | §1 (exec summary) | "caught 56\% **in the pilot** at zero false alarms" | **Author ruling 2.2:** the 56%/zero-FAR are the *pilot* S2 figures (§5: 15 of 27, FIR zero); D35/12-of-31 are confirmatory. Inserting "pilot" names the study. |
| 5 | §10 (cascade) | Recast pre-measurement voice → measured: self-starvation did not manifest (0 grind-deaths); content channel fires; one-shot status isolated; sustained untested. | A7/A7b report + **D38**. **Author ruling 2.1 (approved).** |
| 6 | §10 (flag) | "we must flag the optimistic noise one" → "we flag---and, in the probe below, measure---the optimistic noise one." | **Author ruling 2.1 (approved).** |
| 7 | §1 (end) | Added **RQ1** (observation bound, §5/§7), **RQ2** (cost coupling, §8), **RQ3** (generality across families + noise, §9/§10). | **Author ruling 4.1 (IN as drafted).** |
| 8 | §8 (value model) | Added post-hoc correctness-denominated frontier: break-even ≈ `$0.13 × 31/(14p)` (≈$2.90 at p=10%, ≈$1.15 at p=25%); complements Appendix~B Table~3. | Confirmatory data only (overhead $0.13/run; 14 of 31 justified stops). **Author ruling 4.2 (reframed per-run/fault-rate form; $0.11 dropped).** Verified Table 3 = `tab:breakeven-locate`. |
| 9 | Data Availability | Added the benign-noise family: A7/A7b mini pre-regs + ratification commits, per-cell ledgers, archived trace zips + committed SHA-256 manifest. | Archive (`archives/MANIFEST.sha256`), ledgers (`runs/a7`, `runs/a7b`). **Author ruling 3.2 (approved).** |
| 10 | Appendix A (Integrity & Departure Log) | Added the benign-noise-family entry (§9-second-family style): A7 addendum ratified 2026-07-02 (`7a3807fe`), A7b 2026-07-03; D35–D38; spend $8.75/$4.96 under caps; all three frozen predictions refuted and retained. | A7/A7b pre-regs + D35–D38. **Author ruling 3.1 (approved).** |

## Deliberate submission-time items (unchanged, by author ruling)
- **Bibliography refs `[28]/[29]`** — live inside bibliography-entry text, not body placeholders; final form governed by double-blind anonymization at submission. (Undefined-citation warnings in the v6 build are the pre-existing unresolved bibliography, identical to v5.)
- **`[REPLICATION-PACKAGE-URL]`** (Data Availability) — the public package address, filled at submission.

## Compile + integrity
- `latexmk -pdf` on `fse_focused_v6.tex`: exit 0, `fse_focused_v6.pdf` produced (586 KB).
- Frozen gate/verdict blocks byte-identical v5↔v6 (KG0–KG4, 1bKG1/2/3, and the measured
  numbers 55.5% / 0.3642 / 0.2342 / 24-of-31 / 10-of-15 / 12-of-31 / 0-of-31 / 7,008 / 6,404).
- Exactly 10 changed hunks; no frozen file touched; v5 unchanged.
