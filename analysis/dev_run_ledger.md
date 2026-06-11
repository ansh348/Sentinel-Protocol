# Dev-run ledger — every execution involving a v2-style component

Opened 2026-06-12 per the Phase 1b archaeology-v2 brief (and per the GPT-5.5 Pro review's
"data embargo / publish a dev-run ledger" tightening, adopted here ahead of any ruling).
Scope: every execution of probe construction, probe execution, policy replay, or
deterministic-world re-instantiation — anything that exercises a v2-style component or
touches benchmark-world outputs outside the banked traces. Pure reads of banked trace
files are NOT ledgered; world re-instantiation IS.

Columns: UTC timestamp | component | purpose | inputs | LLM cost (USD) | notes

| ts (UTC) | component | purpose | inputs | LLM cost | notes |
|---|---|---|---|---|---|
| 2026-06-11T22:42Z | world re-instantiation (analysis/replay_check.py) | Phase 0 (iii) byte-identity confirmation | 27 injected S5 cells: world_config.json + recorded tool_call streams; traces redirected to tempdir | $0 | first pass: 26/27; one divergence at d1-S5-endpoint_404-s1 counter 31 |
| 2026-06-11T22:48Z | world re-instantiation (analysis/replay_check.py) | re-run after classifying the LOSSY-REQ exclusion (invalid-UTF8 request bytes unrecoverable from trace) | same 27 cells | $0 | 27/27 byte-identical; exclusions counted: control-stripped, tripped-409, lossy-req=1; detail runs/archaeology_v2/replay_check.json |
| 2026-06-11T23:03Z | armed-matcher raw replay (analysis/raw_replay.py) | Task A: pipe recorded raw streams through fresh-armed matchers, 12 L2 cells x 2 dialects + union variant + dead-pattern sweep over 27 cells | banked traces only; no world instantiation | $0 | three runs (initial + union variant + freshness patch); outputs runs/archaeology_v2/raw_replay.json |
