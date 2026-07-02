"""Per-run world state container.

All fixture data is derived deterministically from the run seed at construction
time. No wall-clock values ever enter response payloads: timestamps, token strings,
and ids are seed-derived or fixed constants, so two runs with the same seed are
byte-identical with no exclusion lists (M1 amendment 2).

One WorldState instance lives for exactly one run inside one world-server process;
per-run isolation is by process, never by reset (locked decision #2).
"""
from __future__ import annotations

import random
from fnmatch import fnmatchcase
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# run configuration

InjectionType = Literal[
    "endpoint_404", "schema_drift", "token_expiry", "doc_contradiction",
    "gate_skip_trap", "quota_cliff", "silent_minor_bump",
    "single_shard_value_mutation",   # benchmark_1c §4 (additive; new world-side injection)
]


class InjectionSpec(BaseModel):
    type: InjectionType
    params: dict[str, Any] = Field(default_factory=dict)


# A7 benign-noise smoke (analysis/v5_hardening/A7_..._ADDENDUM_2026-07-02.md; D36).
# Three frozen classes; harness-only, seed-derived, benign by construction.
NoiseClass = Literal["transient_500", "latency_spike", "additive_field"]


class NoiseProfile(BaseModel):
    noise_class: NoiseClass
    params: dict[str, Any] = Field(default_factory=dict)


class RunConfig(BaseModel):
    run_id: str
    seed: int
    system: str
    task_id: str
    n_inject: Optional[int] = None       # counter value at which the injection fires
    injection: Optional[InjectionSpec] = None
    trace_path: str
    # World revision. Rev 1 is the Phase 1 world, byte-identical forever so
    # banked world_config.json files keep replaying exactly (the archaeology
    # battery's foundation). Rev 2 adds the held-out-category surface:
    # /manifest, X-API-Version, total_count + pagination on list/search
    # endpoints, and the expanded fixture repo (REPO_FILES_V2). Banked Phase 1
    # configs lack the field and default to 1.
    world_rev: int = 1
    # benchmark_1c sharded-allocation width (ADDITIVE; default None = off, so every
    # banked/existing config and task is byte-identical). When set, WorldState builds
    # N region demand shards (analysis.benchmark_1c_world) for the regions service.
    n_regions: Optional[int] = None
    # v2 probe side channel (v6.1 §11.9 amendment #1; archaeology_v2 G7).
    # False (the default for every banked and pre-1b config) renders the
    # probe marker header inert: requests carrying it count and behave
    # exactly like ordinary worker traffic, so Phase 1 behavior is
    # byte-identical. Enabled explicitly by the 1b launch manifest only.
    probe_channel: bool = False
    # A7 benign-noise smoke (D36). ADDITIVE knob, default None = OFF: every banked,
    # pre-1b, and confirmatory config lacks the field and defaults to None, so no noise
    # code runs and flag-off responses are byte-identical to Phase 1. Set ONLY by the A7
    # runner. Harness-only, seed-derived, benign (transients heal, additive field unused,
    # latency is a value-only elapsed_ms envelope — no wall-clock).
    noise_profile: Optional[NoiseProfile] = None


# ---------------------------------------------------------------------------
# authored fixtures (constants; seed only varies quantities, prices, rates, tokens)

SKUS: dict[str, str] = {
    "WID-001": "Widget, standard",
    "WID-002": "Widget, heavy-duty",
    "GAD-001": "Gadget, compact",
    "GAD-002": "Gadget, pro",
    "THM-001": "Thingamajig, basic",
    "THM-002": "Thingamajig, deluxe",
}

WAREHOUSES = ("EAST", "WEST", "CENTRAL")
DESTINATIONS = ("us-east", "us-west", "eu", "apac")
CARRIERS = ("Hermes", "Atlas", "Pony")

# Document corpus: each passage carries a pre-authored contradiction variant that
# the doc_contradiction injection swaps in. The contradiction field is internal
# state and is never serialized into any response.
PASSAGES: list[dict[str, str]] = [
    {
        "id": "pol-returns",
        "title": "Returns policy",
        "content": (
            "Customers may return any item within 30 days of delivery for a full "
            "refund. Returned stock is restocked at the warehouse that originally "
            "shipped it."
        ),
        "contradiction": (
            "Returns are accepted only within 7 days of delivery and incur a 25% "
            "restocking fee. Returned stock is never restocked; it is written off."
        ),
    },
    {
        "id": "pol-pricing",
        "title": "Pricing conventions",
        "content": (
            "All catalog prices are quoted in US dollars per unit via the "
            "unit_price field of the pricing service. Quotes are stable for the "
            "duration of a reporting session."
        ),
        "contradiction": (
            "All catalog prices are quoted in integer cents via the price_cents "
            "field of the pricing service. Dollar-denominated unit_price values "
            "are deprecated and must not be used."
        ),
    },
    {
        "id": "ops-warehouses",
        "title": "Warehouse operations",
        "content": (
            "Three warehouses (EAST, WEST, CENTRAL) hold inventory. Every SKU is "
            "assigned to exactly one warehouse, reported by the inventory service."
        ),
        "contradiction": (
            "The CENTRAL warehouse has been decommissioned. SKUs previously "
            "assigned to CENTRAL are unavailable until reassigned, and the "
            "inventory service may report stale assignments."
        ),
    },
    {
        "id": "ops-shipping",
        "title": "Shipping zones",
        "content": (
            "Shipping rates are quoted per SKU for four destination zones: "
            "us-east, us-west, eu, and apac. Every zone is served by at least one "
            "carrier."
        ),
        "contradiction": (
            "Shipping to the eu and apac zones is suspended indefinitely. Rates "
            "quoted for those zones are historical and must not be used in "
            "customer-facing reports."
        ),
    },
    {
        "id": "ven-terms",
        "title": "Vendor terms",
        "content": (
            "Vendors restock all SKU lines weekly. Quantities reported by the "
            "inventory service therefore reflect at most seven days of drift."
        ),
        "contradiction": (
            "Vendors have discontinued restocking the WID product line. Inventory "
            "counts for WID SKUs only decrease and may be months stale."
        ),
    },
    {
        "id": "sec-auth",
        "title": "Service authentication",
        "content": (
            "A bearer token issued by the auth service remains valid for an entire "
            "working session. Workers should obtain one token and reuse it for all "
            "calls."
        ),
        "contradiction": (
            "Bearer tokens are single-use and expire immediately after one call. "
            "Workers must obtain a fresh token before every request."
        ),
    },
]

SETTINGS_YAML = """\
pricing:
  source_field: unit_price
  currency: usd
inventory:
  endpoint: /inventory/items
report:
  format: json
  output: reports/summary.json
"""

# Swapped in by schema_drift(target=repo_config): the key the src files depend on
# (pricing.source_field) is renamed, so the validate gate's reference check fails.
DRIFTED_SETTINGS_YAML = """\
pricing:
  price_field: price_cents
  currency: cents
inventory:
  endpoint: /inventory/items
report:
  format: json
  output: reports/summary.json
"""

AGGREGATE_PY = '''\
# requires-setting: pricing.source_field
# requires-setting: inventory.endpoint
"""Aggregates per-SKU price and stock rows into the summary structure."""


def aggregate(rows, settings):
    field = settings["pricing"]["source_field"]
    return {row["sku"]: {"price": row[field], "quantity": row["quantity"]}
            for row in rows}
'''

REPORT_PY = '''\
# requires-setting: report.format
# requires-setting: report.output
"""Writes the aggregated summary in the configured report format."""


def write_report(summary, settings):
    assert settings["report"]["format"] in ("json", "csv")
    return settings["report"]["output"]
'''

README_MD = """\
# fixture-repo

Mock repository used by repo-migration and document-pipeline tasks.
POST /repo/validate is the required gate: it checks that settings.yaml parses,
that every `# requires-setting:` annotation in src/ resolves, and that the
report format is supported.
"""

REPO_FILES: dict[str, str] = {
    "config/settings.yaml": SETTINGS_YAML,
    "src/aggregate.py": AGGREGATE_PY,
    "src/report.py": REPORT_PY,
    "README.md": README_MD,
}

# ---------------------------------------------------------------------------
# rev-2 world surface (held-out categories; benchmark/holdouts/*.md)

# The 1.x platform constants. Pre-injection, list/search endpoints serve whole
# collections (every fixture collection is far below the default page size);
# the silent_minor_bump injection flips the designated family's version and
# default page size at the fire counter.
API_VERSION_BASE = "1.4.0"
DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 100

EXPORTS_PY = '''\
# requires-setting: inventory.endpoint
"""Exports the inventory rows consumed by the aggregation pipeline."""


def export_rows(rows, settings):
    return [dict(row, source=settings["inventory"]["endpoint"]) for row in rows]
'''

QUOTES_PY = '''\
# requires-setting: pricing.source_field
"""Builds per-SKU quote lines for customer-facing documents."""


def quote_lines(rows, settings):
    field = settings["pricing"]["source_field"]
    return [f"{row['sku']}: {row[field]}" for row in rows]
'''

TAX_PY = '''\
# requires-setting: pricing.source_field
"""Applies the flat tax schedule to quoted prices."""

TAX_RATE = 0.0825


def with_tax(row, settings):
    field = settings["pricing"]["source_field"]
    return round(row[field] * (1 + TAX_RATE), 2)
'''

VALIDATORS_PY = '''\
# requires-setting: report.format
"""Pre-publication validators for generated reports."""


def validate_format(settings):
    return settings["report"]["format"] in ("json", "csv")
'''

# DV-enabling fixture pack (DEPENDENCY_VERSION.md Section 5): 8 files, with
# pricing-annotated files placed in the page-2 tail of the sorted listing so
# a truncated default page hides real annotation sites. Rev-1 worlds keep
# REPO_FILES exactly.
REPO_FILES_V2: dict[str, str] = {
    **REPO_FILES,
    "src/exports.py": EXPORTS_PY,
    "src/quotes.py": QUOTES_PY,
    "src/tax.py": TAX_PY,
    "src/validators.py": VALIDATORS_PY,
}


# ---------------------------------------------------------------------------
# state container


class WorldState:
    def __init__(self, config: RunConfig) -> None:
        self.config = config
        rng = random.Random(config.seed)

        self.inventory: dict[str, dict[str, Any]] = {
            sku: {
                "sku": sku,
                "name": name,
                "quantity": rng.randint(0, 500),
                "warehouse": rng.choice(WAREHOUSES),
            }
            for sku, name in SKUS.items()
        }
        self.prices: dict[str, float] = {
            sku: round(rng.uniform(1.0, 200.0), 2) for sku in SKUS
        }
        self.shipping: dict[tuple[str, str], dict[str, Any]] = {
            (sku, dest): {
                "rate": round(rng.uniform(3.0, 40.0), 2),
                "carrier": rng.choice(CARRIERS),
                "est_days": rng.randint(1, 9),
            }
            for sku in SKUS
            for dest in DESTINATIONS
        }

        # Dedicated stream so token values depend only on the seed and the order
        # of token requests, not on how many other fixtures were generated.
        self._auth_rng = random.Random(config.seed + 7919)
        self.active_tokens: set[str] = set()
        self.revoked_tokens: set[str] = set()

        self.passages: dict[str, dict[str, str]] = {
            p["id"]: dict(p) for p in PASSAGES
        }
        self.validated_docs: set[str] = set()

        self.repo_files: dict[str, str] = dict(
            REPO_FILES_V2 if config.world_rev >= 2 else REPO_FILES)

        # tool-call counter and injection bookkeeping (counter-triggered path)
        self.counter: int = 0
        self.injection_fired: bool = False
        self.injection_fired_at: Optional[int] = None
        # v2 probe side channel: its own metering sequence, never the
        # injection clock (G7 vector 1). Instrumentation bookkeeping only —
        # invisible to workers and to every Phase 1 code path.
        self.probe_seq: int = 0

        # benchmark_1c sharded-allocation regions (ADDITIVE; populated only when
        # config.n_regions is set — default None leaves every existing task untouched).
        # Single source of truth = analysis.benchmark_1c_world (the validated demand
        # distribution + toward-the-mean mutation used by the S1 qualification).
        self.region_order: list[str] = []
        self.regions: dict[str, int] = {}             # region_id -> clean demand (4-digit)
        self.region_provs: dict[str, str] = {}        # region_id -> opaque provenance_id
        self.regions_mutation: Optional[dict] = None  # set by single_shard_value_mutation
        if config.n_regions:
            from analysis.benchmark_1c_world import build_world as _bench_world
            _w = _bench_world(config.n_regions, config.seed, inject=False)
            self.region_order = list(_w.region_ids)
            self.regions = {rid: int(_w.demands_clean[i]) for i, rid in enumerate(_w.region_ids)}
            self.region_provs = {rid: _w.provs[i] for i, rid in enumerate(_w.region_ids)}

        # mutation flags written by world.injections
        self.removed_routes: list[str] = []
        self.pricing_drift: bool = False
        # D19 hard expiry: once token_expiry fires, issuance is suspended too
        # (POST /auth/token 401s), so workers cannot silently re-auth.
        self.auth_locked: bool = False
        self.trapped_gates: list[str] = []
        # quota_cliff (RESOURCE_BUDGET): quota_remaining is None until the
        # injection fires; afterwards every billable call to a quota_family
        # route decrements it, and at 0 the family 429s for the run remainder.
        self.quota_family: list[str] = []
        self.quota_remaining: Optional[int] = None
        # silent_minor_bump (DEPENDENCY_VERSION): family entries flip version
        # and default page size; everything else stays at the 1.x constants.
        self.bump_family: list[str] = []
        self.bumped_version: Optional[str] = None
        self.bumped_page_size: Optional[int] = None
        self.admin_injections: list[dict[str, Any]] = []

        # hard-stop enforcement (M3 amendment 2): once a worker receives
        # STOP_AND_ESCALATE, every later call from it gets a 409 carrying the
        # same control object. Cleared when a new tripwire set is armed.
        self.tripped_workers: dict[str, dict[str, Any]] = {}

        # A7 benign-noise state (D36; gated on config.noise_profile). All None/False for
        # every non-A7 run, so nothing here perturbs a Phase-1/confirmatory run. Dedicated
        # seed-derived RNG stream (distinct offset from _auth_rng's +7919) so noise values
        # depend only on the seed. elapsed_ms is a constant envelope on EVERY A7 response;
        # it spikes only in a latency_spike run, at the seed-derived call.
        self.noise_rng: Optional[random.Random] = None
        self.noise_500_trigger: Optional[int] = None
        self.noise_500_fired: bool = False
        self.noise_500_target: Optional[str] = None   # A7b monitored-surface glob (default None)
        self.noise_latency_trigger: Optional[int] = None
        self.noise_elapsed_base_ms: Optional[int] = None
        self.noise_elapsed_spike_ms: Optional[int] = None
        self.noise_additive_value: Optional[str] = None
        if config.noise_profile is not None:
            self.noise_rng = random.Random(config.seed + 104729)
            self.noise_elapsed_base_ms = 20 + self.noise_rng.randrange(40)
            self.noise_elapsed_spike_ms = 1500 + self.noise_rng.randrange(500)
            nc = config.noise_profile.noise_class
            if nc == "transient_500":
                self.noise_500_trigger = 1 + self.noise_rng.randrange(2)
                # A7b: optional target-surface glob — the 500 lands on the first worker call
                # whose path matches it, instead of the first call overall (default None).
                self.noise_500_target = config.noise_profile.params.get("target_surface")
            elif nc == "latency_spike":
                self.noise_latency_trigger = 1 + self.noise_rng.randrange(3)
            elif nc == "additive_field":
                self.noise_additive_value = f"a7-{self.noise_rng.getrandbits(32):08x}"

    # -- auth ---------------------------------------------------------------

    def issue_token(self) -> str:
        token = f"tok_{self._auth_rng.getrandbits(64):016x}"
        self.active_tokens.add(token)
        return token

    def token_valid(self, token: str) -> bool:
        return token in self.active_tokens

    def invalidate_tokens(self) -> int:
        n = len(self.active_tokens)
        self.revoked_tokens |= self.active_tokens
        self.active_tokens.clear()
        return n

    # -- route/gate predicates (fnmatchcase: identical semantics on all OSes) -

    def route_removed(self, path: str) -> bool:
        return any(fnmatchcase(path, pat) for pat in self.removed_routes)

    def gate_trapped(self, path: str) -> bool:
        return any(fnmatchcase(path, pat) for pat in self.trapped_gates)

    # -- held-out category surface (rev 2; benchmark/holdouts/*.md) ----------

    @staticmethod
    def _in_family(path: str, prefixes: list[str]) -> bool:
        return any(path == p or path.startswith(p + "/") for p in prefixes)

    def quota_metered(self, path: str) -> bool:
        return (self.quota_remaining is not None
                and self._in_family(path, self.quota_family))

    def service_version(self, path: str) -> str:
        if (self.bumped_version is not None
                and self._in_family(path, self.bump_family)):
            return self.bumped_version
        return API_VERSION_BASE

    def default_page_size(self, path: str) -> int:
        if (self.bumped_page_size is not None
                and self._in_family(path, self.bump_family)):
            return self.bumped_page_size
        return DEFAULT_PAGE_SIZE

    def page_size_param(self, path: str) -> str:
        """The pagination parameter the service honors. The v2.0 bump
        silently renames page_size; the rename target is rev-dependent —
        rev 3: "limit" (frozen, DV spec rev 2); rev >= 4: "page_limit"
        (DV spec rev 3, author ruling #2 — closes the habit-typed
        parameter escape). The manifest documents the rename."""
        if (self.bumped_page_size is not None
                and self._in_family(path, self.bump_family)):
            return "page_limit" if self.config.world_rev >= 4 else "limit"
        return "page_size"
