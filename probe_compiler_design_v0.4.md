# Sentinel Protocol v2 — Probe Compiler Design (v0.4, LOCKED for build)

**Status:** Design of record for the v2 probe-compiler build window. Supersedes the
v0.3 draft (project-root `probe_compiler_design_v0.3.md`). Compiler-INTERNAL design
remains settable during the build; the clauses below marked **[design-of-record]**
are locked by author ruling for this session, and items marked **[GATE-Δ]** amend the
frozen prereg_1b (6c8cc47) and are entered as numbered deviations (deviations.md),
never edited silently. **Rule Zero:** every clause is general — derived from the
pre-holdout 8-category ontology and the plan's own surfaces only. No
category-specific probe types, templates, or heuristics anywhere.

---

## Amendment log (v0.3 → v0.4)

Folded in this session (all pre-data, blind to any v2 measured outcome):

- **A1 (Break-A fix, §2.1/§2).** The §2.1 typing rule governs the **baseline-drift
  path ONLY**. Compiled hard invariants (§2(i)) fire **on their own**, with no
  typing gate — a gate that was enforcing-then-off from the very first observation
  is caught by the compiled hard invariant, not by drift-from-a-baseline (there is
  no clean "on" baseline to drift from). See §2, §2.1.
- **A2 (new fault-shapes + primitives, §2.1).** Add two general fault-shapes with
  matching executor primitives — **ORDER/SEQUENCE changed** on a stationary surface
  (order-sensitive read: position-pinned read or sub-array hash) and
  **RELATIONAL/JOIN broken** (a relation across surfaces; **exempt from
  transition-typing** because it has no single-surface baseline). Plus **FIELD-ADDED
  on a value-watched surface** is made interrupt-eligible (see the count-reconciliation
  note below). See §2.1, §1.1.
- **A3 (§0 honesty).** Typed-drift trades **bounded recall** for noise protection —
  NOT "costs nothing" as v0.3 §0 claimed. The bound is minimized (not removed) by
  the new shapes in A2. See §0.
- **A4 (Break-E fix, §2 obligation 3).** "**Stationary**" = **no concurrent worker is
  planned to write the surface** per the *global* planned write-set, not merely "this
  plan-step doesn't write it." The emergent-write residual (a worker writing a surface
  no plan step declared) is a named limit. See §2, §3.3, §8.
- **A5 (Break-G fix, §6).** Replan/recompile cost is **booked against whichever run it
  occurs on**, including counting toward the clean-run ≤12% overhead cap when the
  replan happens on a clean run. See §6.
- **A6 (§3.1 predicate rewrite).** The attachment predicate is "**the assumption's
  truth is NOT carried by the surface's ordinary worker-visible traffic**" — replacing
  v0.3's "self-announcing by signal shape", which conflicted with §3.2. See §3.1.

Plus two **author rulings** (D1, D2) recorded as design-of-record, and two **[GATE-Δ]**
deviations (D25, D26). See the two sections immediately below.

### Count-reconciliation note (FLAGGED FOR AUTHOR)

Amendment A2's prose adds three items (ORDER, RELATIONAL, FIELD-ADDED) to v0.3's four
shapes, which would read as **seven**; the build brief (§11.9 build order B2) names
"**the 6 general shapes**." Resolution adopted for this build, to honour both: the
**enum has six members** — `FIELD_ABSENT, STATUS_CLASS, SCHEMA_SHAPE, VALUE_CHANGED,
ORDER_CHANGED, RELATION_BROKEN` — and **FIELD-ADDED is detected as a `SCHEMA_SHAPE`
instantiation** (an added `{key:type}` pair), with the v0.4 nuance that a *value-watched*
probe also carries a shape fingerprint so an added sibling field still instantiates a
shape change rather than being silently missed by a single-field value read. If the
author prefers FIELD_ADDED as a distinct seventh member, it is a one-line enum addition;
recorded as an open reconciliation, not a silent choice.

---

## Author rulings (design of record, this session)

### Ruling D1 — §4 gate route is a no-write wrapper with a non-perturbation trapdoor

Build the §4 gate re-read as a **thin no-write wrapper over the REAL enforcement
predicate** (not a `gate_enabled` flag or any status surrogate). The non-perturbation
check is a **HARD TRAPDOOR**: if the route does not pass the three-vector
non-perturbation gate (injection counter / token stream / validation sentinel), the
route is **DISABLED**, and the gate-enforcement assumption is flagged **UNCOVERED
(loud)** and routed to **caution per §5.2** — never silently treated as covered, never
fired under a privileged surrogate. See §4, §5.2, build B5.

### Ruling D2 — replan keeps the inventory (does NOT flush)

On replan, **do not flush** the probe inventory (this overrides v0.3 §6's "flush and
recompile"). Instead: **keep** the prior probe inventory, **recompile-and-add** for the
revised plan, **prune only** probes the N2 pattern-liveness sweep proves dead, and
**instrument every post-replan fire**. No runtime-execution-state architecture change
this phase; the in-flight-dropped probe (a probe whose target is dropped from the plan
mid-flight) is a **named, instrumented residual limit**, not a silent gap. See §6,
build B6.

---

## 0. Invariants and the governing tension

- The probe path runs **no LLM**. Inference happens once, at compile time; runtime probe
  execution is fully deterministic.
- Primitives (built, N5): GET/HEAD over a perturbation-isolated side channel; pointer
  field-read in the matcher's pointer dialect; case-insensitive header read; content
  SHA-256; schema fingerprint = sorted `{key:type}` set (shape-sensitive, value-blind).
  **Added (v0.4, B1):** order-sensitive read (position-pinned read / sub-array hash) and
  relational/join read (a relation evaluated across surfaces).
- Side-channel **non-perturbation** is a hard gate (verified against three vectors: the
  injection counter, the token stream, the validation sentinel).
- **Economics:** clean-run overhead ≤ 12% with probe traffic booked as waste. **(v0.4,
  A5):** replan/recompile cost is booked against the run it occurs on, the clean cap
  included.

**The two-gate tension and its resolution.** Two of our own gates pull opposite ways:
the **probe-validity gate** rewards *auditable* evidence (a clean chain from plan
assumption → compiled invariant → deterministic read → violation), which favours compiled
expectations; the **recall gate** (post-D23) is unpassable without catching change the
design never anticipated, which only drift-from-a-clean-baseline can do generally.

Resolution: **baseline-drift is the general *detection* vehicle, but it *interrupts* only
when it instantiates a general fault-shape (§2.1) or is corroborated by a confirming
probe. Raw, shapeless drift is telemetry, never a raw interrupt.** This keeps recall's
generalization vehicle while protecting the absolute noise caps.

**Honesty (v0.4, A3):** the typing requirement is **not free**. It trades a **bounded**
amount of recall (the shapeless-but-real drift our primitives could not reliably read
anyway) for noise protection. The bound is **minimized — not eliminated —** by the
ORDER/SEQUENCE, RELATIONAL/JOIN, and FIELD-ADDED shapes added in v0.4, which convert
previously-shapeless classes into typed, interrupt-eligible ones.

---

## 1. What a probe is (schema)

`{ method, target, lens, comparison, fault_shape, evidence_class, cost_class, cadence_hint, provenance }`

- **target** — the surface the probe re-reads, in the matcher's pointer dialect, so probe
  and predicate can never disagree on a pointer.
- **lens** — the extraction op and the *slice* it covers (§1.1).
- **comparison** — compiled invariant or proof-obligated baseline (§2).
- **fault_shape** — the general violation type the drift must instantiate to interrupt (§2.1).
- **evidence_class** — status-coded / content-shaped / field-shape / counter, with trust
  priors (field-shape, v1's false-interrupt engine, starts low-trust).
- **provenance** — the dependency chain justifying the probe (§3.3 gate).

### 1.1 Lens / granularity selection

Unit of targeting is the **assumption, not the endpoint**: narrowest slice that covers it.
Structural assumption → schema fingerprint of the relevant sub-object (value-blind).
Specific value → pointer field-read of that field. Whole-payload integrity → content
SHA-256, **only** when the whole payload is genuinely load-bearing (a whole-payload hash
on a one-field assumption fails the *targeted* audit).

**Added (v0.4, A2):**
- **Order/sequence assumption** (a load-bearing array whose ORDER matters: ranking,
  precedence, a sorted/paged window) → **order-sensitive read**: a position-pinned read
  of the element(s) the assumption pins, or a hash of the ordered sub-array. The plain
  schema fingerprint is order-blind (it is a *set*), so a reorder of a load-bearing array
  is missed by the fingerprint and must use this lens.
- **Relational/join assumption** (a relation that must hold *across* two surfaces — e.g.
  every id on surface A resolves on surface B; a foreign-key/coverage/consistency
  relation) → **relational/join read**: read both surfaces and evaluate the relation. This
  has no single-surface clean baseline and is **exempt from the §2.1 transition-typing
  rule** (its fault-shape is the relation predicate failing, evaluated directly).
- **Value-watched surface, field-added** → the value-read lens additionally carries a
  shape fingerprint of the watched object, so a field *appearing* alongside the watched
  value instantiates `SCHEMA_SHAPE` rather than being missed by the single-field read.

---

## 2. Comparison semantics

Two interrupt-grade paths.

**(i) Compiled hard invariant.** Route exists; method allowed; status class; required
field presence/type; gate-enforcement predicate; explicit contract constraints. Auditable
ex ante; used wherever expressible — but only as *hard invariants*, never invented exact
schemas everywhere (that re-creates v1's brittle tripwires). **(v0.4, A1):** the compiled
hard-invariant path **fires on its own** and is **NOT subject to the §2.1 typing rule** —
typing gates only the drift path (ii). This is the Break-A fix: a guarantee that was
violated from the first observation (no clean "on" baseline ever existed) is still caught,
because the compiled invariant does not need a baseline to drift from.

**(ii) Proof-obligated baseline.** A baseline may feed an interrupt only if all five hold:
1. **Clean** — captured before any possible invalidation under the actual trajectory.
2. **Equivalent** — captured via a path observationally equivalent to the worker's view
   (§5.1), not a privileged/stale side view.
3. **Stationary** — over a surface the plan *reads and trusts*, with **no concurrent
   worker planned to write it per the global planned write-set** (§3.3), never one any
   plan-step mutates. **(v0.4, A4 — Break-E fix):** stationarity is a property of the
   *whole plan's* write-set, not the local step; the emergent-write case (a worker writing
   a surface no step declared) is a named residual (§8).
4. **Targeted** — comparison scope is the slice covering the assumption (§1.1).
5. **Frozen** — no rolling update (a rolling baseline launders phase-consistent drift into
   "normal").

**Disqualification.** A baseline failing any obligation is **not interrupt-grade**: logged
as lower-confidence telemetry, counts toward neither strict recall nor a plan interrupt.
(A dirty baseline does not merely miss — it *certifies the mutated world as normal*.)

### 2.1 The typing rule (interrupt gate for the DRIFT path only)

**(v0.4, A1):** this rule gates the **baseline-drift path (2(ii)) ONLY**; compiled hard
invariants (2(i)) and the relational/join read (§1.1) fire without it.

Detected drift interrupts the orchestrator on its own **only when** it instantiates a
*general* fault-shape. Drift that maps to no fault-shape (a shapeless whole-payload
difference) is **telemetry** unless it **persists across a confirming re-observation**, in
which case it is promoted to a **caution-grade** corroborated invalidation (§2.2). The
fault-shape vocabulary is ontology-general; it names no category.

*(v0.4 + D28: the v0.3 "or a second independent probe corroborates it" clause is **dead** —
correlated noise self-corroborates [6/18 false interrupts passed it, two on a clean run;
archaeology_v2 §E.4]. Corroboration is now persistence over time, §2.2.)*

**The six general fault-shapes (enum):**

1. **FIELD_ABSENT** — a present, load-bearing field is now absent.
2. **STATUS_CLASS** — a status moved out of its compiled class.
3. **SCHEMA_SHAPE** — the `{key:type}` set changed (a type flipped, a field removed, or a
   field **added** — the FIELD-ADDED case, including on value-watched surfaces per §1.1).
4. **VALUE_CHANGED** — a read-trusted value changed on a stationary surface.
5. **ORDER_CHANGED** *(new, v0.4)* — the order/sequence of a load-bearing array changed on
   a stationary surface (caught by the order-sensitive read, missed by the fingerprint).
6. **RELATION_BROKEN** *(new, v0.4)* — a relation across surfaces broke (caught by the
   relational/join read; **exempt from transition-typing** — no single-surface baseline).

### 2.2 Corroboration (persistence over time) *(D28, deterministic — no LLM)*

The typing engine (§2/§2.1) types a **single** observation. Corroboration is the layer
**above** it that decides, over an **ordered sequence** of observations of one surface,
whether an *ambiguous* signal earns a route to the orchestrator. It is fully deterministic.

- **What is ambiguous.** A signal is ambiguous iff it is **non-status-coded** and is **not**
  already a clean fault-shape or a hard-invariant violation — i.e. the per-observation engine
  returned **telemetry** for shapeless drift. Typed drift and hard invariants are *not*
  ambiguous: they fire on their own at INTERRUPT grade.
- **Persistence, not breadth.** An ambiguous signal promotes **only if a confirming
  re-observation of the SAME surface still shows the anomaly**. A one-shot wobble that has
  **healed** by the re-look stays telemetry. The dead v0.3 "second independent signal" clause
  is replaced by this: persistence over time, because correlated noise self-corroborates.
- **Threshold = ONE re-look** (least-latency default, frozen pre-data, D28): two
  **consecutive** anomalous observations (first sighting + one confirming re-look). A surface
  with **no** re-observation before the run ends stays telemetry and is backstopped by the
  cadence **pre-completion sweep** — **never promoted blind**.
- **Promotion grade = CAUTION.** A persistence-confirmed ambiguous signal becomes a
  corroborated invalidation at **caution grade** (a recommended action routed to the
  orchestrator), kept **distinct** from the hard interrupt-and-replan path.
- **Status-coded fast path retained.** A status-coded signal (the §5.3 compiled status
  expectation / STATUS_CLASS hard invariant) keeps its **direct interrupt path with no
  persistence**. Persistence governs only the non-status-coded signals.
- **No raw-count aggregation (hard prohibition, D28).** The layer builds **no** "wobbles
  exceed N ⇒ stop" counter — that is v1's escalation-cap pathology (172 noise fires ground
  one run to death). Each persistence-confirmed surface is emitted as a **separate** caution;
  the layer **aggregates nothing**. Breadth across surfaces is the orchestrator's existing
  replan decision, which sees the multiple live cautions.

**Named dependency (cadence, next session).** Corroboration consumes re-observations through
a minimal interface; the **guaranteed pre-completion sweep** that supplies a final re-look
for an un-re-observed surface is the cadence layer's job (§3.1) and is **not built this
session** — corroboration only declares the requirement.

---

## 3. Attachment policy

### 3.1 Compile-time attachment (no trajectory prediction)

The compiler does **not** predict whether the worker will re-observe a surface — that is
runtime trajectory prediction it cannot do at plan time. Instead, attach a probe iff the
assumption is **load-bearing, read-and-trust (§3.3), and its truth is NOT carried by the
surface's ordinary worker-visible traffic** *(v0.4, A6 — replaces v0.3's "self-announcing
by signal shape", resolving the §3.1/§3.2 conflict)*. That is: if the worker's normal
calls to the surface would already reveal the assumption's violation (the guarantee rides
the ordinary traffic), no probe is needed; if the guarantee lives somewhere the ordinary
traffic does not surface (a body/header/hidden policy/enforcing-vs-accepting gate/a
per-revisit different slice/a cross-surface join/a late-loud re-announcement), a probe is
warranted. The question "will it be re-observed *in time to recover*" is delegated to the
runtime event-gated cadence layer and its **guaranteed pre-completion sweep** — a runtime
guarantee, not a compile-time guess.

### 3.2 The class the surface-level rule mis-handled

**Self-reobserving but non-self-validating** surfaces: they keep answering (often a stable
status) while the load-bearing guarantee is not re-announced — the guarantee lives in the
body/a header/a hidden policy/a sortedness-coverage-consistency property/whether a
downstream gate is actually *enforcing* rather than merely *accepting*; or each revisit
reads a different slice; or a cross-surface (join) invariant breaks while each component
looks fine; or a **late-loud** surface re-announces only after the recoverability window
closed (economically blind). "Status-coded → leave passive" is therefore wrong for the
enforcing-gate case — which is why §4 exists.

### 3.3 Provenance gate; read-and-trust only

A tripwire's mere existence is not proof it is load-bearing — v1's field-shape tripwires
were the false-interrupt engine (14/18 false interrupts). A probe attaches only to an
assumption with a complete chain: `plan step → required world fact → observable surface →
deterministic read → comparison predicate → recovery hint`. Missing the chain ⇒ telemetry
only. And the compiler probes only surfaces the plan **reads and trusts**, never surfaces
**any plan step writes**, and — for baseline stationarity — never surfaces **any concurrent
worker is planned to write per the global planned write-set** *(v0.4, A4)*; those
legitimately drift (a frozen baseline would fire on the plan's own intended work — e.g. a
repository-migration task rewriting its own world).

---

## 4. Gate re-read transport

Keep the **POST-free side channel** (the non-perturbation proof assumes POST-free
transport). The gate-status re-read uses **a world-side, read-only GET route that executes
the *real enforcement predicate* in a no-write mode** — answering "would the gate enforce
this now?", never reading a `gate_enabled` flag (a status surrogate gives high-confidence
false assurance and fails the *targeted* audit). In a world we own, this route is the
principled "shadow evaluator": real enforcement code/config, no mutable world state touched.
**Proof obligation:** the route is demonstrably write-free (no persistence, counters,
caches, logs, rate-limits, auth, sentinels, or timing perturbation). **[Cost]** a
world-surface addition (rev/flag-gated; byte-identical when the v2 channel is off).

**Author ruling D1 (design of record):** built as a thin no-write wrapper over the real
enforcement predicate; the non-perturbation check is a **hard trapdoor** — a route that
fails the three-vector gate is **DISABLED**, the assumption is flagged **UNCOVERED (loud)**
and routed to caution (§5.2). The shadow evaluator runs the real predicate against a
deliberately-failing **canary input** and reports the *behavioural* verdict (a trapped /
bypassed gate admits the canary; an enforcing gate rejects it), so the answer is never a
flag read.

---

## 5. Cross-cutting validity properties

Property set, **extended from four to five**: targeted · fresh · non-perturbing ·
independent · **equivalent [GATE-Δ]**.

### 5.1 Independence, equivalence, and the auth requirement

- **Independent** — the probe re-fetches *from source*; not derived from the worker's
  buffered read or the triggering evidence (v1's "second signal" self-corroborated: 6/18
  false interrupts passed it).
- **Equivalent [GATE-Δ]** — the probe observes the *same logical world-view as the worker*.
  **Hard build requirement:** the probe inherits the **worker's own auth/session context**,
  never a privileged or root credential, or it reads a different world and "confirms" a room
  the worker never stood in. A probe that **cannot acquire worker context is DISQUALIFIED to
  telemetry**, never fired under a privileged key.
- Resolution: **same room, fresh look, not the worker's photo** — equivalent view,
  independent acquisition. Non-perturbation does not imply equivalence; both are required.

### 5.2 Broken-probe semantics (probe-tier vs world-state)

- Response **violates a compiled hard invariant** (expected 200, got 404; required field
  absent) ⇒ **world-state signal** — often the strongest detection.
- Probe **cannot complete or returns a probe-infrastructure error** (timeout, transport
  failure, rate-limit 429, transient 5xx) ⇒ **inconclusive**: certifies nothing, raises no
  strict interrupt alone, bounded retry, persistent failure logged as a *coverage gap*.
- **Inconclusive guaranteed pre-completion sweep** ⇒ commit is **unverified**: routed to
  caution, never silently passed. *(A disabled §4 route per ruling D1 routes here.)*

The probe-tier-vs-world-fault distinction is trivial in the deterministic mock (no
transport weather) and becomes load-bearing in the real-suite study (§8).

### 5.3 Status-coded fast path (tightened)

A status signal takes the no-corroboration fast path **only when the status is unexpected
for that surface at the current plan phase per a compiled expectation** — not merely "≥400"
(a 4xx/5xx can be transient, phase-dependent, or expected in a branch; the in-corpus
"no false interrupt carried status ≥400" prior is small and synthetic).

---

## 6. Replan: keep, recompile-add, prune-dead, verify coverage

**(v0.4, ruling D2 — replaces v0.3 §6's flush-and-recompile.)** On replan:
1. **Keep** the prior probe inventory (no flush; no probe-to-context re-mapping loss).
2. **Recompile and add** probes for the revised plan.
3. **Prune only** probes the N2 pattern-liveness sweep proves **dead** against the revised
   plan's surfaces.
4. **Instrument every post-replan fire** (so a fire from a kept-but-now-irrelevant probe is
   visible, not silent).

Then run the **coverage/liveness check** — reusing the compile-time pattern-liveness
assertion already built (N2) — confirming that **every assumption still live for in-flight
or downstream work has a covering probe**. A still-live assumption left uncovered after
recompilation is flagged loudly; this is the detector for v1's death specimen (replan →
recompiled set covered none of the original armed surfaces → injection fired into an
unwatched world). **Cost (v0.4, A5):** the recompile is booked against whichever run it
occurs on — including the clean-run ≤12% overhead cap when the replan lands on a clean run.

**Named residual (instrumented, not silent):** the **in-flight-dropped probe** — a probe
whose target the revised plan drops while work is still in flight against it — is a known
limit this phase does not architect away; it is logged and observable. No
runtime-execution-state architecture change this phase.

---

## 7. Audits

- **Firing-interrupt audit.** Seeded 20% of probe-*generated interrupts* must be 100%
  targeted / fresh / non-perturbing / independent / **equivalent**.
- **Probe-inventory audit [GATE-Δ → deviations D25].** Audits the compiled probe set ex
  ante — *before any fires* — for provenance-completeness, targetedness, clean/equivalent
  baselines, and non-perturbation by construction. **Honest denominator: the true
  load-bearing assumption set** (task ground truth, the 4–8 per task), not the assumptions
  the compiler mapped — so a compiler that silently fails to emit a probe shows up as a
  coverage hole, not a clean 100%. **Quarantine discipline (D25):** the held-out
  denominator is computed **escrow-side**, reported as an **aggregate only**, and **never
  fed back into compiler iteration**; "load-bearing" is defined **compiler-independently**
  (perturb-and-replay), so the audit measures the information-bound failure directly without
  becoming a tuning signal.

Both the `equivalent` property and the inventory audit **strengthen** the gates, are decided
**before any v2 data exists** (clean), and amend a frozen prereg — entered as numbered
deviations. The `equivalent` firing-audit check is logged as a deviation when the audit
harness lands (a hard stop this session); the inventory-audit quarantine is logged now as
**D25**.

---

## 8. Acknowledged limits (→ threats-to-validity)

- **Information-bounded.** A probe cannot watch a surface the compiler never extracted from
  the plan; "build generally" means *extract surface dependencies thoroughly*, not "probe harder."
- **Semantically incomplete.** Hash/shape primitives cannot see a meaning-level contradiction
  where bytes and shape look fine — marks retrieval-integrity as the recall soft spot.
- **Emergent-write residual (v0.4, A4).** Stationarity is judged against the *planned*
  write-set; a worker that writes a surface no plan step declared can dirty a baseline the
  compiler believed stationary. Named, not closed, this phase.
- **In-flight-dropped probe (v0.4, ruling D2).** A probe whose target the revised plan drops
  mid-flight is kept-but-stale until the next sweep; logged and observable, not architected
  away this phase.
- **Probe-tier failure in the wild.** The probe-infra-vs-world-fault distinction (§5.2) is
  benign in the deterministic mock but load-bearing in the real suite (rate limits, transient
  outages); a pre-committed real-suite policy is owed for Phase 1c **[GATE-Δ → deviations D26]**.

**Paper-framing claim (narrowed):** compiled deterministic probes restore observation *only
for plan-exposed, probe-equivalent, comparison-valid surfaces, under non-perturbation and
timing constraints* — not "active monitoring solves observation."

---

## 9. Compile prompt (D4) — design of record (built 2026-06-14)

The single LLM step that feeds the substrate. **Author-ratified design of record:**

- **Soft extraction over the substrate's hard constraints.** The prompt's only output is
  a list of ASSUMPTIONS — each `{plan-step ref, the world-fact that step needs, the real
  surface where that fact lives, optional recovery hint}`. It emits **no probes, no lens
  choices, no firing decisions**; the substrate (B1–B7) compiles all of it.
- **Generous extraction.** The prompt surfaces everything the plan plausibly leans on and
  is NOT asked to be careful; precision is the substrate's job (the provenance gate, the
  appendix grounding, the attachment policy, and the 12% budget are the filters). Tune for
  **recall of dependencies**.
- **Category-blind (Rule Zero).** No failure-category list enters the prompt. It reasons in
  two general things only: the dependency-noticing instinct ("what does this step trust
  about the world") and the six general change-shapes already in the substrate
  (**vanished / status-moved / structure-changed / value-moved / order-scrambled /
  relationship-broke**). Category labels are applied only at analysis time, escrow-side for
  the held-out two. The prompt is tuned and validated ONLY on the five seen categories;
  generalization to the held-out two is measured ONLY at matrix launch.
- **Few-shot from seen.** Grounded with worked examples drawn ONLY from the five seen
  categories — concrete instances of "a step trusted X, X changed, this is the shape it
  took." The held-out two never appear as examples, in the prompt, or in any test world.
- **Frozen example-selection rule (custody; deviations D27, sibling to D25).** The few-shot
  set is chosen by a fixed rule committed BEFORE any prompt tuning (cover all six change-
  shapes on seen-category surfaces by a stated criterion) and then frozen — NOT hand-curated.

### 9.1 Operationalization (build note, FLAGGED FOR AUTHOR)

The design-of-record output is the four soft fields. The build adds ONE optional field,
`pointer` — "the real surface where that fact lives" at field granularity (a fact often
lives in a specific field of a surface). The emitted assumption therefore is
`{plan_step, world_fact, surface, pointer?, recovery_hint?}` and carries **no shape, lens,
comparison, attach/passive decision, evidence-class, cadence, or method** — those remain
the substrate's. The deterministic bridge maps the surface's STRUCTURE to a substrate kind:

- surface is a known enforcement **gate** (`/repo/validate`, `/docs/validate`) → `GATE`
  (the §4 shadow route + non-perturbation trapdoor, ruling D1);
- a `pointer` is given (the fact lives in a specific field) → `VALUE` (FIELD_READ drift);
- a bare surface → `STRUCTURE` (SCHEMA_FINGERPRINT drift).

This covers the five seen categories as interrupting probes (endpoint-removal and
auth-revocation change the body's `{key:type}` shape → STRUCTURE; a field rename →
STRUCTURE; a value swap on a stable shape → VALUE via the pointer; a gate that stops
enforcing → GATE). The full six-shape vocabulary (incl. ORDER/RELATION/STATUS/PRESENCE/
WHOLE_PAYLOAD) remains available in the substrate; the soft prompt exercises the
gate/value/structure subset, with richer extraction (ORDER/RELATION) a later refinement.
The prompt still REASONS about all six shapes (step iii) to decide *what* is a real,
watchable dependency — it just does not emit the shape. **Open for author:** whether to
have the prompt also emit the change-shape explicitly (it would let the substrate pick
STATUS/ORDER/RELATION directly); deferred as it edges toward a lens-ish choice.

### 9.2 Internal structure (one bounded call)

(i) identify the surfaces the plan touches from the plan + the rev-aware surface appendix
(B7); (ii) pull the contract/schema-grounded assumptions mechanically; (iii) the judgment
pass, per plan step — "what does it trust, and which of the six shapes would break that
trust"; (iv) bind each assumption to a real appendix surface + the provenance chain + a
recovery hint. One bounded compile call per run, and per replan (keep-not-flush, ruling
D2); the compile cost is booked into the economics against the 12% (§0).

---

## Open residuals

1. Is the §2.1 fault-shape vocabulary complete enough to carry generalization, or does it
   leave a class of plan-breaking change that is real, detectable in principle, and not a
   listed shape? (v0.4 narrows this with ORDER/RELATION/FIELD-ADDED; the bound is reduced,
   not closed — §0/A3.)
2. Does keep-plus-recompile-add-plus-liveness (§6) fully close the v1 blind window, or only
   narrow it — e.g. for an assumption that is live but not derivable from the revised plan
   text, or an in-flight-dropped probe?
3. The §8 Phase-1c probe-failure policy is named but unwritten (D26, owed).
4. The fault-shape count reconciliation (6 vs 7; FIELD-ADDED as `SCHEMA_SHAPE` vs a distinct
   member) is an open author decision — see the reconciliation note at the top.
