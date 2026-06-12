"""Architecture v2 package (prereg_1b.md, FROZEN 6c8cc47 as amended by D23;
build scope = sentinel_protocol_v6_1.md §11.9 as amended, memo §5(d)).

Night-shift foundations ONLY (mechanical layers): scaffolding, the #7-class
pattern-liveness fix, escrow loading, the probe side-channel transport, and
read-only probe primitives. The judgment layers — the probe COMPILER and its
prompts/ontology, probe-primary corroboration wiring, event-gated cadence
semantics, and anything touching judge logic — are deliberately absent and
must not be added without the author present.

Design-blindness rule (Rule Zero): nothing in this package may encode
holdout-category-specific knowledge (no resource/quota/version-specific
categories, templates, or probe types). The ontology and compiler follow
§11.9's pre-holdout design exclusively; generic primitives only.

Everything here is feature-flagged OFF by default (sentinel_v2.flags): with
the flag off, no Phase 1 code path changes behavior anywhere.
"""
