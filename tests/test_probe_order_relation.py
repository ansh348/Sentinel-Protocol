"""B1 acceptance: order-sensitive and relational/join executor primitives
(design v0.4 §1.1/§2.1; probe_compiler_design_v0.4.md). GENERIC lenses only
(Rule Zero) — no category-specific reads anywhere.

Headline: a reorder of a load-bearing array is MISSED by the value-blind
schema fingerprint (a sorted set) and CAUGHT by the order-sensitive primitive.
"""
from __future__ import annotations

import pytest

from conftest import get_token
from sentinel_v2.probes import (JoinResult, ProbeExecutor, ordered_digest,
                                ordered_subarray, project_keys, read_field,
                                relation_holds, schema_fingerprint)


@pytest.fixture
def probe_world(make_world):
    world = make_world(probe_channel=True, world_rev=2)
    token = get_token(world.client)
    return world, ProbeExecutor(world.client, auth_token=token)


# -- order-sensitive lens ------------------------------------------------------

def test_order_blindness_repro():
    """The B1 acceptance: the sorted-set fingerprint is order-blind; the
    order-sensitive read is not."""
    base = {"results": [{"sku": "A"}, {"sku": "B"}, {"sku": "C"}]}
    reordered = {"results": [{"sku": "C"}, {"sku": "B"}, {"sku": "A"}]}

    # the value-blind {key:type} fingerprint CANNOT see a reorder
    assert schema_fingerprint(base) == schema_fingerprint(reordered)

    # the order-sensitive primitive CAN
    assert ordered_subarray(base, "/results", field="sku") == ("A", "B", "C")
    assert ordered_subarray(reordered, "/results", field="sku") == ("C", "B", "A")
    assert (ordered_subarray(base, "/results", field="sku")
            != ordered_subarray(reordered, "/results", field="sku"))
    # and so does the sub-array hash flavor
    assert (ordered_digest(base, "/results", field="sku")
            != ordered_digest(reordered, "/results", field="sku"))


def test_ordered_subarray_whole_elements_and_scalars():
    body = {"ranking": ["x", "y", "z"]}
    assert ordered_subarray(body, "/ranking") == ("x", "y", "z")
    # whole-dict elements canonicalize value-faithfully (order-sensitive)
    dicts = {"rows": [{"a": 1, "b": 2}, {"b": 2, "a": 1}]}
    seq = ordered_subarray(dicts, "/rows")
    assert seq[0] == seq[1]  # same dict, key-order-independent canonicalization


def test_ordered_subarray_raises_on_non_list_and_missing_field():
    with pytest.raises(KeyError):
        ordered_subarray({"x": 1}, "/x")             # not a list
    with pytest.raises(KeyError):
        ordered_subarray({"x": 1}, "/missing")       # unresolvable pointer
    with pytest.raises(KeyError):
        ordered_subarray({"r": [{"sku": "A"}, {"name": "B"}]},
                         "/r", field="sku")          # field missing in element 1


def test_ordered_digest_is_deterministic_and_order_sensitive():
    body = {"r": [1, 2, 3]}
    assert ordered_digest(body, "/r") == ordered_digest({"r": [1, 2, 3]}, "/r")
    assert ordered_digest(body, "/r") != ordered_digest({"r": [3, 2, 1]}, "/r")


def test_position_pinned_read_is_the_other_order_flavor():
    """The design names two order flavors; the position-pinned read needs no new
    primitive — it is read_field on an indexed pointer."""
    from sentinel_v2.probes import ProbeResult
    r = ProbeResult(method="GET", path="/x", status=200, headers={},
                    body={"results": [{"sku": "A"}, {"sku": "B"}]})
    assert read_field(r, "/results/0/sku") == "A"
    assert read_field(r, "/results/1/sku") == "B"


# -- relational/join lens ------------------------------------------------------

def test_relation_subset_holds_and_breaks_with_witnesses():
    # a cross-surface coverage relation: every ordered SKU resolves in the catalog
    catalog = {"items": [{"sku": "A"}, {"sku": "B"}, {"sku": "C"}]}
    orders_ok = {"lines": [{"sku": "A"}, {"sku": "B"}]}
    orders_bad = {"lines": [{"sku": "A"}, {"sku": "Z"}]}

    held = relation_holds(orders_ok, "/lines", catalog, "/items",
                          left_field="sku", right_field="sku", relation="subset")
    assert isinstance(held, JoinResult) and held.holds is True
    assert held.left_only == () and held.relation == "subset"

    broken = relation_holds(orders_bad, "/lines", catalog, "/items",
                            left_field="sku", right_field="sku", relation="subset")
    assert broken.holds is False
    assert broken.left_only == ("Z",)   # the witness: the unresolved foreign key


def test_relation_equal_semantics():
    a = {"k": [1, 2, 3]}
    b = {"k": [3, 2, 1]}            # same set, different order
    c = {"k": [1, 2]}
    assert relation_holds(a, "/k", b, "/k", relation="equal").holds is True
    eq = relation_holds(a, "/k", c, "/k", relation="equal")
    assert eq.holds is False and eq.left_only == (3,) and eq.right_only == ()


def test_relation_unknown_raises():
    with pytest.raises(ValueError, match="unknown relation"):
        relation_holds({"k": []}, "/k", {"k": []}, "/k", relation="bogus")


def test_project_keys_is_set_semantics():
    body = {"items": [{"sku": "A"}, {"sku": "A"}, {"sku": "B"}]}
    assert project_keys(body, "/items", field="sku") == frozenset({"A", "B"})


# -- live ProbeResult compatibility (across surfaces) --------------------------

def test_lenses_accept_live_probe_results(probe_world):
    _, ex = probe_world
    passages = ex.get("/docs/passages")
    inventory = ex.get("/inventory/items")

    # order-sensitive read on a live list surface (insertion order preserved)
    ids = ordered_subarray(passages, "/passages", field="id")
    assert len(ids) == 6 and ids[0] == "pol-returns"
    assert ordered_digest(passages, "/passages", field="id") == \
        ordered_digest(ex.get("/docs/passages"), "/passages", field="id")

    # self-coverage holds across a live ProbeResult round-trip
    assert relation_holds(inventory, "/items", inventory, "/items",
                          relation="equal").holds is True

    # a genuinely cross-surface relation that is BROKEN on live data: the SKUs
    # the inventory lists are not covered by the passage-id namespace
    broken = relation_holds(inventory, "/items", passages, "/passages",
                            right_field="id", relation="subset")
    assert broken.holds is False and len(broken.left_only) == 6
