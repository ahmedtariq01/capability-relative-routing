from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class ModelProfile:
    name: str
    capabilities: Mapping[str, float]
    inference_cost_dollars: float
    inference_latency_ms: float
    # This is an explicit uncertainty estimate, not a score-gap proxy. In the
    # empirical phase it must be calibrated within development data only.
    uncertainty: Mapping[str, float] = field(default_factory=dict)

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

    def estimated_uncertainty(self, problem: "Problem") -> float:
        """Return the profile's uncertainty estimate for this problem.

        Missing uncertainty metadata is conservatively treated as 1.0. The
        value is a routing signal only until calibration evidence exists.
        """
        if not problem.required_capabilities:
            raise ValueError("problem must require at least one capability")
        return sum(
            self.uncertainty.get(name, 1.0) * weight
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
    estimated_uncertainty: float
    total_cost_dollars: float
    total_latency_ms: float
    routing_cost: RouterCost
    escalated: bool = False
    threshold_met: bool = True


def route(
    problem: Problem,
    models: tuple[ModelProfile, ...],
    routing_cost: RouterCost = RouterCost(),
    *,
    uncertainty_threshold: float | None = None,
    escalation_model: ModelProfile | None = None,
) -> RouteDecision:
    """Select the cheapest predicted viable model and optionally escalate.

    Quality estimates and uncertainty estimates are separate quantities. The
    uncertainty threshold is intentionally not called confidence: calibration
    within development data is required before interpreting it as one.
    """
    if not models:
        raise ValueError("at least one candidate model is required")
    viable = [(m, m.estimated_quality(problem)) for m in models]
    viable = [(m, q) for m, q in viable if q >= problem.quality_threshold]
    if not viable:
        if escalation_model is None:
            raise ValueError("no candidate model meets the quality threshold")
        selected = escalation_model
        quality = escalation_model.estimated_quality(problem)
        escalated = True
    else:
        viable.sort(key=lambda pair: (pair[0].inference_cost_dollars, pair[0].inference_latency_ms, pair[0].name))
        selected, quality = viable[0]
        escalated = False
        if (
            escalation_model is not None
            and uncertainty_threshold is not None
            and selected.estimated_uncertainty(problem) > uncertainty_threshold
        ):
            selected, quality, escalated = escalation_model, escalation_model.estimated_quality(problem), True
    uncertainty = selected.estimated_uncertainty(problem)
    return RouteDecision(
        item_id=problem.item_id,
        selected_model=selected.name,
        estimated_quality=quality,
        estimated_uncertainty=uncertainty,
        total_cost_dollars=selected.inference_cost_dollars + routing_cost.dollars,
        total_latency_ms=selected.inference_latency_ms + routing_cost.latency_ms,
        routing_cost=routing_cost,
        escalated=escalated,
        threshold_met=quality >= problem.quality_threshold,
    )
