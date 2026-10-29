"""Backend export regressions use invented preparation hashes and mock scores."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from crr.backend_equivalence import compare_exports, digest, selected_items, PROBE_SCORES


def fixture(split="development"):
    manifest = json.loads((ROOT / "docs/experiment-01/manifest.draft.json").read_text())
    preparation = dict(manifest["upstream_task"])
    preparation.update({key: digest(key) for key in ("task_source_sha256", "solver_source_sha256", "scorer_source_sha256", "template_sha256")})
    export = {
        "schema_version": 1, "role": "official", "evidence_kind": "synthetic_fixture",
        "provider_calls": 0, "real_outcomes_collected": False,
        "split": split, "dataset_revision": manifest["dataset"]["revision"],
        "selection_sha256": manifest["selection"]["items_sha256"],
        "exporter_revision": "1" * 40, "exporter_source_sha256": "4" * 64,
        "exporter_worktree_dirty": False, "exporter_revision_kind": "clean_checkout_commit",
        "source_case_id_namespace": "lab-bench-original-id", "preparation": preparation,
        "preparation_sha256": digest(preparation),
        "records": [{"original_id": row["original_id"], "category": row["subset"],
                     "source_case_id": row["original_id"], "variant_case_id": row["original_id"],
                     "prepared_input_sha256": digest([row["original_id"], "input"]),
                     "ordered_choices_sha256": digest([row["original_id"], "choices"]),
                     "target_mapping_sha256": digest([row["original_id"], "target"])}
                    for row in selected_items(manifest, split)],
        "selected_denominator": 15 if split == "smoke" else 60,
        "scorer_probes": {name: {"score": score, "input_sha256": digest([name, "input"]),
                                "response_sha256": digest([name, "response"])}
                          for name, score in PROBE_SCORES.items()},
        "probe_aggregate": {"n_samples": 4, "n_scored": 4, "score_counts": {"C": 1, "I": 2, "N": 1}},
    }
    candidate = deepcopy(export)
    candidate.update(role="candidate", engine_location="local", engine_revision="2" * 40)
    for row in candidate["records"]:
        row["variant_case_id"] = "variant-" + row["original_id"]
    candidate["cache_identity"] = {"variant_id": "crr-test-" + split,
        "variant_revision": "3" * 64, "split": split,
        "selection_sha256": manifest["selection"]["items_sha256"],
        "preparation_sha256": candidate["preparation_sha256"]}
    return manifest, export, candidate


class BackendEquivalenceTests(unittest.TestCase):
    def test_synthetic_success_is_not_engine_evidence(self):
        result = compare_exports(*fixture())
        self.assertTrue(result["passed"], result["errors"])
        self.assertEqual(result["evidence_kind"], "synthetic_fixture_validation")
        self.assertEqual(result["selected_count"], 60)

    def test_smoke_selection_is_exact_and_development_only(self):
        data = fixture("smoke")
        result = compare_exports(*data)
        self.assertTrue(result["passed"], result["errors"])
        self.assertEqual(result["selected_count"], 15)
        data[2]["records"][0]["original_id"] = next(r["original_id"] for r in data[0]["selection"]["items"] if r["split"] == "held_out")
        self.assertFalse(compare_exports(*data)["passed"])

    def test_unknown_duplicate_and_missing_ids_rejected(self):
        for mutation in ("extra", "duplicate", "missing"):
            with self.subTest(mutation=mutation):
                data = fixture()
                rows = data[2]["records"]
                if mutation == "extra":
                    rows.append({**rows[0], "original_id": "unknown"})
                elif mutation == "duplicate":
                    rows.append(deepcopy(rows[0]))
                else:
                    rows.pop()
                self.assertFalse(compare_exports(*data)["passed"])

    def test_export_order_can_change_without_changing_mapping(self):
        data = fixture()
        data[2]["records"].reverse()
        self.assertTrue(compare_exports(*data)["passed"])

    def test_changed_category_input_choices_or_target_rejected(self):
        for key in ("category", "source_case_id", "prepared_input_sha256", "ordered_choices_sha256", "target_mapping_sha256"):
            with self.subTest(key=key):
                data = fixture()
                data[2]["records"][0][key] = digest("changed")
                self.assertFalse(compare_exports(*data)["passed"])

    def test_matching_wrong_categories_still_rejected_against_manifest(self):
        data = fixture()
        data[1]["records"][0]["category"] = data[2]["records"][0]["category"] = "wrong"
        self.assertFalse(compare_exports(*data)["passed"])

    def test_source_and_variant_case_mappings_must_be_one_to_one(self):
        for key in ("source_case_id", "variant_case_id"):
            data = fixture()
            data[2]["records"][1][key] = data[2]["records"][0][key]
            self.assertFalse(compare_exports(*data)["passed"])

    def test_selected_denominator_and_probe_aggregation_rejected(self):
        data = fixture()
        data[2]["selected_denominator"] = 199
        self.assertFalse(compare_exports(*data)["passed"])
        data = fixture()
        data[2]["probe_aggregate"]["n_scored"] = 3
        self.assertFalse(compare_exports(*data)["passed"])

    def test_changed_scorer_or_missing_abstention_probe_rejected(self):
        data = fixture()
        data[2]["scorer_probes"]["abstain"]["score"] = "I"
        self.assertFalse(compare_exports(*data)["passed"])
        data = fixture()
        del data[2]["scorer_probes"]["abstain"]
        self.assertFalse(compare_exports(*data)["passed"])

    def test_heldout_and_paid_or_actual_outcome_exports_rejected(self):
        for key, value in (("split", "held_out"), ("provider_calls", 1), ("provider_calls", False),
                           ("real_outcomes_collected", True), ("real_outcomes_collected", "false")):
            with self.subTest(key=key, value=value):
                data = fixture()
                data[1][key] = data[2][key] = value
                self.assertFalse(compare_exports(*data)["passed"])

    def test_synthetic_to_engine_promotion_rejected(self):
        data = fixture()
        data[2]["evidence_kind"] = "engine_mock"
        self.assertFalse(compare_exports(*data)["passed"])

    def test_pinned_task_and_source_hash_changes_rejected(self):
        for key, value in (("choice_shuffle_seed", 8), ("scorer_source_sha256", digest("changed"))):
            data = fixture()
            data[2]["preparation"][key] = value
            data[2]["preparation_sha256"] = digest(data[2]["preparation"])
            self.assertFalse(compare_exports(*data)["passed"])

    def test_cache_identity_must_bind_split_and_selection(self):
        for key in ("split", "selection_sha256", "preparation_sha256", "variant_revision"):
            data = fixture()
            data[2]["cache_identity"][key] = "incorrect"
            self.assertFalse(compare_exports(*data)["passed"])

    def test_malformed_export_fails_closed(self):
        data = fixture()
        del data[2]["records"]
        result = compare_exports(*data)
        self.assertFalse(result["passed"])
        self.assertTrue(any("malformed" in e for e in result["errors"]))

    def test_nonobject_or_nonfinite_export_has_failed_report(self):
        for bad in (None, [], {"x": float("nan")}):
            data = fixture()
            data = (data[0], bad, data[2])
            result = compare_exports(*data)
            self.assertFalse(result["passed"])
            self.assertTrue(any("malformed" in error for error in result["errors"]))

    def test_cli_preserves_existing_output_and_rejects_malformed_input(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            paths = []
            for name, value in zip(("manifest", "official", "candidate"), fixture()):
                path = directory / f"{name}.json"
                path.write_text(json.dumps(value))
                paths.extend([f"--{name}", str(path)])
            output = directory / "result.json"
            command = [sys.executable, str(ROOT / "scripts/check_backend_equivalence.py"), *paths, "--output", str(output)]
            completed = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            original = output.read_bytes()
            completed = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("already exists", completed.stderr)
            self.assertEqual(output.read_bytes(), original)
            (directory / "candidate.json").write_text("invalid json")
            command[-1] = str(directory / "new-result.json")
            completed = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("cannot read valid input", completed.stderr)
            self.assertFalse((directory / "new-result.json").exists())

    def test_original_id_namespace_rejects_matching_wrong_source_ids(self):
        data = fixture()
        for export in data[1:]:
            export["records"][0]["source_case_id"] = "same-wrong-source-id"
        result = compare_exports(*data)
        self.assertFalse(result["passed"])
        self.assertTrue(any("lab-bench-original-id namespace" in error for error in result["errors"]))

    def test_exporter_revision_distinguishes_dirty_source_bytes(self):
        data = fixture()
        data[1]["exporter_worktree_dirty"] = True
        result = compare_exports(*data)
        self.assertFalse(result["passed"])
        self.assertTrue(any("revision provenance" in error for error in result["errors"]))
        data[1]["exporter_revision_kind"] = "checkout_base_with_uncommitted_changes"
        self.assertTrue(compare_exports(*data)["passed"])
        data[1]["exporter_worktree_dirty"] = "false"
        self.assertFalse(compare_exports(*data)["passed"])


if __name__ == "__main__":
    unittest.main()
