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
    "gate_skip_trap",
]


class InjectionSpec(BaseModel):
    type: InjectionType
    params: dict[str, Any] = Field(default_factory=dict)


class RunConfig(BaseModel):
    run_id: str
    seed: int
    system: str
    task_id: str
    n_inject: Optional[int] = None       # counter value at which the injection fires
    injection: Optional[InjectionSpec] = None
    trace_path: str


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

        self.repo_files: dict[str, str] = dict(REPO_FILES)

        # tool-call counter and injection bookkeeping (counter-triggered path)
        self.counter: int = 0
        self.injection_fired: bool = False
        self.injection_fired_at: Optional[int] = None

        # mutation flags written by world.injections
        self.removed_routes: list[str] = []
        self.pricing_drift: bool = False
        self.trapped_gates: list[str] = []
        self.admin_injections: list[dict[str, Any]] = []

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
