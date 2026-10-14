"""Capability-Relative Routing research prototype."""

from .oracle import FrontierPoint, ModelOutcome, PolicySummary, fixed_policies, matched_cost, opportunity_capture, oracle_frontier, oracle_policy
from .router import ModelProfile, Problem, RouteDecision, RouterCost, route

__all__ = [
    "ModelProfile", "Problem", "RouteDecision", "RouterCost", "route",
    "ModelOutcome", "PolicySummary", "FrontierPoint", "fixed_policies", "matched_cost",
    "opportunity_capture", "oracle_frontier", "oracle_policy",
]
