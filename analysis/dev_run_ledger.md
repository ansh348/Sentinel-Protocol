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
