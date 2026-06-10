"""Programmatic success checker for task a1 (exact-match against the world's
ground truth; no LLM grading — protocol Section 4)."""
from __future__ import annotations

from typing import Any

TOLERANCE = 0.005


def check(final_report: Any, ground_truth: dict) -> tuple[bool, str]:
    if not isinstance(final_report, dict):
        return False, "final report is not a JSON object"
    problems: list[str] = []
    for sku, price in ground_truth["prices"].items():
        entry = final_report.get(sku)
        if not isinstance(entry, dict):
            problems.append(f"{sku}: missing")
            continue
        inv = ground_truth["inventory"][sku]
        ship = ground_truth["shipping"][sku]["us-east"]
        unit_price = entry.get("unit_price")
        if not isinstance(unit_price, (int, float)) or abs(unit_price - price) > TOLERANCE:
            problems.append(f"{sku}: unit_price {unit_price!r} != {price}")
        if entry.get("quantity") != inv["quantity"]:
            problems.append(f"{sku}: quantity {entry.get('quantity')!r} != {inv['quantity']}")
        if entry.get("warehouse") != inv["warehouse"]:
            problems.append(f"{sku}: warehouse {entry.get('warehouse')!r} != {inv['warehouse']}")
        shipping = entry.get("shipping")
        if not isinstance(shipping, dict):
            problems.append(f"{sku}: shipping missing")
        else:
            rate = shipping.get("rate")
            if not isinstance(rate, (int, float)) or abs(rate - ship["rate"]) > TOLERANCE:
                problems.append(f"{sku}: shipping.rate {rate!r} != {ship['rate']}")
            if shipping.get("carrier") != ship["carrier"]:
                problems.append(f"{sku}: shipping.carrier {shipping.get('carrier')!r} != {ship['carrier']}")
    if problems:
        return False, "; ".join(problems[:10])
    return True, "all six SKUs match ground truth"
