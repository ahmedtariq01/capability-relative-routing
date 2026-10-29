from dataclasses import replace
from pathlib import Path
import copy
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from crr.empirical import choose, fit_development, plan_routes, restore_profiles, route_question
from crr.overhead import measure_overhead
from empirical_fixtures import fixture


class OverheadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, cls.questions, cls.observations = fixture()
        cls.fitted = fit_development(cls.manifest, cls.questions, cls.observations)
        cls.fitted["provenance"] = {"data_kind": "synthetic"}

    def test_category_route_preserves_choices_without_computing_features(self):
        profiles = restore_profiles(self.fitted)
        expected = {q.item_id: choose([p.predict(q) for p in profiles], "category", .5)
                    for q in self.questions}
        with patch("crr.empirical.features", side_effect=AssertionError("category extracted CRR features")):
            actual = {q.item_id: route_question(profiles, q, "category", .5) for q in self.questions}
            self.assertEqual(actual, expected)
            self.assertIsNotNone(plan_routes(self.fitted, self.questions, "category", .8)["routes"])

    def test_measurement_never_promotes_synthetic_or_missing_cost_to_evidence(self):
        result = measure_overhead(self.fitted, self.questions[:2], input_data_kind="synthetic",
                                  warmup=1, repetitions=2)
        self.assertEqual(len(result["raw_samples"]), 8)
        self.assertFalse(result["execution_gate_satisfied"])
        self.assertFalse(result["backend_dispatch_measured"])
        self.assertFalse(result["total_deployable_overhead_available"])
        self.assertEqual(result["provider_calls"], 0)
        self.assertIsNone(result["router_cpu_usd_per_second"])
        for family in result["families"].values():
            self.assertIsNone(family["components"]["total"]["mean_local_cpu_cost_usd"])
            self.assertGreater(family["components"]["total"]["elapsed_ns"]["mean"], 0)

    def test_explicit_cpu_rate_applies_only_to_measured_local_component(self):
        result = measure_overhead(self.fitted, self.questions[:1], input_data_kind="synthetic",
                                  warmup=1, repetitions=2, cpu_usd_per_second=.01)
        for family in result["families"].values():
            total = family["components"]["total"]
            self.assertAlmostEqual(total["mean_local_cpu_cost_usd"], total["cpu_ns"]["mean"] / 1e9 * .01)
        self.assertEqual(result["cost_status"], "local_cpu_component_only")
        self.assertFalse(result["execution_gate_satisfied"])

    def test_bad_rates_and_unrepeated_measurements_rejected(self):
        for rate in (0, -1, True, float("nan"), float("inf")):
            with self.subTest(rate=rate), self.assertRaises(ValueError):
                measure_overhead(self.fitted, self.questions[:1], input_data_kind="synthetic", cpu_usd_per_second=rate)
        for args in ({"warmup": 0}, {"repetitions": 1}, {"repetitions": True}):
            with self.assertRaises(ValueError):
                measure_overhead(self.fitted, self.questions[:1], input_data_kind="synthetic", **args)

    def test_heldout_and_data_kind_mislabeling_rejected(self):
        with self.assertRaises(ValueError):
            measure_overhead(self.fitted, (replace(self.questions[0], item_id="never-load-LitQA2-0"),),
                             input_data_kind="synthetic")
        for kind in ("measured_development", "held_out", "unknown"):
            with self.assertRaises(ValueError):
                measure_overhead(self.fitted, self.questions[:1], input_data_kind=kind)

    def test_real_development_requires_exact_complete_fitted_input_bytes(self):
        artifact = copy.deepcopy(self.fitted)
        artifact["provenance"]["data_kind"] = "measured_development"
        for changed in (self.questions[:-1],
                        (replace(self.questions[0], input_text="different prepared payload"),) + self.questions[1:],
                        (replace(self.questions[0], choices=tuple(reversed(self.questions[0].choices))),) + self.questions[1:]):
            with self.subTest(changed=changed[0].item_id), self.assertRaises(ValueError):
                measure_overhead(artifact, changed, input_data_kind="measured_development", warmup=1, repetitions=2)
        result = measure_overhead(artifact, tuple(reversed(self.questions)),
                                  input_data_kind="measured_development", warmup=1, repetitions=2)
        self.assertEqual(result["input_sha256"], artifact["training_inputs_sha256"])
        self.assertFalse(result["execution_gate_satisfied"])

    def test_unattainable_primary_cannot_borrow_secondary_threshold(self):
        artifact = copy.deepcopy(self.fitted)
        for family in artifact["selections"].values():
            next(p for p in family if p["target"] == .8)["selected"] = None
        result = measure_overhead(artifact, self.questions[:1], input_data_kind="synthetic", warmup=1, repetitions=2)
        self.assertEqual(result["raw_samples"], [])
        self.assertTrue(all(r["status"] == "unattainable_on_development" for r in result["families"].values()))


if __name__ == "__main__":
    unittest.main()
