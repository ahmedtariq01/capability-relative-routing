from dataclasses import replace
import itertools
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from crr.empirical import Observation, Question
from crr.analysis import (PolicyRow, replay, cascade_routes, fixed_selection, oracle_opportunity,
                          mixture_frontier, paired_comparison)
from crr.oracle import ModelOutcome, oracle_frontier, matched_cost, opportunity_capture


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.roster = ("cheap", "strong")
        self.questions = tuple(Question(str(i), "SeqQA", str(i), "text", ("a", "b")) for i in range(3))
        self.observations = (Observation("0", "cheap", True, "answered", 1),
            Observation("0", "strong", True, "answered", 4),
            Observation("1", "cheap", False, "answered", 1),
            Observation("1", "strong", True, "answered", 4),
            Observation("2", "cheap", False, "failed", 2),
            Observation("2", "strong", False, "abstained", 4))

    def test_replay_charges_all_attempts_and_routing(self):
        routes = cascade_routes(self.observations, "cheap", "strong")
        self.assertEqual(routes["1"], ("cheap",))  # wrong answer is not an observable gate
        self.assertEqual(routes["2"], ("cheap", "strong"))
        result = replay(self.questions, self.observations, routes, {str(i): .25 for i in range(3)}, model_roster=self.roster)
        self.assertEqual([r.cost_usd for r in result], [1.25, 1.25, 6.25])
        self.assertEqual(sum(r.solved for r in result), 1)

    def test_missing_cost_is_null_not_zero_or_dropped(self):
        obs = (replace(self.observations[0], cost_usd=None),) + self.observations[1:]
        result = replay(self.questions, obs, {str(i): ("cheap",) for i in range(3)}, {str(i): .1 for i in range(3)}, model_roster=self.roster)
        self.assertEqual(len(result), 3)
        self.assertIsNone(result[0].cost_usd)
        self.assertEqual(oracle_opportunity(self.questions, obs, .5, model_roster=self.roster)["status"], "missing_cost")

    def test_missing_overhead_blocks_dollar_claim(self):
        rows = replay(self.questions, self.observations, {str(i): ("cheap",) for i in range(3)},
                      {str(i): None for i in range(3)}, model_roster=self.roster)
        result = paired_comparison(rows, rows, target=.5, resamples=50)
        self.assertIsNone(result["mean_saving_usd"])
        self.assertEqual(result["mean_saving_ci"]["invalid"], 50)
        self.assertFalse(result["confirmatory_matched_quality_claim"])

    def test_incomplete_routes_are_rejected(self):
        with self.assertRaises(ValueError):
            replay(self.questions, self.observations, {"0": ("cheap",)}, {str(i): 0 for i in range(3)}, model_roster=self.roster)

    def test_entire_missing_model_column_is_rejected(self):
        observations = tuple(r for r in self.observations if r.model == "cheap")
        with self.assertRaises(ValueError):
            oracle_opportunity(self.questions, observations, .5, model_roster=self.roster)
        with self.assertRaises(ValueError):
            fixed_selection(observations, .5, model_roster=self.roster)
        with self.assertRaises(ValueError):
            replay(self.questions, observations, {str(i): ("cheap",) for i in range(3)},
                   {str(i): 0 for i in range(3)}, model_roster=self.roster)

    def test_per_subset_counts_keep_terminal_failures(self):
        rows = replay(self.questions, self.observations, {str(i): ("cheap",) for i in range(3)},
                      {str(i): 0 for i in range(3)}, model_roster=self.roster)
        report = paired_comparison(rows, rows, target=.5, resamples=50)
        summary = report["subset_results"]["SeqQA"]["category"]
        self.assertEqual(summary["assigned"], 3)
        self.assertEqual(summary["successes"], 1)
        self.assertEqual(summary["terminal_status_counts"]["failed"], 1)

    def test_fixed_baseline_is_selected_at_target(self):
        self.assertEqual(fixed_selection(self.observations, 2/3, model_roster=self.roster)["selected"]["model"], "strong")
        self.assertIsNone(fixed_selection(self.observations, 1, model_roster=self.roster)["selected"])

    def test_oracle_headroom_has_distinct_retrospective_scope(self):
        result = oracle_opportunity(self.questions, self.observations, 2/3, model_roster=self.roster)
        self.assertEqual(result["fixed_cost_usd"], 12)
        self.assertEqual(result["oracle_cost_usd"], 7)
        self.assertEqual(result["opportunity_usd"], 5)
        self.assertEqual(result["selection"], "retrospective")
        self.assertIsNone(oracle_opportunity(self.questions, self.observations, 1, model_roster=self.roster)["opportunity_usd"])

    def test_oracle_matches_bruteforce_including_all_model_misses(self):
        matrix = tuple(ModelOutcome(r.item_id, r.model, r.solved, r.cost_usd) for r in self.observations)
        choices = [[r for r in matrix if r.item_id == q.item_id] for q in self.questions]
        for target in (0, 1/3, .5, 2/3, 1):
            eligible = [sum(r.cost_dollars for r in policy) for policy in itertools.product(*choices)
                        if sum(r.solved for r in policy)/3 >= target]
            self.assertEqual(matched_cost(oracle_frontier(matrix), target), min(eligible) if eligible else None)

    def test_secondary_mixtures_have_expected_not_realised_labels(self):
        points = mixture_frontier(self.questions, self.observations, model_roster=self.roster)
        half = next(p for p in points if p["left_weight"] == .5)
        self.assertEqual(half["expected_accuracy"], .5)
        self.assertEqual(half["status"], "secondary_expected_randomisation")

    def test_paired_source_resampling_and_signs(self):
        category, crr = [], []
        for subset in ("a", "b", "c"):
            for i in range(8):
                item = f"{subset}-{i}"
                group = f"{subset}-{i//2}"
                category.append(PolicyRow(item, subset, group, float(i % 2 == 0), 2., ("a",)))
                crr.append(PolicyRow(item, subset, group, float(i % 3 != 0), 1. + i / 20, ("b",)))
        result = paired_comparison(tuple(category), tuple(crr), target=.5, resamples=100)
        self.assertAlmostEqual(result["mean_saving_usd"], .825)
        self.assertEqual(result["n_source_clusters"], {"a": 4, "b": 4, "c": 4})
        self.assertEqual(result["accuracy_difference_ci"]["valid"], 100)
        self.assertEqual(result, paired_comparison(tuple(reversed(category)), tuple(reversed(crr)), target=.5, resamples=100))
        self.assertFalse(result["confirmatory_matched_quality_claim"])

    def test_target_miss_and_degenerate_intervals_are_visible(self):
        rows = tuple(PolicyRow(str(i), "a", str(i), 0., 1., ("m",)) for i in range(5))
        result = paired_comparison(rows, rows, target=.8, resamples=50)
        self.assertFalse(result["both_targets_met"])
        self.assertEqual(result["accuracy_difference_ci"]["status"], "degenerate")
        self.assertFalse(result["exploratory_zero_loss_rule_met"])
        self.assertTrue(result["warnings"])

    def test_invalid_oracle_cost_and_negative_headroom_rejected(self):
        for value in (None, float("nan"), float("inf"), True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                oracle_frontier((ModelOutcome("q", "m", False, value),))
        self.assertIsNone(opportunity_capture(1, 2, 3))


if __name__ == "__main__":
    unittest.main()
