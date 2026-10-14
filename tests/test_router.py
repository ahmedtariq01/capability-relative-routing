import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from crr import ModelProfile, Problem, RouterCost, route


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.models = (
            ModelProfile("cheap", {"retrieval": 0.86}, 0.1, 10.0),
            ModelProfile("strong", {"retrieval": 0.95}, 0.5, 20.0),
        )
        self.overhead = RouterCost(dollars=0.01, latency_ms=2.0, tokens=5)

    def test_selects_cheapest_viable_model_and_charges_overhead(self):
        decision = route(Problem("a", {"retrieval": 1.0}, 0.80), self.models, self.overhead)
        self.assertEqual(decision.selected_model, "cheap")
        self.assertAlmostEqual(decision.total_cost_dollars, 0.11)
        self.assertAlmostEqual(decision.total_latency_ms, 12.0)

    def test_stronger_model_is_selected_when_threshold_requires_it(self):
        decision = route(Problem("b", {"retrieval": 1.0}, 0.90), self.models, self.overhead)
        self.assertEqual(decision.selected_model, "strong")
        self.assertFalse(decision.escalated)

    def test_missing_viability_is_fail_closed(self):
        with self.assertRaises(ValueError):
            route(Problem("c", {"reasoning": 1.0}, 0.80), self.models, self.overhead)

    def test_uncertainty_escalation_is_explicit(self):
        near = (
            ModelProfile("cheap", {"retrieval": 0.81}, 0.1, 10.0),
            ModelProfile("near", {"retrieval": 0.82}, 0.2, 15.0),
        )
        decision = route(
            Problem("d", {"retrieval": 1.0}, 0.70),
            near,
            self.overhead,
            confidence_margin=0.05,
            escalation_model=self.models[1],
        )
        self.assertEqual(decision.selected_model, "strong")
        self.assertTrue(decision.escalated)


if __name__ == "__main__":
    unittest.main()
