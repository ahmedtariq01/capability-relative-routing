"""Finite-matrix replay and paired uncertainty for already-frozen policies.

These functions do not fit or select a router from test outcomes. The oracle
comparison explicitly selects after outcomes and is only a retrospective bound.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math
import random
from statistics import mean

from .empirical import Observation, Question, nonnegative, validate_matrix
from .oracle import ModelOutcome, fixed_policies, matched_cost, oracle_frontier

ANALYSIS_VERSION = "crr-analysis-v0.2"
EVALUATION_SCOPE = "single_draw_finite_matrix_conditional_on_provider_stochasticity"


@dataclass(frozen=True)
class PolicyRow:
    item_id: str
    subset: str
    source_group: str
    solved: float
    cost_usd: float | None
    models_called: tuple[str, ...]
    terminal_status: str = "unknown"

    def __post_init__(self):
        if not all(isinstance(x, str) and x for x in (self.item_id, self.subset, self.source_group)):
            raise ValueError("policy row needs item, subset and source-group identifiers")
        if self.terminal_status not in {"answered", "abstained", "malformed", "failed", "unknown"}:
            raise ValueError("invalid terminal status")
        if type(self.solved) not in (int, float, bool) or not math.isfinite(self.solved) or not 0 <= self.solved <= 1:
            raise ValueError("invalid correctness value")
        if self.cost_usd is not None:
            nonnegative(self.cost_usd, "policy cost")


def replay(questions: tuple[Question, ...], observations: tuple[Observation, ...],
           routes: dict[str, tuple[str, ...]], overhead_usd: dict[str, float | None], *,
           model_roster: tuple[str, ...]) -> tuple[PolicyRow, ...]:
    """Charge selected calls plus feature/decision/dispatch cost for every item.

    Sequential policies return the final attempted answer, even if it fails.
    Each Observation already includes every retry for that item/model call.
    """
    ids = {q.item_id for q in questions}
    models = model_roster
    index = validate_matrix(questions, observations, models)
    if set(routes) != ids or set(overhead_usd) != ids:
        raise ValueError("route and overhead records must cover every assigned item")
    rows = []
    for q in questions:
        route = routes[q.item_id]
        if not route or len(route) != len(set(route)) or not set(route) <= set(models):
            raise ValueError("route must contain known, nonduplicated models")
        calls = [index[q.item_id, model] for model in route]
        overhead = overhead_usd[q.item_id]
        if overhead is not None:
            nonnegative(overhead, "routing overhead")
        cost = None if overhead is None or any(r.cost_usd is None for r in calls) else overhead + sum(r.cost_usd for r in calls)
        rows.append(PolicyRow(q.item_id, q.subset, q.source_group, float(calls[-1].solved), cost, route,
                              calls[-1].response_status))
    return tuple(rows)


def cascade_routes(observations: tuple[Observation, ...], cheap: str, strong: str) -> dict[str, tuple[str, ...]]:
    """Observable gate only. An answered-but-wrong response never triggers it."""
    if cheap == strong:
        raise ValueError("cascade requires two distinct, development-selected models")
    rows = [r for r in observations if r.model == cheap]
    if not rows or len(rows) != len({r.item_id for r in rows}):
        raise ValueError("missing or duplicate cheap-model observations")
    return {r.item_id: (cheap,) if r.response_status == "answered" else (cheap, strong) for r in rows}


def fixed_selection(observations: tuple[Observation, ...], target: float, *, model_roster: tuple[str, ...]) -> dict:
    """Development-only caller supplies a previously validated complete matrix."""
    if type(target) not in (float, int) or not math.isfinite(target) or not 0 <= target <= 1:
        raise ValueError("target must be in [0,1]")
    grouped = defaultdict(list)
    for r in observations:
        grouped[r.model].append(r)
    if not model_roster or len(model_roster) != len(set(model_roster)) or set(grouped) != set(model_roster):
        raise ValueError("outcomes do not match the model roster")
    if not grouped or len({r.item_id for r in observations}) * len(grouped) != len(observations):
        raise ValueError("incomplete fixed-model matrix")
    ids = {r.item_id for r in observations}
    if any(len(rows) != len(ids) or {r.item_id for r in rows} != ids for rows in grouped.values()):
        raise ValueError("duplicate or missing fixed-model rows")
    if any(r.cost_usd is None for r in observations):
        return {"status": "missing_cost", "selected": None}
    candidates = [{"model": model, "accuracy": mean(r.solved for r in rows),
                   "mean_cost_usd": mean(r.cost_usd for r in rows)} for model, rows in grouped.items()]
    eligible = [c for c in candidates if c["accuracy"] >= target]
    return {"status": "selected" if eligible else "unattainable_on_development",
            "selected": min(eligible, key=lambda c: (c["mean_cost_usd"], -c["accuracy"], c["model"])) if eligible else None}


def oracle_opportunity(questions: tuple[Question, ...], observations: tuple[Observation, ...], target: float, *,
                       model_roster: tuple[str, ...]) -> dict:
    """All individual fixed models vs the deterministic oracle. Inference cost only.

    Both sides use the same all-attempt, frozen-price costs. Unknown costs block
    dollar claims. Fixed-model mixtures have a separate expected frontier.
    """
    if type(target) not in (int, float) or not math.isfinite(target) or not 0 <= target <= 1:
        raise ValueError("target must be in [0,1]")
    validate_matrix(questions, observations, model_roster)
    base = {"target": target, "n_items": len(questions), "selection": "retrospective",
            "interpretation": "inference_cost_only_retrospective_upper_bound",
            "evaluation_scope": EVALUATION_SCOPE,
            "cost_basis": "frozen_price_all_attempt_inference_only", "mixtures_in_primary": False,
            "oracle_routing_cost_assumption_usd": 0.0}
    if any(r.cost_usd is None for r in observations):
        return {**base, "status": "missing_cost", "opportunity_usd": None,
                "missing_cost_cells": sum(r.cost_usd is None for r in observations)}
    matrix = tuple(ModelOutcome(r.item_id, r.model, r.solved, r.cost_usd) for r in observations)
    fixed = matched_cost(fixed_policies(matrix), target)
    oracle = matched_cost(oracle_frontier(matrix), target)
    status = "available" if fixed is not None and oracle is not None else "unattainable_target"
    return {**base, "status": status, "fixed_cost_usd": fixed, "oracle_cost_usd": oracle,
            "opportunity_usd": fixed - oracle if status == "available" else None}


def mixture_frontier(questions: tuple[Question, ...], observations: tuple[Observation, ...], *,
                     model_roster: tuple[str, ...]) -> list[dict]:
    """Secondary expected points for all 5%-grid two-model fixed mixtures.

    These integrate exogenous randomisation. They are not realised integer-score
    policies and never enter the primary deterministic oracle denominator.
    """
    models = tuple(sorted(model_roster))
    validate_matrix(questions, observations, models)
    grouped = {model: [r for r in observations if r.model == model] for model in models}
    points = []
    for i, left in enumerate(models):
        for right in models[i + 1:]:
            for k in range(21):
                weight = k / 20
                portions = [(weight, grouped[left]), (1 - weight, grouped[right])]
                active = [(w, rows) for w, rows in portions if w > 0]
                cost = None if any(r.cost_usd is None for _, rows in active for r in rows) else sum(
                    w * mean(r.cost_usd for r in rows) for w, rows in active)
                points.append({"models": [left, right], "left_weight": weight,
                    "expected_accuracy": sum(w * mean(r.solved for r in rows) for w, rows in active),
                    "expected_mean_inference_cost_usd": cost, "status": "secondary_expected_randomisation"})
    return points


def uniform_mixture(questions: tuple[Question, ...], observations: tuple[Observation, ...], *,
                    model_roster: tuple[str, ...], overhead_usd: dict[str, float | None]) -> dict:
    """Secondary expectation of selecting one model uniformly for each item.

    Weights are fixed by the declared roster, independently of inputs, outcomes
    and costs. The complete matrix integrates routing randomisation analytically;
    it does not average over new provider draws or call all models at deployment.
    Overhead is the measured expected selection/dispatch cost per assigned item.
    Each cell's inference cost already includes every selected-model attempt.
    """
    models = tuple(sorted(model_roster))
    index = validate_matrix(questions, observations, models)
    if set(overhead_usd) != {q.item_id for q in questions}:
        raise ValueError("uniform overhead records must cover every assigned item")
    for overhead in overhead_usd.values():
        if overhead is not None:
            nonnegative(overhead, "uniform selection and dispatch overhead")
    items = []
    for q in sorted(questions, key=lambda q: q.item_id):
        calls = [index[q.item_id, model] for model in models]
        inference = None if any(r.cost_usd is None for r in calls) else mean(r.cost_usd for r in calls)
        overhead = overhead_usd[q.item_id]
        items.append({"item_id": q.item_id, "subset": q.subset,
                      "expected_accuracy": mean(r.solved for r in calls),
                      "expected_mean_inference_cost_usd": inference,
                      "expected_mean_routing_overhead_usd": overhead,
                      "expected_mean_total_cost_usd": None if inference is None or overhead is None else inference + overhead,
                      "missing_cost_cells": sum(r.cost_usd is None for r in calls)})
    fields = ("expected_accuracy", "expected_mean_inference_cost_usd",
              "expected_mean_routing_overhead_usd", "expected_mean_total_cost_usd")
    def summary(rows):
        return {"assigned": len(rows),
                **{field: mean(r[field] for r in rows) if all(r[field] is not None for r in rows) else None
                   for field in fields},
                "missing_cost_cells": sum(r["missing_cost_cells"] for r in rows),
                "missing_overhead_items": sum(r["expected_mean_routing_overhead_usd"] is None for r in rows)}
    subsets = {subset: summary([r for r in items if r["subset"] == subset])
               for subset in sorted({q.subset for q in questions})}
    macro = {field: mean(s[field] for s in subsets.values()) if all(s[field] is not None for s in subsets.values()) else None
             for field in fields}
    return {"analysis_version": ANALYSIS_VERSION, "status": "secondary_expected_randomisation",
            "evaluation_scope": EVALUATION_SCOPE, "selection": "fixed_uniform_independent_of_item_and_outcomes",
            "model_weights": {model: 1 / len(models) for model in models}, "selected_models_per_item": 1,
            "n_items": len(questions), "subset_weights": "equal", "subset_results": subsets, **macro,
            "missing_cost_cells": sum(r["missing_cost_cells"] for r in items),
            "missing_overhead_items": sum(r["expected_mean_routing_overhead_usd"] is None for r in items),
            "cost_basis": "frozen_price_all_attempt_inference_plus_selection_and_dispatch",
            "primary_comparator": False,
            "limitations": "Expected routing randomisation on the observed matrix, not a realised random route or repeated provider sample."}


def _macro(rows: list[PolicyRow], field: str) -> float:
    groups = defaultdict(list)
    for row in rows:
        groups[row.subset].append(getattr(row, field))
    return mean(mean(values) for values in groups.values())


def _interval(values: list[float], total: int) -> dict:
    if not values:
        return {"low": None, "high": None, "status": "unavailable", "valid": 0, "invalid": total}
    values.sort()
    def percentile(p):
        x = (len(values) - 1) * p
        lo, hi = math.floor(x), math.ceil(x)
        return values[lo] + (x - lo) * (values[hi] - values[lo])
    lo, hi = percentile(.025), percentile(.975)
    return {"low": lo, "high": hi, "status": "degenerate" if math.isclose(lo, hi, abs_tol=1e-12) else "ok",
            "valid": len(values), "invalid": total - len(values)}


def paired_comparison(category: tuple[PolicyRow, ...], crr: tuple[PolicyRow, ...], *,
                      target: float, resamples: int = 5000, seed: int = 261026) -> dict:
    """Equal subset weights, paired source-cluster bootstrap, no policy refit.

    Returns savings = category minus CRR and accuracy difference = CRR minus
    category. Even a passing exploratory zero-loss rule is not a powered
    confirmatory non-inferiority result. Degenerate intervals remain explicit.
    """
    if type(target) not in (float, int) or not math.isfinite(target) or not 0 <= target <= 1:
        raise ValueError("invalid target")
    if type(resamples) is not int or resamples < 2:
        raise ValueError("at least two resamples required")
    a, b = {r.item_id: r for r in category}, {r.item_id: r for r in crr}
    if not a or len(a) != len(category) or len(b) != len(crr) or set(a) != set(b):
        raise ValueError("paired policies must cover the same unique assigned IDs")
    groups = defaultdict(lambda: defaultdict(list))
    source_subsets = defaultdict(set)
    for item in sorted(a):
        if (a[item].subset, a[item].source_group) != (b[item].subset, b[item].source_group):
            raise ValueError("paired metadata mismatch")
        groups[a[item].subset][a[item].source_group].append(item)
        source_subsets[a[item].source_group].add(a[item].subset)
    if any(len(subsets) != 1 for subsets in source_subsets.values()):
        raise ValueError("source cluster crosses categories")
    known_cost = all(r.cost_usd is not None for r in (*category, *crr))
    accuracy_a, accuracy_b = _macro(list(category), "solved"), _macro(list(crr), "solved")
    cost_delta = _macro(list(category), "cost_usd") - _macro(list(crr), "cost_usd") if known_cost else None
    accuracy_samples, cost_samples = [], []
    rng = random.Random(seed)
    for _ in range(resamples):
        ids = []
        for subset in sorted(groups):
            keys = sorted(groups[subset])
            for key in rng.choices(keys, k=len(keys)):
                ids.extend(groups[subset][key])
        rows_a, rows_b = [a[i] for i in ids], [b[i] for i in ids]
        accuracy_samples.append(_macro(rows_b, "solved") - _macro(rows_a, "solved"))
        if known_cost:
            cost_samples.append(_macro(rows_a, "cost_usd") - _macro(rows_b, "cost_usd"))
    accuracy_ci = _interval(accuracy_samples, resamples)
    savings_ci = _interval(cost_samples, resamples)
    enough_groups = all(len(v) >= 2 for v in groups.values())
    warnings = []
    if not known_cost:
        warnings.append("Missing selected-call or routing-overhead costs block dollar savings.")
    if not enough_groups:
        warnings.append("Fewer than two source clusters in a subset: uncertainty is not estimable there.")
    if accuracy_ci["status"] == "degenerate" or savings_ci["status"] == "degenerate":
        warnings.append("Zero-width bootstrap interval: report degeneracy, not certainty.")
    both_targets = min(accuracy_a, accuracy_b) >= target
    if not both_targets:
        warnings.append("At least one frozen policy missed the declared target on held-out items.")
    gate = (both_targets and enough_groups and accuracy_ci["status"] == "ok" and
            savings_ci["status"] == "ok" and accuracy_ci["low"] >= 0 and savings_ci["low"] > 0)
    def summary(rows):
        return {"assigned": len(rows), "successes": sum(r.solved for r in rows),
                "accuracy": mean(r.solved for r in rows),
                "mean_cost_usd": mean(r.cost_usd for r in rows) if all(r.cost_usd is not None for r in rows) else None,
                "terminal_status_counts": {status: sum(r.terminal_status == status for r in rows)
                                           for status in sorted({r.terminal_status for r in rows})}}
    subset_results = {s: {"category": summary([r for r in category if r.subset == s]),
                          "crr": summary([r for r in crr if r.subset == s])} for s in sorted(groups)}
    return {"analysis_version": ANALYSIS_VERSION, "evaluation_scope": EVALUATION_SCOPE,
            "cost_basis": "total_deployable_feature_prediction_dispatch_and_selected_model_attempts",
            "n_items": len(a), "target": target, "subset_weights": "equal",
            "subset_results": subset_results,
            "category_successes": sum(r.solved for r in category), "crr_successes": sum(r.solved for r in crr),
            "category_mean_cost_usd": _macro(list(category), "cost_usd") if all(r.cost_usd is not None for r in category) else None,
            "crr_mean_cost_usd": _macro(list(crr), "cost_usd") if all(r.cost_usd is not None for r in crr) else None,
            "n_source_clusters": {s: len(v) for s, v in groups.items()},
            "category_accuracy": accuracy_a, "crr_accuracy": accuracy_b,
            "accuracy_difference": accuracy_b - accuracy_a, "accuracy_difference_ci": accuracy_ci,
            "mean_saving_usd": cost_delta, "mean_saving_ci": savings_ci,
            "missing_cost_items": sum(a[i].cost_usd is None or b[i].cost_usd is None for i in a),
            "both_targets_met": both_targets, "exploratory_zero_loss_rule_met": gate,
            "confirmatory_matched_quality_claim": False,
            "resamples": resamples, "seed": seed, "warnings": warnings,
            "limitations": "Single-draw finite-matrix evaluation conditional on provider stochasticity and the fixed development fit. Bootstrap intervals exclude training and provider-sampling uncertainty."}
