from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class ModelProfile:
    name: str
    capabilities: Mapping[str, float]
    inference_cost_dollars: float
    inference_latency_ms: float

    def estimated_quality(self, problem: "Problem") -> float:
        if not problem.required_capabilities:
            raise ValueError("problem must require at least one capability")
        missing = set(problem.required_capabilities) - set(self.capabilities)
        if missing:
            return 0.0
        return sum(
            self.capabilities[name] * weight
            for name, weight in problem.required_capabilities.items()
        ) / sum(problem.required_capabilities.values())


@dataclass(frozen=True)
class Problem:
    item_id: str
    required_capabilities: Mapping[str, float]
    quality_threshold: float


@dataclass(frozen=True)
class RouterCost:
    dollars: float = 0.0
    latency_ms: float = 0.0
    tokens: int = 0


@dataclass(frozen=True)
class RouteDecision:
    item_id: str
    selected_model: str
    estimated_quality: float
    total_cost_dollars: float
    total_latency_ms: float
    routing_cost: RouterCost
    escalated: bool = False


def route(
    problem: Problem,
    models: tuple[ModelProfile, ...],
    routing_cost: RouterCost = RouterCost(),
    *,
    confidence_margin: float = 0.0,
    escalation_model: ModelProfile | None = None,
) -> RouteDecision:
    """Select the cheapest predicted viable model, optionally escalating ties.

    This is deliberately a transparent baseline. It does not claim calibrated
    probabilities: confidence_margin is a deterministic uncertainty proxy used
    only by the synthetic fixture.
    """
    if not models:
        raise ValueError("at least one candidate model is required")
    viable = [(m, m.estimated_quality(problem)) for m in models]
    viable = [(m, q) for m, q in viable if q >= problem.quality_threshold]
    if not viable:
        if escalation_model is None:
            raise ValueError("no candidate model meets the quality threshold")
        selected, quality, escalated = escalation_model, escalation_model.estimated_quality(problem), True
    else:
        viable.sort(key=lambda pair: (pair[0].inference_cost_dollars, pair[0].inference_latency_ms, pair[0].name))
        selected, quality = viable[0]
        escalated = False
        if escalation_model is not None and len(viable) > 1:
            margin = viable[1][1] - quality
            if margin < confidence_margin:
                selected, quality, escalated = escalation_model, escalation_model.estimated_quality(problem), True
    return RouteDecision(
        item_id=problem.item_id,
        selected_model=selected.name,
        estimated_quality=quality,
        total_cost_dollars=selected.inference_cost_dollars + routing_cost.dollars,
        total_latency_ms=selected.inference_latency_ms + routing_cost.latency_ms,
        routing_cost=routing_cost,
        escalated=escalated,
    )
