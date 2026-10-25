"""Failures that could silently invalidate the proposed experiment."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("validate_protocol", ROOT / "scripts/validate_lab_bench_protocol.py")
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.m = json.loads((ROOT / "docs/experiment-01/manifest.draft.json").read_text())

    def rehash(self):
        self.m["selection"]["items_sha256"] = MOD.digest(self.m["selection"]["items"])

    def test_review_manifest_valid_but_not_frozen(self):
        self.assertEqual(MOD.check_manifest(self.m), [])
        self.assertIn("manifest remains a draft", MOD.check_manifest(self.m, True))

    def test_heldout_cannot_be_smoke(self):
        next(r for r in self.m["selection"]["items"] if r["split"] == "held_out")["smoke"] = True
        self.rehash()
        self.assertIn("smoke item is outside development", MOD.check_manifest(self.m))

    def test_heldout_cannot_calibrate(self):
        item = next(r for r in self.m["selection"]["items"] if r["split"] == "held_out")
        self.m["method"]["calibration_item_ids"].append(item["original_id"])
        self.assertIn("calibration IDs must be unique development IDs", MOD.check_manifest(self.m))

    def test_source_overlap_rejected_even_with_updated_digest(self):
        items = self.m["selection"]["items"]
        dev = next(r for r in items if r["split"] == "development")
        held = next(r for r in items if r["split"] == "held_out")
        held["source_group"] = dev["source_group"]
        self.rehash()
        self.assertIn("source group crosses the split", MOD.check_manifest(self.m))

    def test_duplicate_content_rejected(self):
        rows = self.m["selection"]["items"]
        rows[1]["full_input_sha256"] = rows[0]["full_input_sha256"]
        self.rehash()
        self.assertIn("duplicate full-input content", MOD.check_manifest(self.m))

    def test_selection_tamper_detected(self):
        self.m["selection"]["items"][0]["original_id"] = "changed"
        self.assertIn("selection digest mismatch", MOD.check_manifest(self.m))

    def test_status_alone_cannot_freeze(self):
        self.m["status"] = "frozen"
        errors = MOD.check_manifest(self.m)
        self.assertIn("method.profile_estimator unresolved", errors)
        self.assertIn("backend.id_mapping_verified unresolved", errors)
        self.assertIn("freeze record missing", errors)

    def test_string_false_is_not_engine_verification(self):
        self.m["backend"]["id_mapping_verified"] = "false"
        self.assertIn("backend.id_mapping_verified unresolved", MOD.check_manifest(self.m, True))

    def test_nonfinite_and_boolean_budget_rejected(self):
        for value in [float("nan"), float("inf"), True, -1, 0]:
            with self.subTest(value=value):
                self.m["billing"]["approved_limit_usd"] = value
                self.assertIn("approved positive spend limit missing", MOD.check_manifest(self.m, True))

    def test_unknown_holdout_exposure_fails_closed(self):
        for value in [None, True, "false"]:
            with self.subTest(value=value):
                self.m["method"]["held_out_outcomes_seen"] = value
                self.assertIn("held-out outcomes already seen or status unknown", MOD.check_manifest(self.m))


if __name__ == "__main__":
    unittest.main()
