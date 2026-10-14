from __future__ import annotations

from dataclasses import dataclass
from math import isclose
from typing import Iterable, Mapping


@dataclass(frozen=True)
class ModelOutcome:
    """Observed outcome for one model on one item.

    The oracle consumes already-scored outcomes. It does not claim to predict
    them and should never be confused with a deployable routing policy.
    """

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


def _validate(outcomes: Iterable[ModelOutcome]) -> tuple[ModelOutcome, ...]:
    rows = tuple(outcomes)
    if not rows:
        raise ValueError("at least one model outcome is required")
    if any(row.cost_dollars < 0 or row.latency_ms < 0 for row in rows):
        raise ValueError("cost and latency must be non-negative")
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


def oracle_policy(outcomes: Iterable[ModelOutcome]) -> PolicySummary:
    """Choose the cheapest successful model per item.

    If no model solves an item, the cheapest available model is still routed so
    the oracle accounts for the complete item set and records the miss.
    """
    rows = _validate(outcomes)
    items = tuple(dict.fromkeys(row.item_id for row in rows))
    chosen: list[ModelOutcome] = []
    for item_id in items:
        candidates = [row for row in rows if row.item_id == item_id]
        successful = [row for row in candidates if row.solved]
        chosen.append(min(successful or candidates, key=lambda row: (row.cost_dollars, row.latency_ms, row.model_name)))
    return PolicySummary(
        policy="oracle",
        solved_rate=sum(row.solved for row in chosen) / len(items),
        total_cost_dollars=sum(row.cost_dollars for row in chosen),
        total_latency_ms=sum(row.latency_ms for row in chosen),
        routes=tuple((row.item_id, row.model_name) for row in chosen),
    )


def matched_cost(summary: Iterable[PolicySummary], quality: float) -> float | None:
    """Return minimum cost among policies meeting a solved-rate target."""
    eligible = [row.total_cost_dollars for row in summary if row.solved_rate >= quality]
    return min(eligible) if eligible else None


def opportunity_capture(best_fixed: float, routed: float, oracle: float) -> float | None:
    """Fraction of oracle savings captured by a routed policy.

    Returns None when the oracle offers no measurable savings, avoiding a
    misleading division by zero in homogeneous or cost-neutral settings.
    """
    denominator = best_fixed - oracle
    if isclose(denominator, 0.0, abs_tol=1e-12):
        return None
    return (best_fixed - routed) / denominator
