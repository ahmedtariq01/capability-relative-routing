import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from crr.oracle import ModelOutcome, fixed_policies, matched_cost, opportunity_capture, oracle_frontier, oracle_policy


class OracleTests(unittest.TestCase):
    def setUp(self):
        self.outcomes = (
            ModelOutcome("easy", "cheap", True, 1.0, 10.0),
            ModelOutcome("easy", "strong", True, 4.0, 30.0),
            ModelOutcome("hard", "cheap", False, 1.0, 10.0),
            ModelOutcome("hard", "strong", True, 4.0, 30.0),
            ModelOutcome("miss", "cheap", False, 1.0, 10.0),
            ModelOutcome("miss", "strong", False, 4.0, 30.0),
        )

    def test_oracle_picks_cheapest_successful_model_per_item(self):
        result = oracle_policy(self.outcomes)
        self.assertEqual(result.routes, (("easy", "cheap"), ("hard", "strong"), ("miss", "cheap")))
        self.assertAlmostEqual(result.solved_rate, 2 / 3)
        self.assertAlmostEqual(result.total_cost_dollars, 6.0)

    def test_oracle_frontier_has_matched_quality_costs(self):
        frontier = oracle_frontier(self.outcomes)
        self.assertEqual([(point.solved_count, point.total_cost_dollars) for point in frontier], [(1, 3.0), (2, 6.0)])
        low = matched_cost(frontier, 1 / 3)
        high = matched_cost(frontier, 2 / 3)
        if low is None or high is None:
            self.fail("expected both target qualities on the oracle frontier")
        self.assertAlmostEqual(low, 3.0)
        self.assertAlmostEqual(high, 6.0)

        fixed = {row.policy: row for row in fixed_policies(self.outcomes)}
        self.assertAlmostEqual(fixed["cheap"].solved_rate, 1 / 3)
        self.assertAlmostEqual(fixed["strong"].solved_rate, 2 / 3)
        cost = matched_cost(fixed.values(), 2 / 3)
        if cost is None:
            self.fail("expected a fixed policy at target quality")
        self.assertAlmostEqual(cost, 12.0)

    def test_opportunity_capture_is_fraction_of_available_savings(self):
        self.assertAlmostEqual(opportunity_capture(9.0, 7.0, 6.0), 2 / 3)
        self.assertIsNone(opportunity_capture(5.0, 5.0, 5.0))

    def test_duplicate_item_model_rows_fail_closed(self):
        with self.assertRaises(ValueError):
            fixed_policies(self.outcomes + (self.outcomes[0],))

        with self.assertRaises(ValueError):
            fixed_policies(self.outcomes[:-1])


if __name__ == "__main__":
    unittest.main()
