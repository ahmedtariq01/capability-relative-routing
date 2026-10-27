import copy
from dataclasses import asdict, replace
import json
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from crr.empirical import (Question, Observation, features, grouped_folds, fit_development,
                           restore_profiles, plan_routes, validate_development, choose, PRIMARY_TARGET)
from empirical_fixtures import fixture


class EmpiricalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, cls.questions, cls.observations = fixture()
        cls.fitted = fit_development(cls.manifest, cls.questions, cls.observations)

    def test_features_use_only_allowed_visible_fields(self):
        q = Question("x", "SeqQA", "g", "ACGTACGT 123", ("A", "BBBB"))
        actual = features(q)
        expected = (math.log1p(12), 3/12, 8/12, math.log1p(2), math.log1p(2.5), 3/2.5)
        for a, b in zip(actual, expected):
            self.assertAlmostEqual(a, b)
        self.assertEqual(actual, features(replace(q, item_id="bookkeeping-only", source_group="different")))
        for field in ("target", "answer", "subtask", "response", "usage", "cost"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                Question.from_dict({**asdict(q), field: "never a feature"})
        with self.assertRaises(ValueError):
            Question.from_dict({**asdict(q), "choices": "ABCD"})

    def test_category_shrinkage_and_uncertainty(self):
        p = self.fitted["profiles"][0]["categories"]["LitQA2"]
        rows = [r for r in self.observations if r.model == "model_1" and "LitQA2" in r.item_id]
        successes = sum(r.solved for r in rows)
        self.assertEqual(p["n"], 20)
        self.assertAlmostEqual(p["probability"], (successes + 1) / 22)
        self.assertGreater(p["posterior_sd"], 0)
        self.assertAlmostEqual(p["expected_cost_usd"], .01)

    def test_bookkeeping_ids_cannot_change_frozen_predictions_costs_or_routes(self):
        changed = tuple(replace(q, item_id=f"renamed-{i}", source_group=f"other-{i}")
                        for i, q in enumerate(self.questions))
        for profile in restore_profiles(self.fitted):
            for original, renamed in zip(self.questions, changed):
                self.assertEqual(profile.predict(original), profile.predict(renamed))
        for family in ("category", "crr"):
            original_routes = plan_routes(self.fitted, self.questions, family, .5)["routes"]
            renamed_routes = plan_routes(self.fitted, changed, family, .5)["routes"]
            for original, renamed in zip(self.questions, changed):
                self.assertEqual(original_routes[original.item_id], renamed_routes[renamed.item_id])

    def test_unknown_category_cannot_be_inferred_from_bookkeeping(self):
        question = replace(self.questions[0], subset="undeclared_task")
        with self.assertRaises(ValueError):
            restore_profiles(self.fitted)[0].predict(question)
        with self.assertRaises(ValueError):
            plan_routes(self.fitted, (question,), "crr", .5)

    def test_features_center_within_category_on_training_only(self):
        profile = restore_profiles(self.fitted)[0]
        for subset in profile.categories:
            values = [features(q) for q in self.questions if q.subset == subset]
            for j, center in enumerate(profile.means[subset]):
                self.assertAlmostEqual(sum(v[j] - center for v in values), 0)
        for p in self.fitted["profiles"]:
            self.assertLessEqual(p["gradient_max"], 1e-9)

    def test_crossfit_never_sees_validation_labels_or_scaling(self):
        for audit in self.fitted["fold_audits"]:
            train, validation = set(audit["train_ids"]), set(audit["validation_ids"])
            self.assertFalse(train & validation)
            self.assertEqual(train | validation, {q.item_id for q in self.questions})
            self.assertEqual(sum(c["n"] for c in audit["profiles"][0]["categories"].values()), len(train))
        changed_id = self.questions[0].item_id
        changed = tuple(replace(r, solved=not r.solved) if r.item_id == changed_id else r for r in self.observations)
        refit = fit_development(self.manifest, self.questions, changed)
        self.assertEqual(self.fitted["oof_predictions"][changed_id], refit["oof_predictions"][changed_id])

    def test_related_source_items_share_fold(self):
        qs = list(self.questions)
        qs[1] = replace(qs[1], source_group=qs[0].source_group)
        folds = grouped_folds(tuple(qs))
        self.assertEqual(folds[qs[0].item_id], folds[qs[1].item_id])

    def test_heldout_and_missing_or_duplicate_rows_fail_closed(self):
        bad = replace(self.questions[0], item_id="never-load-LitQA2-0")
        for qs, rows in [(self.questions[1:] + (bad,), self.observations),
                         (self.questions, self.observations[:-1]),
                         (self.questions, self.observations + (self.observations[0],))]:
            with self.assertRaises(ValueError):
                validate_development(self.manifest, qs, rows)
        with self.assertRaises(ValueError):
            validate_development(self.manifest, self.questions,
                                 (replace(self.observations[0], cost_usd=None),) + self.observations[1:])

    def test_manifest_exposure_and_source_leakage_rejected(self):
        m = copy.deepcopy(self.manifest)
        m["method"]["held_out_outcomes_seen"] = True
        with self.assertRaises(ValueError):
            validate_development(m, self.questions, self.observations)
        m = copy.deepcopy(self.manifest)
        next(r for r in m["selection"]["items"] if r["split"] == "held_out")["source_group"] = self.questions[0].source_group
        with self.assertRaises(ValueError):
            validate_development(m, self.questions, self.observations)

    def test_fit_and_route_serialization_is_deterministic(self):
        roundtrip = json.loads(json.dumps(self.fitted))
        plan = plan_routes(roundtrip, self.questions, "crr", .5)
        self.assertEqual(plan, plan_routes(self.fitted, tuple(reversed(self.questions)), "crr", .5))
        refit = fit_development(self.manifest, tuple(reversed(self.questions)), tuple(reversed(self.observations)))
        self.assertEqual(self.fitted, refit)

    def test_unattainable_target_is_not_silently_relaxed(self):
        obs = tuple(replace(r, solved=False) for r in self.observations)
        fit = fit_development(self.manifest, self.questions, obs)
        self.assertEqual(plan_routes(fit, self.questions, "category", .8)["status"], "unattainable_on_development")
        for family in fit["selections"].values():
            self.assertTrue(all(s["selected"] is None for s in family))

    def test_attainable_secondary_cannot_replace_unavailable_primary(self):
        # All models solve the same 12 of 20 questions per category, so every
        # route reaches 0.60 and none can attain the primary target of 0.80.
        obs = tuple(replace(r, solved=int(r.item_id.rsplit("-", 1)[1]) < 12) for r in self.observations)
        fit = fit_development(self.manifest, self.questions, obs)
        self.assertEqual(fit["primary_comparison"]["target"], .8)
        self.assertEqual(fit["primary_comparison"]["status"], "unavailable_on_development")
        self.assertFalse(fit["primary_comparison"]["secondary_target_promotion_allowed"])
        for family in ("category", "crr"):
            primary = plan_routes(fit, self.questions, family, PRIMARY_TARGET)
            secondary = plan_routes(fit, self.questions, family, .5)
            self.assertIsNone(primary["routes"])
            self.assertEqual(primary["target_role"], "primary")
            self.assertIsNotNone(secondary["routes"])
            self.assertEqual(secondary["target_role"], "secondary")
            self.assertEqual(fit["primary_comparison"]["family_status"][family], "unattainable_on_development")
        self.assertIsNone(fit["fixed_model_selections"]["0.8"]["selected"])

    def test_degenerate_features_recover_category_probabilities(self):
        qs = tuple(replace(q, input_text="identical visible input", choices=("a", "b")) for q in self.questions)
        fit = fit_development(self.manifest, qs, self.observations)
        for p in restore_profiles(fit):
            self.assertEqual(p.coefficients, (0.0,) * 6)
            for q in qs[:2]:
                pred = p.predict(q)
                self.assertAlmostEqual(pred["category_probability"], pred["crr_probability"])

    def test_selection_ties_and_unmet_prediction_threshold_are_explicit(self):
        predictions = [{"model": name, "category_probability": .5, "crr_probability": .5,
                        "expected_cost_usd": .1} for name in ("b", "a")]
        self.assertEqual(choose(predictions, "category", .5)["model"], "a")
        selected = choose(predictions, "crr", 1)
        self.assertFalse(selected["threshold_met"])
        self.assertEqual(selected["model"], "a")

    def test_invalid_observation_cannot_enter_fit(self):
        for cost in (float("nan"), float("inf"), -1, True):
            with self.subTest(cost=cost), self.assertRaises(ValueError):
                Observation("x", "m", False, "failed", cost)
        with self.assertRaises(ValueError):
            Observation("x", "m", True, "failed", .1)

    def test_serialized_profile_dimensions_cannot_silently_truncate(self):
        artifact = copy.deepcopy(self.fitted)
        artifact["profiles"][0]["coefficients"] = (1.,)
        with self.assertRaises(ValueError):
            restore_profiles(artifact)

    def test_visible_features_can_change_predictions_within_a_category(self):
        profile = restore_profiles(self.fitted)[0]
        a, b = profile.predict(self.questions[0]), profile.predict(self.questions[17])
        self.assertEqual(a["category_probability"], b["category_probability"])
        self.assertNotAlmostEqual(a["crr_probability"], b["crr_probability"])


if __name__ == "__main__":
    unittest.main()
