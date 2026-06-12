# prereg_1b freeze custody pins (prereg_1b.md §7.2)

**Freeze commit (the ratification signature):** `6c8cc47` —
"prereg_1b FROZEN - author ratification of AUTHOR-1..15 (incl. confirmed
3a manifest + PERMISSION_AUTH ruling)", 2026-06-12. The commit carries the
FROZEN pre-registration, the AUTHOR-5 draw spec, the draw script, and the
AUTHOR-6 re-qualification driver — all before any execution.

SHA-256 of the frozen artifacts (git blob bytes at 6c8cc47, LF-normalized
per .gitattributes; computed byte-faithfully via `git cat-file blob`):

```
0f6cd510e18101dce1ec3327eaef76d8a924598a035cbf82882d41c06d512d44  prereg_1b.md
c53031ee7d80d298ca64ce42a8591c6e4e749908f2e4e63a4e64dbc1234337fe  benchmark/matrix_draw_spec.md
579a16f6d66d205a0249bf47db2fc0eb72d2cffaaa949787a8657118eb174aa3  benchmark/holdouts/RESOURCE_BUDGET.md
463993c4a8b1066e4429641fa3bdb5de5cc53161c28b1fca7fba9578fbc220ae  benchmark/holdouts/DEPENDENCY_VERSION.md
```

Escrow hashes restated (the only public traces of the sealed values):

```
df1dcd8bd1cad04f815576cc1d6876807e95bbf25ffc959ada40ff0fa2bb3c88  escrow/holdout_escrow.json (decisions/holdout_escrow_record.md)
2a9aed0a386df2f0fe5fa2122b2d85114f699eea8d6b2085df786cbeb6204e0e  escrow/matrix_escrow.json (decisions/matrix_escrow_record.md)
```

v2 artifact hashes cannot exist at freeze (the build follows the freeze by
construction, memo §5(a)); they are pinned by the build's own commits.
Changes to the frozen pre-registration hereafter only via numbered
deviations (next: D23).
