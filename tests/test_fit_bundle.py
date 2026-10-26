"""Exercise the file interface using invented records and remapped fixture IDs."""
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from crr.empirical import digest, Question, Observation
from fit_empirical_method import fit_bundle
from validate_lab_bench_protocol import check_manifest


class FitBundleTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((ROOT / "docs/experiment-01/manifest.draft.json").read_text())
        questions, observations = [], []
        for i, entry in enumerate(self.manifest["selection"]["items"]):
            # Reuse only the declared split/subtask shape, not real inputs, IDs or answers.
            entry.update(original_id=f"invented-{i}", source_group=f"invented-source-{i}",
                         full_input_sha256=digest(["invented", i]))
            if entry["split"] == "development":
                questions.append(asdict(Question(entry["original_id"], entry["subset"], entry["source_group"],
                                                "Synthetic text " + "a" * (i+1), ("x", "yy"))))
                for model in self.manifest["models"]:
                    observations.append(asdict(Observation(entry["original_id"], model["slot"], i % 2 == 0,
                                                          "answered", .01)))
        self.manifest["selection"]["items_sha256"] = digest(self.manifest["selection"]["items"])
        self.manifest["method"]["calibration_item_ids"] = [q["item_id"] for q in questions]
        self.manifest["billing"]["pricing_sha256"] = digest("synthetic prices")
        self.bundle = {"questions": questions, "observations": observations, "data_kind": "synthetic",
                       "cost_basis": "frozen_price_all_attempts", "pricing_sha256": digest("synthetic prices"),
                       "preparation_record_sha256": digest("synthetic preparation")}
        self.assertEqual(check_manifest(self.manifest), [])

    def test_normalized_bundle_rejects_mismatched_prices(self):
        self.bundle["pricing_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "pricing snapshot"):
            fit_bundle(self.manifest, self.bundle)

    def test_normalized_bundle_rejects_gold_in_input_view(self):
        self.bundle["questions"][0]["target"] = "A"
        with self.assertRaisesRegex(ValueError, "unexpected fields"):
            fit_bundle(self.manifest, self.bundle)

    def test_cli_preserves_provenance_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "manifest.json").write_text(json.dumps(self.manifest))
            (path / "bundle.json").write_text(json.dumps(self.bundle))
            command = [sys.executable, str(ROOT / "scripts/fit_empirical_method.py"),
                       "--manifest", str(path / "manifest.json"), "--development-bundle", str(path / "bundle.json"),
                       "--output", str(path / "fit.json")]
            result = subprocess.run(command, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            artifact = json.loads((path / "fit.json").read_text())
            self.assertEqual(artifact["provenance"]["data_kind"], "synthetic")
            self.assertEqual(len(artifact["training_ids"]), 60)
            self.assertEqual(json.loads(result.stdout)["fit_sha256"], digest(artifact))
            again = subprocess.run(command, text=True, capture_output=True)
            self.assertNotEqual(again.returncode, 0)
            self.assertIn("output exists", again.stderr)


if __name__ == "__main__":
    unittest.main()
