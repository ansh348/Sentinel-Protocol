# Methodology Deviations Log

Pre-registration discipline requires that any departure from the frozen
protocol/brief be recorded here with evidence, before data collection.
`make freeze` must reference this file from `prereg.md`.

---

## D1 — `--bare` replaced by an equivalent-controls invocation

**Date:** 2026-06-10 (before any Phase 0/1 data collection)
**CLI:** Claude Code 2.1.170
**Affects:** BUILD_BRIEF Section 5 ("Always: `--bare` ...") for every `claude -p`
invocation. Author-approved (Option 1) after empirical demonstration that the
constraint is unsatisfiable under the locked Path A decisions.

### Why

BUILD_BRIEF Section 5 requires `--bare` on every invocation; locked decision #1
requires subscription billing with "no API keys anywhere". In CLI 2.1.170 these
are mutually exclusive: `--bare` documents that "Anthropic auth is strictly
ANTHROPIC_API_KEY or apiKeyHelper via --settings (OAuth and keychain are never
read)". Empirical matrix (all probes 2026-06-10, this machine):

| Mode | Auth source | Result |
|---|---|---|
| normal | OAuth credential store (auto-refresh) | works |
| normal | `CLAUDE_CODE_OAUTH_TOKEN` setup-token, isolated home | works |
| `--bare` | credential store / OAuth env token | "Not logged in" |
| `--bare` | `apiKeyHelper` returning the OAuth setup-token | "Invalid API key" (helper output is sent with API-key semantics) |
| `CLAUDE_CODE_SIMPLE=1` (bare's own mechanism) | OAuth env token | "Not logged in" |

The alternative — `ANTHROPIC_API_KEY` under `--bare` — is Path B billing for
the full matrix and violates locked decision #1, so it was rejected.

### Replacement controls (what `conductor/sessions.py` does instead)

The intent of `--bare` is "no environment-dependent context". Each invocation
replicates that explicitly, in normal mode:

1. **Isolated home**: `USERPROFILE` and `HOME` point at a per-call scratch
   directory, so user hooks, settings, plugins, memory, `CLAUDE.md`
   auto-discovery, and the credential store are never read.
2. **Env stripping**: all inherited `CLAUDE*`/`CLAUDECODE` variables are
   removed from the child environment.
3. **`--system-prompt`**: full replacement of the default prompt, fully
   rendered (unchanged from the brief).
4. **`--settings`**: pinned to a generated minimal settings file (`{}`).
5. **`--strict-mcp-config`** with no `--mcp-config`: no MCP servers.
6. **`--tools ""`** for compile/judge/orchestrator (no tools at all);
   `--allowedTools` pinning for workers (unchanged from the brief).
7. **cwd** set to the isolated home, so no project-level `.claude/` or
   `CLAUDE.md` discovery applies.
8. **Scratch homes and cwd live OUTSIDE the user profile tree** (default
   `C:\temp\tripwire-scratch`, override `TRIPWIRE_SCRATCH`), enforced by a
   hard guard in `sessions.py`. Found by the canary test on first run
   (2026-06-10): `CLAUDE.md` discovery walks **cwd ancestors**, so a session
   whose cwd sits anywhere under `C:\Users\<user>` — including the system temp
   directory — picks up `~\.claude\CLAUDE.md` even with `USERPROFILE`/`HOME`
   fully isolated. Probe matrix: home+cwd under user temp → leaked; home+cwd
   outside the user tree → clean; home under user temp but cwd outside →
   clean (the leak is cwd-borne, not env-borne).

Auth is a long-lived subscription OAuth setup-token supplied via
`CLAUDE_CODE_OAUTH_TOKEN` in the child environment only (never argv, never the
repo, never traces — `trace.py` refuses to serialize `sk-ant` material).

### Verification

`tests/test_canary_isolation.py` runs on every `make test`: it plants a marker
`CLAUDE.md` and a marker `SessionStart` hook in the real user config, runs a
sandboxed pong under the recipe above, and asserts both canaries are invisible
(no canary token in the reply; the hook's sentinel file is never created), and
that the resulting trace contains no credential material.

### Residual differences vs `--bare` (accepted)

- LSP/plugin-sync/attribution/background-prefetch code paths are skipped by
  `--bare` outright; under the replacement they run against an empty isolated
  home, which makes them no-ops rather than disabled. No context can enter the
  prompt from an empty home, which is the property the control exists for.
- Enterprise managed settings (`C:\ProgramData\ClaudeCode\managed-settings.json`)
  would apply in normal mode if present. Not present on this machine; the
  canary test machine-checks the observable consequences regardless.

### Accounting note

The first authenticated probes confirmed `total_cost_usd` IS populated under
subscription billing (protocol §3.6 asked this to be verified on first run).
Token-based reconstruction at list prices is still recorded alongside the
reported number for every invocation, per BUILD_BRIEF Section 5.

---

## D2 — Single-whole-payload fence stripping in sentinel output parsing

**Date:** 2026-06-10 (author-approved). **Affects:** parsing of compile and
judge outputs in `sentinel/compile.py` / `sentinel/judge.py`.

**Evidence:** both attempts of the first live `make smoke` compile (task a1,
Sonnet 4.6, CLI 2.1.170) returned an otherwise schema-valid TripwireSet wrapped
in a ```` ```json ```` fence, despite the frozen prompt's explicit "No prose,
no markdown fences". Under strict parsing the pre-registered one-retry budget
is consumed by a transport wrapper and compile fails ~100% of the time,
dead-ending the pilot on a formatting technicality that KG0's rubric
(observable/parameterized/actionable/calibrated) does not measure.

**Policy (one policy for both sentinel calls, compile and judge):**
- Exactly one whole-payload markdown fence (```` ``` ```` or ```` ```json ````
  wrapping the entire output) is stripped before DSL/verdict validation.
- The boundary is the fence and nothing else: no trailing-comma repair, no
  quote fixes, no partial-JSON salvage, ever. Prose around the JSON, multiple
  blocks, or anything else remains schema-invalid and consumes the retry.
- Every strip is recorded per attempt as `fences_stripped` in the compile /
  judge_verdict trace event. Phase 0 reporting includes the fence rate as a
  descriptive format-compliance statistic.

---

## D3 — `contradicts_assumption` matcher semantics (DSL clarification)

**Date:** 2026-06-10 (author decision, recorded before the C-archetype runs).
**Affects:** `world` middleware matcher only; the frozen DSL text is unchanged.

A tripwire whose ONLY predicate is `contradicts_assumption` is
**touch-triggered**: any response from the monitored retrieval source (the
signal's type/method/url_pattern gates) fires a WARNING escalation to the
judge, deduplicated per (tripwire, resource). Pure predicate matching stays
pure — the middleware never evaluates whether content actually contradicts the
assumption; that semantic comparison is exactly the judge tier's job. When
`contradicts_assumption` is combined with other predicates, the other
predicates decide the match as usual.

---

## D4 — Phase 0 scoring assistance (mechanized + external first-pass rating)

**Date:** 2026-06-10 (author decision, before any KG0 scoring).
**Affects:** how the protocol 6.4 rubric is applied; thresholds unchanged.

KG0 scoring decomposes per rubric property:

- **observable** — mechanized: the matcher itself decides whether the signal
  is evaluable (predicates well-formed and concrete; url_pattern actually
  glob-matches the world's path space). No judgment involved.
- **parameterized, actionable, calibrated** — first-pass rated by an
  **external cross-vendor model (GPT-5.5 Pro), not Claude-family**, so the
  compiler's own model family never grades its own output. The rater receives
  a blind package (`runs/phase0/gpt_audit_package.md`): plans, assumptions,
  and compiled tripwires only — no scores, no injection specs, no KG0
  thresholds. The author's hand audit remains authoritative; the external
  pass is a first-pass and disagreements are resolved by hand.
  **Amended (2026-06-10):** a second cross-vendor rating (Gemini) was added;
  authority now rests with **inter-rater agreement plus author adjudication
  of disputed bits** (the hand-audit clause is retired). Process:
  deterministic task-id normalization, 144-bit agreement, per-bit author
  adjudication under a stated principle, consensus merge. Record committed
  under `decisions/`.
- **would-catch** (KG0 second clause) — empirical, not on-paper judgment: each
  planned (task, injection) pair is simulated against the armed compiled set
  in the real world server, and "caught" means a fresh tripwire fire after
  the injection (`runs/phase0/would_catch.csv`).

KG0 arithmetic is computed by `python -m analysis.phase0_audit kg0` once the
external CSV is merged; the 70% / 80% thresholds live in the analysis code
and this repo, never in the exported rater package.

---

## D5 — `url_pattern` matching: static glob-or-regex classification

**Date:** 2026-06-10 (author-approved with conditions).
**Affects:** the middleware matcher's url_pattern gate; frozen DSL unchanged.

**Evidence:** the DSL comment says url_pattern is a "glob over world-server
paths", but comments do not survive into `model_json_schema()`, so the frozen
compile prompt gives the model no way to know glob was intended. Both live S5
runs compiled regex-style patterns (`.*/pricing/.*`, `.*/inventory/items$`);
under pure glob every gate is dead and S5 cannot detect anything — the
architecture would die on an interface ambiguity rather than a measured
failure.

**Exact classification rule (deterministic, decided once at arm time):**
1. If the pattern glob-matches (`fnmatchcase`) at least one path in the
   committed canonical sample `world.server.PATH_SAMPLES`, its dialect is
   **glob**. Glob takes precedence: a pattern valid under both dialects is
   treated as glob, full stop.
2. Otherwise, if it compiles as a regex and `re.search`-matches at least one
   sample path, its dialect is **regex**.
3. Otherwise it is **dead** and never matches any request.

The dialect is recorded per tripwire at **arm time**: `/admin/arm_tripwires`
returns `pattern_modes` and the conductor writes them into the tripwire_set
trace event (`url_match_modes`); each tripwire_fire additionally carries
`url_match_mode`. Phase 0's mechanized observable bit uses the identical
classifier (dead patterns score observable=0).

**Finding for the paper:** this is the second schema-transmission gap
alongside D2 (fences) — constraints expressed only in frozen prose or code
comments do not reach the compiler model. DSL v2 in the full study moves such
constraints into schema-visible `Field` descriptions.

---

## D6 — Phase 0 recompile under production-fidelity task context

**Date:** 2026-06-10 (author-ordered sequencing, pre-committed before any
recompile ran).

**Sequencing rules (verbatim from the author's ruling):** the lean-context
would-catch result (6/9, 67%) stands in the record as the lean-context
datapoint; the lean sets are NOT sent for external rating. The rich-context
recompile is the official KG0 coverage measurement. If it clears 80%, the new
gpt_audit_package is exported for external rating; if it fails, the single
KG0-permitted prompt-iteration is on the table and the author decides its
content.

**Independence evidence (why the context amendment is not data-driven
tuning):** the endpoint-inventory amendment originated from the live S5
endpoint-invention bug, observed BEFORE any would-catch number existed:
- The S1 live run (`runs/a1-S1-endpoint_404-s1`, after commit 4d61229) shows
  the orchestrator inventing `/pricing/prices` — its redo subtask reads "The
  endpoint /pricing/prices returned 404".
- The second S5 live run shows workers receiving FastAPI's default
  `{"detail": "Not Found"}` (unknown-route 404s), not the deprecation body —
  i.e. calls to endpoints that never existed.
- The would-catch harness and its first numbers (44% with simulation bugs,
  then 67%) were produced after those observations, in commit 77fb03a.

**Mechanical, blind enrichment:** `world/surface.py` (committed) derives, for
every world service a plan touches (rule: the service's route prefix appears
verbatim in the goal/plan text), its surface verbatim from the world server's
own OpenAPI spec, plus the corpus index (passage ids/titles) when the document
store is touched. One identical rule for all four plans; no reference to
injection specs anywhere; plans, assumption lists, and all other compile
inputs stay byte-identical to the lean versions; the frozen compile prompt is
untouched. The conductor uses the same enrichment for production runs.

---

## D7 — NOISE interrupt policy: evidence-scoped re-judgment dedup

**Date:** 2026-06-10 (author design decision).
**Affects:** conductor escalation handling; matcher unchanged except
accounting.

**Post-mortem that motivated it (live S5 run 3):** three concurrent fires of
one ungated tripwire were correctly judged NOISE, but the orchestrator had
hardcoded `X-Worker-Id: w1` into subtask text, so redispatched workers
presented stale identities, were 409'd by stale tripped flags carrying the
original control, and re-escalated the same adjudicated noise 12 times (zero
fresh fires; 16 worker_noncompliance events; run died by escalation_loop,
$0.56). Fixes shipped alongside this policy: NOISE redispatch forgives the
worker lineage via /admin/clear_tripped, and the orchestrator prompt forbids
hardcoding header values.

**Policy:** a `(tripwire_id, evidence_hash)` pair is never re-judged, where
`evidence_hash` is a canonical SHA-256 over the VALUES of the tripwire's
declared `evidence_fields` (whole evidence object when the armed tripwire is
unknown). The same tripwire firing with materially different evidence gets a
fresh judgment. Every escalation eaten by the dedup, and every
matcher-suppressed match, is emitted as a `suppressed_refire` trace event
(`where: conductor` / `where: matcher`) so metrics can count exactly what the
policy ate. Matcher-level suppression still applies within one armed epoch
after a NOISE verdict; re-arming (replan recompile) resets it.

**Parked (build only on recurrence):** if the orchestrator ever again leaks
identity content into subtask text despite the prompt rule, escalate to
unforgeable identity — a per-worker secret header value generated by the
conductor, present only in that worker's rendered system prompt, mapped to
worker id by middleware. Not built preemptively.

---

## D9 — Evidence resolution: alias table, excerpt floor, all-null hash fallback

**Date:** 2026-06-10 (author-confirmed item by item).
**Affects:** `build_control` in the world middleware and the D7 evidence hash.

**Evidence:** live S5 attempt 4 — compiled `evidence_fields` named real
observables under other spellings (`status_code`, `response_body`, `sku`);
the literal resolver produced all-null evidence and the judge correctly ruled
every escalation NOISE, including the genuine 404.

**(a) Alias table** — committed fixed artifact (`world.server._EVIDENCE_ALIASES`),
exact mapping:

| evidence_field spelling (case-insensitive, leading `/`/`_` stripped) | resolves to |
|---|---|
| status, status_code, http_status, code, response_status | response status |
| path, url, endpoint, request_url | request path |
| method, http_method | request method |
| counter | global tool-call counter |
| body, response_body, raw_response, response, raw_response_body, passage_content, content | full parsed response body |
| anything else | JSON-pointer lookup into the body (D8 dialects); null if unresolvable |

**(b) Excerpt floor** — every control's evidence additionally carries
`_status`, `_path`, and `_response_excerpt` (the serialized response body,
hard-capped at **600 UTF-8 bytes**, `world.server.EXCERPT_CAP_BYTES`), because
the frozen judge prompt promises "actual tool response excerpts".

**(c) All-null hash fallback** — when every declared evidence field resolves
to null, the D7 hash falls back to the whole evidence object (which includes
the floor), so a pre-injection all-null NOISE can never suppress a
post-injection all-null GENUINE. Regression-tested. Resolved declared fields
keep governing materiality: floor variance does not split otherwise-identical
evidence.

---

## D10 — Worker final-message reader (four tiers, unique-candidate rule)

**Date:** 2026-06-10 (author-ratified with tightening).
**Affects:** conductor-side parsing of worker final messages only. D2's
strict boundary for compile and judge outputs is untouched.

**Evidence:** live S5 attempt 5 — workers escalated with correct tripwire ids
and real evidence but wrapped the JSON in prose plus a fenced block
("I've detected a tripwire_control ... ```json {...}```"); strict parsing
classified them invalid_output and the escalation flow never started.

**Policy:** the reader collects ALL schema-validating candidates — a JSON
object whose `status` is `escalated`, `done`, or `blocked` — across four
tiers: **exact** (whole message), **fence** (one whole-payload fence),
**embedded_fence** (fenced block inside prose), **embedded_object** (raw JSON
object inside prose). Identical candidates found by several tiers count once
(first tier's label is recorded as `output_parse` on worker_end, keeping
worker.md format compliance measurable). **More than one non-identical
candidate is invalid_output** — first-match-wins could grab a JSON object
merely quoted inside prose instead of the real payload. Regression-tested
with a two-distinct-candidates message.

---

## D11 — Per-tripwire consecutive-NOISE cooldown (interrupt-policy gating)

**Date:** 2026-06-10 (author-ordered; required before further live S5 runs).
**Affects:** conductor escalation handling + world matcher; replaces the
earlier suppress-on-first-NOISE shortcut. The escalation backstop (52) is a
hard safety ceiling only, never the operating mechanism.

**Evidence (live S5 attempt 6 grind):** one compile produced five ungated
tripwires; every worker lane's first /auth/token call tripped one, and per
ratified D7 each lane's evidence was materially different (unique token
values), so each recurrence was judged fresh — 12 correct NOISE verdicts and
the escalation budget burned before the noise drained ($0.49, no replan).

**Policy:**
1. After **K=2 consecutive NOISE VERDICTS** on the same tripwire it enters
   cooldown: further matches emit `suppressed_refire` (`where: cooldown`)
   with no control embedded and no judge call.
   *Considered and rejected (author veto):* counting D7-deduped recurrences
   of already-NOISE'd evidence toward the streak. Rationale: D7 already
   makes identical-evidence loops nearly free (deduped without a judge
   call), so they need no cooldown; D11 exists for distinct-evidence noise,
   which verdicts-only counting handles. Counting recurrences would enter
   cooldown after a single verdict and eat novel same-status-class evidence
   for near-zero savings. The escalation ceiling (52) remains the hard stop
   for pathological identical-evidence churn.
2. Exit conditions: a match whose evidence differs in status-class from EVERY
   NOISE'd instance (different `_status`, or any declared field transitioning
   null<->non-null) exits the cooldown and is treated as a normal fire; a
   replan's fresh tripwire set resets all cooldowns and streaks.
3. Every cooldown suppression is logged (`suppressed_refire`/`cooldown`), so
   judge-cost savings and any missed detections stay measurable. If cooldown
   ever eats a genuine fire, KG1 is the honest place that shows it; that
   exposure is not pre-softened.

**Protocol link:** this is the minimal instance of protocol Section 5.1's
hierarchical gating — S5's severity/scope routing presumes escalation volume
is shaped before the judge tier, not amplified by retry loops.

**Paper finding:** high-entropy evidence (volatile values such as per-call
tokens inside `response_body`) interacts with D7 evidence-freshness to defeat
identity-level dedup entirely; evidence-class cooldown is the consistent
middle ground between re-judging everything and suppressing forever.

---

## D13 — Derived path samples (instrument repair, authorized post-KG0)

**Date:** 2026-06-10 (author-authorized AFTER the KG0 verdict; the verdict's
as-measured numbers are unchanged and remain the verdict basis).

**Defect:** the D5 classification sample was hand-curated and omitted three
real paths (`/docs/passages/ven-terms`, `/docs/passages/pol-pricing`,
`/repo/files/README.md`), so three exact-path tripwires were misclassified
dead — false negatives in the mechanized observable bit AND a latent
live-matcher detection loss (those tripwires could never match in runs).

**Repair:** `world.server.get_path_samples()` derives the sample mechanically
from the world's own fixtures — routes from the OpenAPI spec, `{sku}`
instantiated from the catalog, `{passage_id}` from the corpus index, `{path}`
from the fixture repo tree. No hand-listing. The live-matcher fix applies
prospectively, closing the detection loss before Phase 1.

**Both-numbers rule:** the KG0 record reports 38/48 = 79% as-measured (the
verdict basis, unchanged) and the instrument-corrected figure as a footnote;
dialect classification and the empirical would-catch are re-run under the
corrected samples with any delta reported the same way. See
`decisions/kg0_verdict.md`.

---

## D14 — order_violation key vocabulary: known limitation (fifth gap)

**Date:** 2026-06-10 (author ruling).

The three remaining mechanized-observable zeros are honest zeros, but
reclassified: the compiled `order_violation` predicates used invented keys
(`must_precede`, `all_of`, prose constraints) because the expected
`required_before`/`observed` vocabulary lived only in a frozen code comment —
the **fifth schema-transmission instance** alongside D2 (fences), D5 (glob
dialect), D8 (pointer dialect), and D9 (evidence-field spellings). Unlike the
pointer dialects there is NO small verified set of spellings, so invented
order keys are NOT normalized. Recorded as a known limitation; DSL v2 moves
the vocabulary into the schema.

---

## D15 — Result carryover across replans (uniform replan semantics)

**Date:** 2026-06-10 (author pre-approved conditional on: demonstrated M4
recurrence, uniformity across every replanning system including S1's redo
path, and landing before any Phase 1 run — all three hold).

**Recurrence evidence (M4 acceptance):** post-replan data loss recurred in
every replanning system — S2's final aggregate consumed nothing (used=[],
all six worker instances discarded, empty report); S3 carried w1/w3 forward
but lost the replanned pricing work; S5 attempt 7 lost w1/w3's data after a
pricing-only replan.

**Mechanism (uniform):** at every replan decision the orchestrator message
includes `completed_results` — each done worker's output — and the
orchestrator is instructed to scope replacement steps to only what is
missing or invalidated, never re-request carried data, and embed
already-gathered values into replacement subtasks where needed. Applies to
S5 judged interrupts, S2/S4 unjudged interrupts, and S3 revalidation
replans; S1's redo path already receives all results via the aggregate
message, so the whole matrix shares one replan semantics. Landed before any
Phase 1 run.

---

## D8 — JSON pointer dialect normalization (third schema-transmission gap)

**Date:** 2026-06-10 (flagged for author veto, same class as D2/D5).
**Affects:** `_pointer_lookup` in the matcher and evidence resolver; frozen
DSL unchanged.

**Evidence:** the rich-context d1 compile expressed every pointer in
JSONPath dialect (`$.checks_run`, `$.package_id`, `$.status`); the DSL
comment says "JSON pointer" but, as with D2 (fences) and D5 (glob vs regex),
the frozen prompt cannot transmit the dialect. Unresolvable pointers made
`field_absent` predicates fire spuriously on healthy traffic and erased
genuine post-injection fires from the would-catch differential (d1
gate_skip_trap and endpoint_404 were measured as misses purely from this).

**Policy:** `_pointer_lookup` deterministically accepts three spellings of
the same observable: RFC6901 (`/a/b`), dotted (`a.b`), and JSONPath-prefixed
(`$.a.b`; bare `$` is the body root). No other JSONPath features (filters,
wildcards, slices) are interpreted — those remain unresolvable. Finding for
the paper alongside D2/D5; DSL v2 carries the dialect in schema-visible
Field descriptions.

---

## D16 — Success checkers for b1/c1/d1 (night-0 build gap + test gap)

**Date:** 2026-06-10 (author ruling on night-0 candidate deviation CD-1).

**Evidence:** night 0 enqueued 13 jobs; the 9 b1/c1/d1 jobs all completed
their agent runs and crashed at the checker step with
`FileNotFoundError: tasks/checkers/{b1,c1,d1}.py` — only `a1.py` existed
(the b/c/d yamls said "checker lands with the archetype runs" and never
did). The 76-test suite was green because nothing asserted an existing
checker per task yaml: a build gap and a test gap.

**Mechanism (blind construction rule):** the three checkers derive every
constant from their task yamls at the frozen commit and clone `a1.py`'s
structure (`check(final_report, ground_truth) -> (bool, detail)`); `b1.py`
derives its pre-migration baseline (preserved key value, originally
annotated files) at import time from the world's authored fixtures
(`world.state.REPO_FILES`). Nothing in checker logic originates from
night-0 traces, which were not read during construction. The files are
presented to the author as a derivation diff against their yamls BEFORE any
evaluation runs; after author review, retroactive evaluation over night-0's
preserved final aggregates is ADMISSIBLE (checkers are deterministic
functions of outputs already on disk) and completes the manipulation table
at $0. Night-0 outputs become test fixtures only AFTER their verdicts are
recorded. `tests/test_checkers.py` closes the test gap: every task yaml
must declare an existing, loadable checker that passes ground-truth-derived
smoke fixtures and rejects empty/non-dict reports.

**Limitations (recorded a priori):** c1's premise probes are substring
heuristics derived from yaml assumption a1 ("30-day returns, three
operational warehouses, weekly restocking") — they catch
premise-contradicting briefs at a paraphrase false-negative risk; c1/d1
check `package_id` as a non-empty string only (no world-side registry
cross-check).

**Review record (2026-06-10, checkers APPROVED):** commit-pinned contents
(`git show` at de4de5d) supplied by the author to two independent
cross-vendor reviewers with fresh context and no night-0 trace exposure;
three-pass audit plus a test-fixture timing check. Reviewer A (Claude):
CLEAN on all four files. Reviewer B (Codex): CLEAN on c1; three findings on
b1/d1, all adjudicated NON-DEFECTS by the author under the stated
principle — contamination is a data-flow property (no operative value may
originate from run outputs), not a lexical one; count fidelity means every
code condition maps to a declared table row and vice versa, not that
atomization granularity matches. Adjudications: (1) b1 "11 vs 10" — the
unknown-file rejection is the second clause of the declared files_changed
row ("each must exist in post-run repo_files"); disclosed derived
condition, value-free. (2) b1 docstring phrase — the provenance attestation
DENYING run-output use; lexical false positive, no data flow. (3) d1 "8 vs
6" — atomization granularity; all conditions yaml-defensible per the
reviewer's own note. Both reviewers concur on every substantive axis:
skeletons clone a1; ORIGINAL_VALUE and baselines computed from fixtures,
nothing hardcoded; zero unsourced operative literals; no contradiction
values in c1; checks_run > 0 present in d1; test fixtures synthetic or
fixture-derived only. The exact bytes both reviewers audited are committed
as `decisions/d16_review_package.txt` (sha256
1f3a6de772f44f2c2e3c73057eff23572b5ef29b7187c4810702ef98898c03ef).

**Probe tolerance finalization (a priori, pre-evaluation):** by author
ruling after review and BEFORE any evaluation run, with no trace consulted:
all c1 probes are case-insensitive, and the returns probe accepts "30" or
"thirty". Once retroactive verdicts exist, the probes are frozen.

**Retroactive evaluation protocol (b1 parity):** the retroactive checker
must consume what a live checker would have — the end-of-run ground-truth
snapshot. For a1/c1/d1 the consumed ground truth is seed-deterministic or
key-only (passage ids are not mutated by any injection). For b1 the checker
consumes post-run repo_files, which workers mutate: the snapshot is
deterministically reconstructed by replaying the run's trace (every
successful PUT /repo/files/{path} in counter order, plus the repo_config
drift mutation at its recorded injection counter) from the authored
fixtures, and the reconstruction must be validated against every GET
/repo/files response in the same trace. Any b1 run where this parity
cannot be demonstrated stays UNRESOLVED — stop and report, no substitute
inputs.

---

## D17 — n_inject from n=3 clean medians; failed-checker clean runs stand

**Date:** 2026-06-10 (author rulings 3 and 5 on the night-0 report).

**Rulings:** per-task n_inject is NOT fixed from night-0's n=1 clean
samples. The 8 remaining S1 clean cells (a1/b1/c1/d1 x seeds 2,3 — matrix
cells regardless) run first; per-task n_inject is then fixed from the n=3
medians under the frozen 50%-of-median rule (protocol 5.2). CD-2 ruling:
the a1 seed-1 clean run STANDS as a matrix cell with its failed-checker
outcome ("final report is not a JSON object") — batch flakes are data, not
do-overs — and its 18-call trajectory is a valid median input; a terminal
formatting flake does not alter trajectory length. The same rule applies to
any clean run whose checker fails.

**Cell accounting (explicit):** night-0's 4 clean runs bank as S1/seed-1
matrix cells. Night-0's 9 injected runs are calibration-only (fired at
provisional n_inject=8, not final per-task values): no injected cell banks
from night 0, favorable or not. Once n_inject is fixed and the D18/D19
redesigns land, all 9 manipulation checks re-run (S1, seed 1) under final
parameters; the table must be all-QUALIFIED before any other matrix cell
runs, and those spec-identical re-runs bank as the S1/seed-1 injected
cells. (Amended by D20: the a1/c1/d1 seed-1 clean cells were voided as
class-(iv) coercions and re-ran under the repaired reader.)

**Fraction-resolution rule (author, pre-committed 2026-06-10 BEFORE median
computation):** if 50%-of-median lands on a fraction, n_inject = floor
(round DOWN, toward earlier injection). Rationale, recorded with the rule:
the known failure mode is tail-firing (CD-4); erring earlier only
lengthens the post-injection runway and never weakens the manipulation.
A-priori status: committed after the 11 clean-cell runs drained but before
any median was computed or any trajectory length inspected — the medians
did not exist when this rule was fixed, and it is applied mechanically
(no stop if a fraction bites). A-priori status ACCEPTED by author ruling
despite one discarded computation: that computation ran over void rows
(the D21 zero-call empty runs) and carried zero informational content
about real medians.

---

## D18 — schema_drift(pricing) redesign: non-self-describing rename

**Date:** 2026-06-10 (author ruling 4; manipulation verdicts under the
frozen rule, letter intact — the qualification rule is NOT amended).

**Evidence:** night-0 manipulation check a1+schema_drift NOT QUALIFIED —
checker passed with no redo (24 tool calls vs clean 18). The drifted
payload (`price_cents` plus unchanged-currency context) self-described the
remap, so the batch absorbed the rename without replanning: a drift the
batch shrugs off was never a manipulation.

**Mechanism:** the pricing arm now serves
`{"sku", "price": <integer cents>, "currency": "USD"}` — the rename target
(`price`) no longer self-describes the silent dollars-to-cents unit change,
so a naive remap corrupts every consumed unit_price by 100x and the checker
catches it. The repo_config arm is unchanged (its drift already breaks the
validate gate's reference check). Re-qualification happens in the D17
manipulation re-runs.

---

## D19 — token_expiry redesign: hard expiry (issuance suspended)

**Date:** 2026-06-10 (author ruling 4).

**Evidence:** night-0 manipulation check a1+token_expiry NOT QUALIFIED as
frozen — workers self-recovered by re-calling POST /auth/token after the
401s, burning 44 tool calls vs clean 18 (2.4x) with a passing checker and
no redo. RECORDED NIGHT-0 FINDING (author): silent-recovery waste is real
and thesis-relevant; candidate exploratory arm outside the primary table.

**Mechanism:** token_expiry now revokes all active tokens AND sets
`auth_locked`: POST /auth/token thereafter returns 401
(`token_issuance_suspended`), so the refresh path fails too and recovery
requires an orchestrator-level replan, never a silent worker retry. The
redesign is type-level and therefore also applies to c1+token_expiry.
Re-qualification happens in the D17 manipulation re-runs.

---

## D20 — Strict orchestrator reply reader (harness defect: silently
## swallowed redo requests)

**Date:** 2026-06-10 (author reader ruling on the night-0 flake diagnosis).

**Evidence (four swallowed redo requests):** every night-0 "flaked" final —
a1/c1/d1 clean and b1+schema_drift — was the SAME mechanism and none of the
anticipated transport classes: the orchestrator answered aggregate mode
with a valid plan-shaped JSON redo request (`plan_id/revision/steps/
aggregation`; one arrived fenced and the D2 strip handled it cleanly).
`AggregateReply`'s all-default fields plus pydantic's extras-ignoring
validation coerced each to an empty reply (`final_report=None, redo=[]`):
the redo was silently discarded, no redispatch happened, and the checker
saw None. Author classification: harness defect, not agent behavior. This
is the sixth schema-transmission gap (D2 fences, D5 globs, D8 pointer
dialect, D14 vocabulary), compounded by permissive return-path validation.

**Mechanism (uniform across all five systems):**
1. Every orchestrator reply schema (`Plan`, `PlanStep`, `AggregateReply`,
   `Dismiss`, and the previously unmodeled S3 `Continue`) carries
   `extra="forbid"` and each turn must parse as exactly one sanctioned
   shape (plan: Plan; interrupt: Dismiss XOR Plan; revalidate: Continue
   XOR Plan; aggregate: AggregateReply). An aggregate reply coercing to
   empty (no final_report, no redo) is REJECTED; final_report null is
   accepted only with a non-empty redo when redo was permitted.
2. On rejection the conductor re-prompts with one fixed template, sent as
   `{"mode": <same mode>, "schema_error": <rendered template>}`, recorded
   verbatim here (the {violation} and {schema} slots carry the validator
   message and the per-mode schema restatement from
   `conductor/run_one.py::*_SCHEMA_STR`):

   "SCHEMA ERROR: your previous reply did not match the required schema and
   was rejected. Violation: {violation}. Reply again with a SINGLE JSON
   object matching exactly this schema and nothing else - no extra keys,
   no markdown fences, no prose, and no other shape (a plan is NOT
   accepted unless the schema below says so): {schema}"

   Max 2 re-prompts; then the run FAILS LOUDLY with reason
   `reply_schema_violation`. No silent path exists.
3. Every rejection is a first-class `reply_rejected` trace event (mode,
   attempt, violation, reply keys) and every re-prompt turn carries
   `schema_reprompt: <n>` in its orchestrator event — per-system
   dialect-error rates and re-prompt costs are measurable from traces.
4. NO semantic translation: plan-dialect replies are never converted into
   redos (order_violation precedent, D14). Frozen prompts untouched; the
   permitted prompt-iteration remains unspent.

**Finding-1 corollary (recorded for the paper):** schema constraints must
be schema-visible inbound, and validation must be strict on the return
path — permissive validation does not tolerate dialect drift, it masks it
as silent data loss. The four swallowed redo requests above are the
evidence: four orchestrators correctly detected incomplete work and asked
to fix it, and the harness threw the requests away while reporting
`valid=True`.

**Banked-cell voiding (mechanical criterion, never outcome-based):** any
banked cell whose final reply was class-(iv) coerced — identifiable from
trace flags — is VOIDED and re-runs under the repaired reader; old traces
are preserved and nothing is silently replaced. By this criterion the
a1/c1/d1 seed-1 clean cells are VOIDED and re-run; b1 seed-1 clean is
unaffected and stands. This supersedes D17's flakes-stand clause for
class-(iv) cells only — D17's premise (agent formatting flake) was
falsified by the diagnosis; genuinely flaky outputs still stand as data.
Night-0 injected runs remain calibration-only; b1+schema_drift's QUALIFIED
stays a calibration reading with its attribution note, final word to the
re-run.

---

## D21 — Windows launcher trap: cmd shims truncate multiline arguments
## (binary invocation override + two permanent catches)

**Date:** 2026-06-10 (author ruling on the launcher-trap diagnosis).

**Evidence (full diagnosis chain):**
1. All 11 clean cells of the first post-D20 calibration phase came back
   "done" with ZERO tool calls, no success_check event, $0 recorded cost,
   and near-constant ~12.5 s wall — every trace held exactly
   run_start/plan/error/run_end, the plan event showing valid=false,
   error "empty reply", exit_code 0, empty stderr, and no result envelope
   (num_turns null).
2. The live canary (haiku, single-line system prompt) PASSED after the
   failures, and direct pong probes through the production run_claude
   recipe passed on BOTH haiku and sonnet — the basic invocation path was
   healthy.
3. An exact orchestrator-shaped probe (the real multiline orchestrator.md
   system prompt, JSON stdin) reproduced the failure: exit 0 and RAW PROSE
   on stdout ("I'm now in plan mode...") with no JSON envelope — the
   default-persona CLI answering as if --system-prompt, --output-format,
   and --tools were never passed.
4. `shutil.which("claude")` resolved to the npm-created `claude.CMD` shim
   (created by the D-ruled 2.1.170 reinstall), shadowing the native
   `~\.local\bin\claude.exe` that night-0 actually ran (and which the
   auto-updater had moved to 2.1.172). cmd.exe truncates a command line at
   the first NEWLINE, so any multiline argument silently destroys every
   flag after it, while single-line invocations (`--version`, the canary)
   pass through untouched — the version guard and the full 97-test suite
   were structurally blind to this class.
5. Fix verified: invoking the npm package's real binary
   (`...\@anthropic-ai\claude-code\bin\claude.exe`) directly via the
   conductor's TRIPWIRE_CLAUDE_BIN override returns a valid Plan envelope
   (1 turn, cost reported).

**Cost record:** ~11 truncated-prompt sonnet generations went unrecorded
(no envelope, est. < $0.20); queue jobs 14-24 are the operational record
(zero-call "done" rows, reason orchestrator_invalid). Their first median
computation was discarded as void (see D17 fraction-rule note).

**Mechanism (permanent):**
1. The conductor is launched with TRIPWIRE_CLAUDE_BIN pointed at a real
   executable, never a .cmd shim (RUNBOOK records the export). This
   changes how every future run invokes the binary.
2. **Launcher preflight guard** beside the version guard: at every
   supervisor start, one orchestrator-shaped live probe (haiku, MULTILINE
   system prompt, --output-format json) must return a parseable result
   envelope; no envelope means the launcher is mangling multiline
   arguments and the queue HALTS before claiming any job. The single-line
   canary is shim-transparent and proved blind to this class.
3. **Void-run invariant** (permanent queue invariant, not a one-off
   scan): a runner summary whose run directory shows zero tool calls AND
   no success_check event is never accepted as done — the job is marked
   failed (error void_run) with run_dir and cost persisted per CD-3.


## D22 — CANDIDATE (report-only, archaeology v2): trace request-body decode is lossy for invalid UTF-8

**Date:** 2026-06-12 (found during the Phase 0 byte-identity replay of the
archaeology-v2 battery; reported per the standing instrument-vs-system
boundary — NO repair performed; the author rules on disposition).

**Evidence:** `WorldMiddleware._respond` records `tool_call.body` as
`_parse_json(raw)`, which falls back to `raw.decode("utf-8",
errors="replace")` when the bytes are not valid JSON/UTF-8. The original
request bytes are therefore unrecoverable from the trace whenever a worker
emits invalid UTF-8. One instance exists in the banked matrix:
d1-S5-endpoint_404-s1 counter 31 (POST /docs/validate) — the live router
rejected the malformed bytes with 400 ("error parsing the body") while the
re-encoded trace string parses cleanly (replay returns 200). Detail:
runs/archaeology_v2/replay_check.json (LOSSY-REQ exclusion class);
analysis/replay_check.py header documents the class.

**Scope:** request-side only. The matcher consumes RESPONSE tuples
(method, path, status, body), which replay byte-identically 27/27 across
all injected S5 cells, so no matcher verdict, metric, or gate quantity is
affected. Impact is limited to byte-exact replay/audit of malformed
worker requests (artifact-evaluation fidelity).

**Proposed remediation (for the author; NOT applied):** record a base64
`body_raw` alongside the parsed body when `_parse_json` falls back to
lossy decoding.
