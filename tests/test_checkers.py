"""D16 acceptance: every task yaml declares an existing checker that loads and
smoke-passes — a ground-truth-faithful report passes, empty/non-dict reports
fail. Closes the night-0 test gap (tasks/checkers/ held only a1.py while four
task yamls declared checkers, so 9/13 night-0 jobs crashed at the checker
step).

Smoke fixtures are built from the task yamls and the world's authored
fixtures only — never from run outputs (night-0 outputs become test fixtures
only after their retroactive verdicts are recorded; author ruling
2026-06-10)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = REPO_ROOT / "tasks"
TASK_PATHS = sorted(TASKS_DIR.glob("[abcd][0-9].yaml"))


def load_checker(checker_rel: str):
    # mirrors conductor.run_one._load_checker
    path = TASKS_DIR / checker_rel
    spec = importlib.util.spec_from_file_location(f"checker_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def task_spec(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def ground_truth(client) -> dict:
    return client.get("/admin/ground_truth").json()


def test_every_task_yaml_declares_an_existing_loadable_checker():
    assert TASK_PATHS, "no task yamls found"
    for path in TASK_PATHS:
        spec = task_spec(path)
        checker_rel = spec.get("checker")
        assert checker_rel, f"{path.name}: no checker declared"
        assert (TASKS_DIR / checker_rel).is_file(), \
            f"{path.name}: declared checker {checker_rel} does not exist"
        module = load_checker(checker_rel)
        assert callable(getattr(module, "check", None)), \
            f"{checker_rel}: no callable check()"


def test_every_checker_rejects_non_dict_and_empty_reports(make_world):
    gt = ground_truth(make_world().client)
    for path in TASK_PATHS:
        checker = load_checker(task_spec(path)["checker"])
        for bad in ("not a dict", None, {}):
            ok, detail = checker.check(bad, gt)
            assert ok is False, f"{path.stem}: accepted {bad!r}"
            assert isinstance(detail, str) and detail


def test_a1_checker_passes_a_ground_truth_report(make_world):
    gt = ground_truth(make_world().client)
    report = {
        sku: {
            "unit_price": price,
            "quantity": gt["inventory"][sku]["quantity"],
            "warehouse": gt["inventory"][sku]["warehouse"],
            "shipping": {"rate": gt["shipping"][sku]["us-east"]["rate"],
                         "carrier": gt["shipping"][sku]["us-east"]["carrier"]},
        }
        for sku, price in gt["prices"].items()
    }
    ok, detail = load_checker("checkers/a1.py").check(report, gt)
    assert ok, detail


def test_b1_checker_passes_a_faithful_migration(make_world):
    client = make_world().client
    settings = client.get("/repo/files/config/settings.yaml").json()["content"]
    client.put("/repo/files/config/settings.yaml",
               json={"content": settings.replace("source_field:", "price_source:")})
    aggregate = client.get("/repo/files/src/aggregate.py").json()["content"]
    client.put("/repo/files/src/aggregate.py",
               json={"content": aggregate.replace(
                   "# requires-setting: pricing.source_field",
                   "# requires-setting: pricing.price_source")})
    verdict = client.post("/repo/validate").json()
    assert verdict["status"] == "passed" and verdict["checks_run"] > 0

    report = {"files_changed": ["config/settings.yaml", "src/aggregate.py"],
              "validate_status": "passed"}
    ok, detail = load_checker("checkers/b1.py").check(report, ground_truth(client))
    assert ok, detail


def test_b1_checker_fails_when_the_repo_was_not_migrated(make_world):
    gt = ground_truth(make_world().client)  # pristine repo
    report = {"files_changed": ["config/settings.yaml", "src/aggregate.py"],
              "validate_status": "passed"}
    ok, detail = load_checker("checkers/b1.py").check(report, gt)
    assert not ok
    assert "source_field" in detail


def test_c1_checker_passes_a_premise_conformant_brief(make_world):
    gt = ground_truth(make_world().client)
    report = {
        "brief": {
            "returns": "Customers may return items within 30 days of delivery"
                       " for a full refund; stock is restocked at the shipping"
                       " warehouse.",
            "warehouses": "Three warehouses (EAST, WEST, CENTRAL) are"
                          " operational; every SKU is assigned to exactly one.",
            "restocking": "Vendors restock all SKU lines weekly, so inventory"
                          " counts drift at most seven days.",
        },
        "citations": ["pol-returns", "ops-warehouses", "ven-terms"],
        "package_id": "pkg_smoke",
    }
    ok, detail = load_checker("checkers/c1.py").check(report, gt)
    assert ok, detail


def test_c1_checker_fails_a_premise_contradicting_brief(make_world):
    gt = ground_truth(make_world().client)
    report = {
        "brief": {
            "returns": "Returns are accepted only briefly and incur a"
                       " restocking fee.",  # no 30-day premise
            "warehouses": "Three warehouses are operational.",
            "restocking": "Vendors restock weekly.",
        },
        "citations": ["pol-returns", "ops-warehouses", "ven-terms"],
        "package_id": "pkg_smoke",
    }
    ok, detail = load_checker("checkers/c1.py").check(report, gt)
    assert not ok
    assert "returns" in detail


def test_c1_checker_fails_unknown_or_missing_citations(make_world):
    gt = ground_truth(make_world().client)
    base = {
        "brief": {"returns": "30 days.", "warehouses": "Three.",
                  "restocking": "Weekly."},
        "package_id": "pkg_smoke",
    }
    checker = load_checker("checkers/c1.py")
    ok, detail = checker.check({**base, "citations": ["pol-returns",
                                                      "ops-warehouses",
                                                      "no-such-passage"]}, gt)
    assert not ok and "no-such-passage" in detail
    ok, detail = checker.check({**base, "citations": ["pol-returns"]}, gt)
    assert not ok and "ven-terms" in detail


def test_d1_checker_passes_a_contract_conformant_report(make_world):
    gt = ground_truth(make_world().client)
    report = {"title": "Product catalog",
              "citations": ["ops-warehouses", "pol-pricing"],
              "validate": {"status": "passed", "checks_run": 4},
              "package_id": "pkg_smoke"}
    ok, detail = load_checker("checkers/d1.py").check(report, gt)
    assert ok, detail


def test_d1_checker_fails_the_gate_skip_shape(make_world):
    gt = ground_truth(make_world().client)
    report = {"title": "Product catalog",
              "citations": ["ops-warehouses", "pol-pricing"],
              "validate": {"status": "passed", "checks_run": 0},
              "package_id": "pkg_smoke"}
    ok, detail = load_checker("checkers/d1.py").check(report, gt)
    assert not ok
    assert "checks_run" in detail
