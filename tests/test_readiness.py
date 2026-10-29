"""Local evidence failure cases, using invented approvals and exports only."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from crr.empirical import digest
from crr.readiness import check_readiness, _check_lock, _check_overhead, _check_routes, _check_method_source_hashes, EvidenceError


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = {"schema_version": 1, "held_out_outcomes_seen": False, "evidence": {}}
        self.manifest = json.loads((ROOT / "docs/experiment-01/manifest.draft.json").read_text())
        self.add("manifest", self.manifest)
        documents = {}
        for name in ("METHOD.md", "ANALYSIS.md", "method-plan.json"):
            relative = "docs/experiment-01/" + name
            dest = self.root / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes((ROOT / relative).read_bytes())
            documents[relative] = hashlib.sha256(dest.read_bytes()).hexdigest()
        self.spec = {"schema_version": 1, "status": "specification_approved",
                     "approved_commit": "1" * 40, "approved_by": "fixture reviewer",
                     "approval_url": "https://example.invalid/invented-approval",
                     "approved_at": "2026-10-29T00:00:00Z", "execution_authorized": False,
                     "documents": documents, "selection_sha256": self.manifest["selection"]["items_sha256"]}
        self.add("specification", self.spec)

    def add(self, name, value):
        path = self.root / (name + ".json")
        path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
        ref = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        self.config["evidence"][name] = ref
        return ref

    def report(self):
        return check_readiness(self.config, self.root)

    def stage(self, name):
        return self.report()["stages"][name]

    def add_smoke_prerequisites(self):
        # These are deliberately invented export/approval fixtures. Nothing is executed.
        from test_backend_equivalence import fixture
        from crr.backend_equivalence import compare_exports
        _, official_data, candidate_data = fixture("smoke")
        # Model an engine record's structure in a temporary unit-test fixture.
        # No file produced by this helper is used as real readiness evidence.
        official_data["evidence_kind"] = "upstream_task_mock"
        candidate_data["evidence_kind"] = "engine_mock"
        official = self.add("official_source", official_data)
        candidate = self.add("candidate_source", candidate_data)
        self.backend = compare_exports(self.manifest, official_data, candidate_data)
        self.backend["source_files"] = {"official": official, "candidate": candidate,
                                        "manifest": self.config["evidence"]["manifest"]}
        self.add("backend_equivalence", self.backend)
        self.models = {"evidence_kind": "model_configuration_manifest", "models": [
            {"slot": f"model_{i}", "api_id": f"fixture/model-{i}", "version": "fixture-1",
             "provider_route": "fixture-direct", "generation_settings": {"reasoning": "disabled", "max_output_tokens": 50},
             "retry": {"max_attempts": 1, "retryable_errors": []}, "timeout_seconds": 30,
             "route_fallbacks": []} for i in range(1, 5)]}
        self.add("model_manifest", self.models)
        self.prices = {"evidence_kind": "pricing_manifest", "currency": "USD",
                       "model_manifest_sha256": self.config["evidence"]["model_manifest"]["sha256"],
                       "models": {f"model_{i}": {"input_per_million_tokens_usd": 1, "output_per_million_tokens_usd": 2,
                           "source_url": "https://example.invalid/fixture-prices", "retrieved_at": "2026-10-29",
                           "reasoning_billing": "included in output", "cache_billing": "disabled",
                           "failed_attempt_billing": "record billed usage even on failure"} for i in range(1, 5)},
                       "cost_boundary": {"inference": "all_attempts", "credits": "billing_only",
                                         "routing": "feature_prediction_selection_dispatch"}}
        self.add("pricing_manifest", self.prices)
        self.spending = {"evidence_kind": "spending_approval", "approved_by": "fixture user",
                         "approved_at": "2026-10-29", "source": "invented approval for unit test only",
                         "scopes": ["development_smoke"], "limits_usd": {"development_smoke": 1},
                         "model_manifest_sha256": self.config["evidence"]["model_manifest"]["sha256"],
                         "pricing_manifest_sha256": self.config["evidence"]["pricing_manifest"]["sha256"]}
        self.add("spending_approval", self.spending)

    def test_specification_approval_does_not_clear_execution(self):
        report = self.report()
        self.assertTrue(report["stages"]["specification"]["local_prerequisites_satisfied"])
        for stage in ("development_smoke", "development_collection", "held_out"):
            self.assertFalse(report["stages"][stage]["local_prerequisites_satisfied"])
        self.assertFalse(report["execution_authorized_by_this_check"])
        self.assertEqual(report["provider_calls"], 0)

    def test_source_edit_invalidates_specification(self):
        (self.root / "docs/experiment-01/METHOD.md").write_text("edited after approval")
        self.assertFalse(self.stage("specification")["local_prerequisites_satisfied"])
        self.assertTrue(any("document changed" in e for e in self.stage("specification")["blockers"]))

    def test_wrong_approval_document_scope_rejected(self):
        del self.spec["documents"]["docs/experiment-01/ANALYSIS.md"]
        self.add("specification", self.spec)
        self.assertFalse(self.stage("specification")["local_prerequisites_satisfied"])

    def test_record_cannot_expand_specification_to_execution(self):
        self.spec["execution_authorized"] = True
        self.add("specification", self.spec)
        self.assertFalse(self.stage("specification")["local_prerequisites_satisfied"])

    def test_referenced_file_tamper_is_detected(self):
        (self.root / "specification.json").write_text("{}")
        self.assertIn("specification: artifact file-byte hash mismatch", self.stage("specification")["blockers"])

    def test_unknown_holdout_exposure_fails_closed(self):
        for value in (None, True, "false"):
            with self.subTest(value=value):
                self.config["held_out_outcomes_seen"] = value
                self.assertFalse(self.stage("specification")["local_prerequisites_satisfied"])

    def test_smoke_does_not_require_the_fit_it_will_help_create(self):
        self.add_smoke_prerequisites()
        result = self.stage("development_smoke")
        self.assertTrue(result["local_prerequisites_satisfied"], result["blockers"])
        self.assertFalse(self.stage("development_collection")["local_prerequisites_satisfied"])
        self.assertFalse(self.stage("held_out")["local_prerequisites_satisfied"])

    def test_synthetic_backend_export_cannot_clear_smoke(self):
        self.add_smoke_prerequisites()
        self.backend["evidence_kind"] = "synthetic_fixture_validation"
        self.add("backend_equivalence", self.backend)
        self.assertTrue(any("synthetic backend" in e for e in self.stage("development_smoke")["blockers"]))

    def test_backend_mapping_and_source_bytes_must_survive(self):
        self.add_smoke_prerequisites()
        self.backend["coverage"]["category"] = False
        self.add("backend_equivalence", self.backend)
        self.assertTrue(any("category comparison" in e for e in self.stage("development_smoke")["blockers"]))
        self.backend["coverage"]["category"] = True
        self.add("backend_equivalence", self.backend)
        (self.root / "candidate_source.json").write_text("{}")
        self.assertTrue(any("file-byte hash mismatch" in e for e in self.stage("development_smoke")["blockers"]))

    def test_backend_pass_boolean_cannot_override_bad_exports(self):
        self.add_smoke_prerequisites()
        changed = json.loads((self.root / "candidate_source.json").read_text())
        changed["records"][0]["category"] = "wrong"
        self.backend["source_files"]["candidate"] = self.add("candidate_source", changed)
        self.add("backend_equivalence", self.backend)
        self.assertTrue(any("recomputed comparison" in e for e in self.stage("development_smoke")["blockers"]))

    def test_model_null_settings_need_explicit_semantics(self):
        self.add_smoke_prerequisites()
        for field in ("reasoning", "max_output_tokens", "temperature", "seed"):
            with self.subTest(field=field):
                modified = deepcopy(self.models)
                modified["models"][0]["generation_settings"][field] = None
                self.add("model_manifest", modified)
                self.assertTrue(any("model_manifest:" in e for e in self.stage("development_smoke")["blockers"]))

    def test_malformed_model_array_fails_closed(self):
        self.add_smoke_prerequisites()
        self.models["models"] = [None, [], 1, "invalid"]
        self.add("model_manifest", self.models)
        self.assertFalse(self.stage("development_smoke")["local_prerequisites_satisfied"])

    def test_model_placeholder_or_missing_retry_setting_blocks_smoke(self):
        self.add_smoke_prerequisites()
        for field, value in (("api_id", "placeholder"), ("retry", {}), ("timeout_seconds", True), ("route_fallbacks", None)):
            with self.subTest(field=field):
                modified = deepcopy(self.models)
                modified["models"][0][field] = value
                self.add("model_manifest", modified)
                self.assertFalse(self.stage("development_smoke")["local_prerequisites_satisfied"])

    def test_price_change_invalidates_approval_binding(self):
        self.add_smoke_prerequisites()
        self.prices["models"]["model_1"]["input_per_million_tokens_usd"] = 9
        self.add("pricing_manifest", self.prices)
        self.assertTrue(any("spending approval refers to a different pricing" in e
                            for e in self.stage("development_smoke")["blockers"]))

    def test_smoke_spending_approval_cannot_authorize_collection(self):
        self.add_smoke_prerequisites()
        self.assertTrue(any("does not cover development_collection" in e
                            for e in self.stage("development_collection")["blockers"]))

    def test_synthetic_development_report_cannot_clear_collection(self):
        self.add_smoke_prerequisites()
        self.add("development_smoke", {"evidence_kind": "measured_development_smoke", "data_kind": "synthetic", "passed": True})
        self.assertTrue(any("synthetic fixtures" in e for e in self.stage("development_collection")["blockers"]))

    def add_development_smoke_report(self, *, real_structure=True):
        self.add_smoke_prerequisites()
        self.spending["scopes"].append("development_collection")
        self.spending["limits_usd"]["development_collection"] = 5
        self.add("spending_approval", self.spending)
        entries = [x for x in self.manifest["selection"]["items"] if x["smoke"]]
        rows, terminal = [], []
        for item in entries:
            for model in self.models["models"]:
                setting = {k: model[k] for k in ("generation_settings", "retry", "timeout_seconds", "route_fallbacks")}
                rows.append({"call_id": "invented-" + item["original_id"] + model["slot"],
                    "manifest_sha256": digest(self.manifest), "original_item_id": item["original_id"],
                    "model_slot": model["slot"], "split": "development", "subset": item["subset"],
                    "purpose": "answer", "attempt_index": 1, "previous_attempt_id": None, "status": "success",
                    "model": {"requested_id": model["api_id"], "effective_id": model["api_id"],
                              "provider_route": model["provider_route"], "effective_version": model["version"],
                              "settings_sha256": digest(setting)},
                    "cost": {"currency": "USD", "pricing_sha256": self.config["evidence"]["pricing_manifest"]["sha256"],
                             "estimated_usd": .01, "billed_usd": .01, "source": "invented unit-test receipt"},
                    "outcome": {"grade": "C"}})
                terminal.append({"item_id": item["original_id"], "model": model["slot"],
                                 "solved": True, "response_status": "answered", "cost_usd": .01})
        terminal.sort(key=lambda x: (x["item_id"], x["model"]))
        self.ledger = {"evidence_kind": "provider_attempt_ledger", "data_kind": "measured_development", "receipts": rows}
        if not real_structure:
            self.ledger = {"data_kind": "synthetic", "rows": []}
        ledger_ref = self.add("ledger", self.ledger)
        self.reconciliation = {"evidence_kind": "development_receipt_reconciliation", "data_kind": "measured_development",
                               "passed": True, "receipt_ledger_sha256": ledger_ref["sha256"], "terminal_rows": 60,
                               "terminal_observations_sha256": digest(terminal),
                               **{k: 0 for k in ("missing_cost_rows", "configuration_mismatches", "duplicate_calls",
                                                "broken_attempt_chains", "unexpected_items", "missing_terminal_rows")}}
        report = {"evidence_kind": "measured_development_smoke", "data_kind": "measured_development",
                  "passed": True, "held_out_outcomes_seen": False,
                  "selected_ids": [x["original_id"] for x in entries], "terminal_rows": 60,
                  "receipt_ledger": ledger_ref, "reconciliation": self.add("reconciliation", self.reconciliation),
                  **{name + "_sha256": self.config["evidence"][name]["sha256"]
                     for name in ("model_manifest", "pricing_manifest", "backend_equivalence")}}
        self.smoke_report = report
        self.add("development_smoke", report)

    def rehash_development_report(self):
        self.smoke_report["receipt_ledger"] = self.add("ledger", self.ledger)
        self.reconciliation["receipt_ledger_sha256"] = self.smoke_report["receipt_ledger"]["sha256"]
        self.smoke_report["reconciliation"] = self.add("reconciliation", self.reconciliation)
        self.add("development_smoke", self.smoke_report)

    def test_claimed_reconciliation_cannot_promote_an_empty_synthetic_ledger(self):
        self.add_development_smoke_report(real_structure=False)
        self.assertTrue(any("ledger is not measured development" in e
                            for e in self.stage("development_collection")["blockers"]))

    def test_complete_receipt_graph_can_clear_collection_but_not_heldout(self):
        self.add_development_smoke_report()
        report = self.stage("development_collection")
        self.assertTrue(report["local_prerequisites_satisfied"], report["blockers"])
        self.assertFalse(self.stage("held_out")["local_prerequisites_satisfied"])

    def test_actual_attempt_rows_override_claimed_zero_error_counters(self):
        for mutation in ("missing", "duplicate", "cost", "attempt", "status", "model"):
            with self.subTest(mutation=mutation):
                self.add_development_smoke_report()
                rows = self.ledger["receipts"]
                if mutation == "missing": rows.pop()
                elif mutation == "duplicate": rows.append(deepcopy(rows[0]))
                elif mutation == "cost": rows[0]["cost"]["estimated_usd"] = None
                elif mutation == "attempt": rows[0]["previous_attempt_id"] = "invented-missing-previous"
                elif mutation == "status": rows[0]["status"] = "timeout"
                elif mutation == "model": rows[0]["model"]["provider_route"] = "different-route"
                self.rehash_development_report()
                self.assertFalse(self.stage("development_collection")["local_prerequisites_satisfied"])

    def test_synthetic_timing_cannot_clear_final_overhead(self):
        with self.assertRaisesRegex(EvidenceError, "synthetic timings"):
            _check_overhead({"record_type": "local_routing_overhead", "data_kind": "synthetic", "fit_data_kind": "synthetic"}, {})

    def test_local_serialization_is_not_backend_dispatch(self):
        fit = {"training_ids": ["invented-dev-id"], "training_inputs_sha256": digest("invented input")}
        overhead = {"record_type": "local_routing_overhead", "data_kind": "measured_development",
                    "fit_data_kind": "measured_development", "fit_sha256": digest(fit), "split": "development",
                    "input_ids": fit["training_ids"], "input_sha256": fit["training_inputs_sha256"], "router_cpu_usd_per_second": .001,
                    "warmup_passes": 1, "measurement_passes": 5, "environment": {"python": "fixture"},
                    "families": {"category": {}, "crr": {}}, "backend_dispatch_measured": False,
                    "total_deployable_overhead_available": False}
        with self.assertRaisesRegex(EvidenceError, "actual backend dispatch"):
            _check_overhead(overhead, fit)
        overhead.update(backend_dispatch_measured=True, total_deployable_overhead_available=True)
        with self.assertRaisesRegex(EvidenceError, "reference"):
            _check_overhead(overhead, fit, self.root)

    def test_dispatch_flags_cannot_replace_raw_measurements(self):
        fit = {"training_ids": ["invented-dev-id"], "training_inputs_sha256": digest("invented input")}
        source = self.root / "instrumentation.py"
        source.write_text("# invented instrumentation fixture\n")
        dispatch = {"record_type": "backend_dispatch_measurement", "data_kind": "measured_development",
                    "boundary": "backend_adapter_dispatch", "fit_sha256": digest(fit),
                    "input_sha256": fit["training_inputs_sha256"],
                    "source_sha256": {source.name: hashlib.sha256(source.read_bytes()).hexdigest()}, "raw_samples": []}
        overhead = {"record_type": "local_routing_overhead", "data_kind": "measured_development",
                    "fit_data_kind": "measured_development", "fit_sha256": digest(fit), "split": "development",
                    "input_ids": fit["training_ids"], "input_sha256": fit["training_inputs_sha256"],
                    "router_cpu_usd_per_second": .001, "warmup_passes": 1, "measurement_passes": 2,
                    "environment": {"python": "fixture"}, "families": {"category": {}, "crr": {}},
                    "backend_dispatch_measured": True, "total_deployable_overhead_available": True,
                    "backend_dispatch_evidence": self.add("dispatch", dispatch), "raw_samples": []}
        with self.assertRaisesRegex(EvidenceError, "nonempty"):
            _check_overhead(overhead, fit, self.root)

    def test_lock_cannot_omit_routes_or_selected_policies(self):
        from crr.readiness import REQUIRED
        hashes = {k: digest(k) for k in REQUIRED["held_out"]}
        artifacts = {k: v for k, v in hashes.items() if k != "held_out_lock"}
        lock = {"evidence_kind": "held_out_precollection_lock", "held_out_outcomes_seen": False,
                "locked_at": "2026-10-29", "recorded_by": "fixture", "artifacts": artifacts}
        _check_lock(lock, hashes)
        del artifacts["route_table"]
        with self.assertRaisesRegex(EvidenceError, "every current evidence"):
            _check_lock(lock, hashes)

    def route_fixture(self):
        from crr.empirical import TARGETS
        fit = {"profiles": [{"model": "model_1"}], "selections": {f: [
            {"target": t, "selected": {"threshold": .5}} for t in TARGETS] for f in ("category", "crr")}}
        ids = [x["original_id"] for x in self.manifest["selection"]["items"] if x["split"] == "held_out"]
        rows = {i: {"model": "model_1", "probability": .8, "expected_cost_usd": .01, "threshold_met": True} for i in ids}
        plans = [{"family": f, "target": t, "target_role": "primary" if t == .8 else "secondary",
                  "fit_sha256": digest(fit), "threshold": .5, "routes": deepcopy(rows), "routes_sha256": digest(rows),
                  "visible_inputs_sha256": digest("invented visible inputs"), "status": "planned_not_execution_approval"}
                 for f in ("category", "crr") for t in TARGETS]
        hashes = {"fitted_method": digest("fit file bytes"), "selected_policies": digest("policies file bytes")}
        artifact = {"evidence_kind": "pre_outcome_route_table", "held_out_outcomes_seen": False,
                    "fit_artifact_sha256": hashes["fitted_method"], "selected_policies_sha256": hashes["selected_policies"],
                    "plans": plans}
        return artifact, fit, hashes

    def test_route_table_rejects_unknown_models_and_invalid_selection_values(self):
        artifact, fit, hashes = self.route_fixture()
        _check_routes(artifact, fit, self.manifest, hashes)
        for key, value in (("model", "unknown-model"), ("probability", True), ("probability", 1.1),
                           ("expected_cost_usd", -1), ("threshold_met", "false")):
            with self.subTest(key=key, value=value):
                altered = deepcopy(artifact)
                next(iter(altered["plans"][0]["routes"].values()))[key] = value
                altered["plans"][0]["routes_sha256"] = digest(altered["plans"][0]["routes"])
                with self.assertRaises(EvidenceError):
                    _check_routes(altered, fit, self.manifest, hashes)

    def test_route_table_cannot_promote_a_secondary_target(self):
        artifact, fit, hashes = self.route_fixture()
        artifact["plans"][0]["target_role"] = "primary"
        with self.assertRaisesRegex(EvidenceError, "target role"):
            _check_routes(artifact, fit, self.manifest, hashes)

    def test_unattainable_primary_keeps_its_primary_designation(self):
        artifact, fit, hashes = self.route_fixture()
        for rows in fit["selections"].values():
            next(row for row in rows if row["target"] == .8)["selected"] = None
        for plan in artifact["plans"]:
            plan["fit_sha256"] = digest(fit)
            if plan["target"] == .8:
                plan.update(status="unattainable_on_development", routes=None, target_role="secondary")
        with self.assertRaisesRegex(EvidenceError, "target role"):
            _check_routes(artifact, fit, self.manifest, hashes)

    def test_readme_hash_cannot_replace_implementation_hashes(self):
        path = self.root / "README.md"
        path.write_text("invented source binding fixture")
        with self.assertRaisesRegex(EvidenceError, "empirical.py, analysis.py and oracle.py"):
            _check_method_source_hashes({"README.md": hashlib.sha256(path.read_bytes()).hexdigest()}, self.root)
        source = {}
        for name in ("empirical.py", "analysis.py", "oracle.py"):
            relative = "src/crr/" + name
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((ROOT / relative).read_bytes())
            source[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        _check_method_source_hashes(source, self.root)

    def test_malformed_json_reports_failure_without_loading_secrets(self):
        path = self.root / "bad.json"
        path.write_text('{"value":NaN}')
        self.config["evidence"]["specification"] = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        self.assertIn("specification: artifact must contain finite JSON", self.stage("specification")["blockers"])


if __name__ == "__main__":
    unittest.main()
