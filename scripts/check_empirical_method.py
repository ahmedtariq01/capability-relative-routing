"""Offline synthetic integration check. No LAB-Bench text, answers or model calls."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
from crr.empirical import (FEATURE_NAMES, FOLDS, RIDGE, GRADIENT_TOLERANCE, MAX_ITERATIONS,
    METHOD_VERSION, THRESHOLDS, TARGETS, PRIMARY_TARGET, Question, Observation, digest, fit_development, plan_routes)
from crr.analysis import (ANALYSIS_VERSION, EVALUATION_SCOPE, replay, paired_comparison,
                          oracle_opportunity, uniform_mixture)
from empirical_fixtures import fixture


def check_plan():
    plan = json.loads((ROOT / "docs/experiment-01/method-plan.json").read_text())
    actual = {"method_version": METHOD_VERSION, "feature_names": list(FEATURE_NAMES), "folds": FOLDS,
              "ridge": RIDGE, "gradient_tolerance": GRADIENT_TOLERANCE, "max_iterations": MAX_ITERATIONS,
              "thresholds": list(THRESHOLDS), "targets": list(TARGETS), "primary_target": PRIMARY_TARGET,
              "analysis_version": ANALYSIS_VERSION, "evaluation_scope": EVALUATION_SCOPE}
    for key, value in actual.items():
        if plan[key] != value:
            raise ValueError(f"plan/implementation mismatch: {key}")
    return plan


def main():
    plan = check_plan()
    manifest, questions, observations = fixture()
    roster = tuple(m["slot"] for m in manifest["models"])
    fitted = fit_development(manifest, questions, observations)
    if fitted["primary_comparison"]["target"] != plan["primary_target"] or fitted["primary_comparison"]["secondary_target_promotion_allowed"]:
        raise ValueError("primary policy declaration changed")
    # Invent new visible questions, plan first, and only then construct fixture
    # outcomes. None of these IDs or labels comes from the actual benchmark.
    held_questions = tuple(Question(f"test-fixture-{s}-{i}", s, f"test-group-{s}-{i}",
                           "Invented held-out question " + "word " * (i+1), ("a", "bb", "unknown"))
                           for s in ("LitQA2", "ProtocolQA", "SeqQA") for i in range(40))
    route_tables = {family: plan_routes(fitted, held_questions, family, .5) for family in ("category", "crr")}
    if any(table["routes"] is None for table in route_tables.values()):
        raise ValueError("fixture failed to produce the intended selected policies")
    frozen_routes = {family: table["routes_sha256"] for family, table in route_tables.items()}
    held_observations = tuple(Observation(q.item_id, f"model_{j+1}", (i+j) % 5 <= j,
                                         "answered", (j+1)*.01)
                              for i, q in enumerate(held_questions) for j in range(4))
    replays = {family: replay(held_questions, held_observations,
                  {item: (record["model"],) for item, record in table["routes"].items()},
                  {q.item_id: .0001 if family == "category" else .0002 for q in held_questions}, model_roster=roster)
               for family, table in route_tables.items()}
    paired = paired_comparison(replays["category"], replays["crr"], target=.5)
    opportunity = oracle_opportunity(held_questions, held_observations, .5, model_roster=roster)
    uniform_overhead = {q.item_id: .00005 for q in held_questions}
    uniform = uniform_mixture(held_questions, held_observations, model_roster=roster, overhead_usd=uniform_overhead)
    if uniform["model_weights"] != plan["uniform_control"]["model_weights"] or uniform["primary_comparator"]:
        raise ValueError("uniform control differs from its fixed secondary declaration")
    if uniform["n_items"] != 120 or abs(uniform["expected_mean_total_cost_usd"] - .02505) > 1e-12:
        raise ValueError("uniform control lost assigned items or charged the wrong calls")
    if paired["n_items"] != 120 or paired["accuracy_difference_ci"]["valid"] != 5000:
        raise ValueError("paired analysis lost assigned items or resamples")
    if any(digest(table["routes"]) != frozen_routes[family] for family, table in route_tables.items()):
        raise ValueError("analysis changed a committed synthetic route table")
    unknown = (replace(held_observations[0], cost_usd=None),) + held_observations[1:]
    if oracle_opportunity(held_questions, unknown, .5, model_roster=roster)["status"] != "missing_cost":
        raise ValueError("missing cost did not block headroom")
    uniform_unknown = uniform_mixture(held_questions, unknown, model_roster=roster, overhead_usd=uniform_overhead)
    if uniform_unknown["expected_mean_total_cost_usd"] is not None or uniform_unknown["expected_accuracy"] != uniform["expected_accuracy"]:
        raise ValueError("uniform control dropped a missing-cost item or emitted a cost claim")
    print(json.dumps({"check": "synthetic_empirical_method_pipeline", "passed": True,
        "scope": "generated fixtures only; not benchmark/model/backend evidence",
        "method_plan_sha256": digest(plan), "development_items": 60, "synthetic_test_items": 120,
        "model_slots": 4, "source_group_folds": 5, "paired_resamples": 5000,
        "oracle_status": opportunity["status"], "missing_cost_guard": "passed",
        "uniform_control": {"status": uniform["status"], "model_weights": uniform["model_weights"],
                            "n_items": uniform["n_items"], "missing_cost_guard": "passed"},
        "primary_target": fitted["primary_comparison"]["target"], "integration_target_role": "secondary",
        "provider_calls": 0, "actual_held_out_outcomes_loaded": 0}, indent=2))


if __name__ == "__main__":
    main()
