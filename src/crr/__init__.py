"""Capability-Relative Routing research prototype."""

from .oracle import ModelOutcome, PolicySummary, fixed_policies, matched_cost, opportunity_capture, oracle_policy
from .router import ModelProfile, Problem, RouteDecision, RouterCost, route

__all__ = [
    "ModelProfile", "Problem", "RouteDecision", "RouterCost", "route",
    "ModelOutcome", "PolicySummary", "fixed_policies", "matched_cost",
    "opportunity_capture", "oracle_policy",
]
