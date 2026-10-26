from __future__ import annotations

from dataclasses import dataclass
from math import isclose, isfinite
from typing import Iterable


@dataclass(frozen=True)
class ModelOutcome:
    """Observed outcome for one model on one item."""

    item_id: str
    model_name: str
    solved: bool
    cost_dollars: float
    latency_ms: float = 0.0


@dataclass(frozen=True)
class PolicySummary:
    policy: str
    solved_rate: float
    total_cost_dollars: float
    total_latency_ms: float
    routes: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class FrontierPoint:
    solved_count: int
    total_items: int
    solved_rate: float
    total_cost_dollars: float
    total_latency_ms: float
    routes: tuple[tuple[str, str], ...]


def _validate(outcomes: Iterable[ModelOutcome]) -> tuple[ModelOutcome, ...]:
    rows = tuple(outcomes)
    if not rows:
        raise ValueError("at least one model outcome is required")
    if any(type(value) not in (int, float) or not isfinite(value) or value < 0
           for row in rows for value in (row.cost_dollars, row.latency_ms)):
        raise ValueError("cost and latency must be known, finite and non-negative")
    if any(type(row.solved) is not bool for row in rows):
        raise ValueError("solved must be boolean")
    keys = [(row.item_id, row.model_name) for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate outcome for an item/model pair")
    items = {row.item_id for row in rows}
    models = {row.model_name for row in rows}
    for item_id in items:
        names = {row.model_name for row in rows if row.item_id == item_id}
        if names != models:
            raise ValueError(f"incomplete model matrix for item {item_id!r}")
    return rows


def fixed_policies(outcomes: Iterable[ModelOutcome]) -> tuple[PolicySummary, ...]:
    rows = _validate(outcomes)
    items = tuple(dict.fromkeys(row.item_id for row in rows))
    model_names = sorted({row.model_name for row in rows})
    summaries = []
    for model_name in model_names:
        selected = [row for row in rows if row.model_name == model_name]
        summaries.append(
            PolicySummary(
                policy=model_name,
                solved_rate=sum(row.solved for row in selected) / len(items),
                total_cost_dollars=sum(row.cost_dollars for row in selected),
                total_latency_ms=sum(row.latency_ms for row in selected),
                routes=tuple((item_id, model_name) for item_id in items),
            )
        )
    return tuple(summaries)


def oracle_frontier(outcomes: Iterable[ModelOutcome]) -> tuple[FrontierPoint, ...]:
    """Build the cost frontier by buying successful upgrades incrementally.

    The baseline runs the cheapest model on every item. For each item that the
    baseline misses, the oracle can purchase the cheapest successful upgrade.
    Those upgrades are sorted by incremental cost, so every returned point is
    the cheapest oracle policy for the successes it has accumulated.
    """
    rows = _validate(outcomes)
    items = tuple(dict.fromkeys(row.item_id for row in rows))
    base: list[ModelOutcome] = []
    upgrades: list[tuple[float, ModelOutcome]] = []
    for item_id in items:
        candidates = [row for row in rows if row.item_id == item_id]
        cheapest = min(candidates, key=lambda row: (row.cost_dollars, row.latency_ms, row.model_name))
        base.append(cheapest)
        successful = [row for row in candidates if row.solved]
        if successful and not cheapest.solved:
            success = min(successful, key=lambda row: (row.cost_dollars, row.latency_ms, row.model_name))
            upgrades.append((success.cost_dollars - cheapest.cost_dollars, success))

    routes = {row.item_id: row for row in base}
    total_cost = sum(row.cost_dollars for row in base)
    total_latency = sum(row.latency_ms for row in base)
    solved_count = sum(row.solved for row in base)
    points = [
        FrontierPoint(
            solved_count=solved_count,
            total_items=len(items),
            solved_rate=solved_count / len(items),
            total_cost_dollars=total_cost,
            total_latency_ms=total_latency,
            routes=tuple((item_id, routes[item_id].model_name) for item_id in items),
        )
    ]
    for delta, success in sorted(upgrades, key=lambda pair: (pair[0], pair[1].item_id, pair[1].model_name)):
        total_cost += delta
        total_latency += success.latency_ms - routes[success.item_id].latency_ms
        routes[success.item_id] = success
        solved_count += 1
        points.append(
            FrontierPoint(
                solved_count=solved_count,
                total_items=len(items),
                solved_rate=solved_count / len(items),
                total_cost_dollars=total_cost,
                total_latency_ms=total_latency,
                routes=tuple((item_id, routes[item_id].model_name) for item_id in items),
            )
        )
    return tuple(points)


def oracle_policy(outcomes: Iterable[ModelOutcome]) -> PolicySummary:
    """Return the maximum-quality endpoint of the oracle frontier."""
    point = oracle_frontier(outcomes)[-1]
    return PolicySummary("oracle", point.solved_rate, point.total_cost_dollars, point.total_latency_ms, point.routes)


def matched_cost(summary: Iterable[PolicySummary | FrontierPoint], quality: float) -> float | None:
    """Return minimum cost among policies/frontier points meeting a target."""
    if type(quality) not in (float, int) or not isfinite(quality) or not 0 <= quality <= 1:
        raise ValueError("quality target must be in [0, 1]")
    eligible = [row.total_cost_dollars for row in summary if row.solved_rate >= quality]
    return min(eligible) if eligible else None


def opportunity_capture(best_fixed: float, routed: float, oracle: float) -> float | None:
    """Fraction of oracle savings captured by a routed policy."""
    if any(type(v) not in (int, float) or not isfinite(v) or v < 0 for v in (best_fixed, routed, oracle)):
        raise ValueError("capture requires known, finite and non-negative costs")
    denominator = best_fixed - oracle
    if denominator < 0 or isclose(denominator, 0.0, abs_tol=1e-12):
        return None
    return (best_fixed - routed) / denominator
