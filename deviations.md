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
