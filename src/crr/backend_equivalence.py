"""Compare selected-ID preparation and mock-scoring exports, without model calls.

Exports contain hashes rather than benchmark answers. A passing comparison
checks the supplied artifacts; it cannot authenticate their collection path.
"""
from __future__ import annotations

import hashlib
import json
import re

SHA256 = re.compile(r"[0-9a-f]{64}\Z")
REVISION = re.compile(r"[0-9a-f]{40}\Z")
PROBE_SCORES = {"correct": "C", "incorrect": "I", "abstain": "N", "malformed": "I"}
RECORD_FIELDS = ("category", "source_case_id", "prepared_input_sha256",
                 "ordered_choices_sha256", "target_mapping_sha256")
PREPARATION_HASH_FIELDS = ("task_source_sha256", "solver_source_sha256",
                           "scorer_source_sha256", "template_sha256")
COVERAGE = ("category", "selected_ids", "prepared_input", "choice_order",
            "target_mapping", "scorer", "aggregation", "cache_identity")


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def selected_items(manifest: dict, split: str) -> list[dict]:
    if split not in ("development", "smoke"):
        raise ValueError("backend preflight accepts development or smoke only")
    return [r for r in manifest["selection"]["items"]
            if r["split"] == "development" and (split != "smoke" or r["smoke"] is True)]


def compare_exports(manifest: dict, official: dict, candidate: dict) -> dict:
    """Fail closed on incomplete exports, drift, or synthetic/engine mixing."""
    errors: list[str] = []
    result = {"schema_version": 1, "check": "backend_export_equivalence",
              "evidence_kind": None, "engine_location": None, "split": None,
              "provider_calls": 0, "real_outcomes_collected": False,
              "proof_limit": "Comparison of supplied preparation/mock exports only. Authentic collection, deployed access and execution approval require separate evidence. Transport failures need separate receipt validation."}
    try:
        if any(not isinstance(value, dict) for value in (manifest, official, candidate)):
            raise ValueError("manifest and both exports must be JSON objects")
        split = official.get("split")
        kind = "synthetic_fixture_validation" if official.get("evidence_kind") == "synthetic_fixture" else "engine_mock_export_comparison"
        result.update(evidence_kind=kind, engine_location=candidate.get("engine_location"), split=split,
                      selection_sha256=manifest.get("selection", {}).get("items_sha256"),
                      official_export_sha256=digest(official), candidate_export_sha256=digest(candidate))
        expected = selected_items(manifest, split)
        expected_by_id = {r["original_id"]: r for r in expected}
        if len(expected_by_id) != len(expected) or len(expected) != (15 if split == "smoke" else 60):
            errors.append("manifest has duplicate or incomplete development selection")
        if manifest["selection"]["items_sha256"] != digest(manifest["selection"]["items"]):
            errors.append("manifest selection digest mismatch")
        if official.get("evidence_kind") == "synthetic_fixture":
            if candidate.get("evidence_kind") != "synthetic_fixture":
                errors.append("synthetic official export cannot certify an engine export")
        elif (official.get("evidence_kind") != "upstream_task_mock"
              or candidate.get("evidence_kind") != "engine_mock"):
            errors.append("expected upstream_task_mock and engine_mock provenance")
        records_by_side = {}
        for side, export in (("official", official), ("candidate", candidate)):
            if export.get("schema_version") != 1 or type(export.get("schema_version")) is not int:
                errors.append(f"{side}: unsupported export schema")
            if export.get("role") != side:
                errors.append(f"{side}: incorrect export role")
            if export.get("provider_calls") != 0 or type(export.get("provider_calls")) is not int:
                errors.append(f"{side}: export must positively record zero provider calls")
            if export.get("real_outcomes_collected") is not False:
                errors.append(f"{side}: export must be mock-only")
            if export.get("split") != split:
                errors.append(f"{side}: split mismatch")
            if export.get("dataset_revision") != manifest["dataset"]["revision"]:
                errors.append(f"{side}: dataset revision mismatch")
            if export.get("selection_sha256") != manifest["selection"]["items_sha256"]:
                errors.append(f"{side}: selection digest mismatch")
            if not SHA256.fullmatch(export.get("exporter_source_sha256") or ""):
                errors.append(f"{side}: exporter source hash missing")
            if export.get("source_case_id_namespace") != "lab-bench-original-id":
                errors.append(f"{side}: unsupported source case namespace")
            if not REVISION.fullmatch(export.get("exporter_revision") or ""):
                errors.append(f"{side}: exporter revision missing")
            dirty = export.get("exporter_worktree_dirty")
            if type(dirty) is not bool:
                errors.append(f"{side}: exporter worktree state missing")
            revision_kind = "checkout_base_with_uncommitted_changes" if dirty else "clean_checkout_commit"
            if export.get("exporter_revision_kind") != revision_kind:
                errors.append(f"{side}: exporter revision provenance conflicts with worktree state")
            preparation = export["preparation"]
            if export.get("preparation_sha256") != digest(preparation):
                errors.append(f"{side}: preparation digest mismatch")
            for key, value in manifest["upstream_task"].items():
                if preparation.get(key) != value or type(preparation.get(key)) is not type(value):
                    errors.append(f"{side}: pinned preparation field differs: {key}")
            for key in PREPARATION_HASH_FIELDS:
                if not SHA256.fullmatch(preparation.get(key) or ""):
                    errors.append(f"{side}: missing source hash: {key}")
            records = export["records"]
            by_id = {r["original_id"]: r for r in records}
            records_by_side[side] = by_id
            if len(by_id) != len(records):
                errors.append(f"{side}: duplicate original IDs")
            if set(by_id) != set(expected_by_id):
                errors.append(f"{side}: selected IDs differ (missing={len(set(expected_by_id)-set(by_id))}, extra={len(set(by_id)-set(expected_by_id))})")
            source_ids, variant_ids = [], []
            for row in records:
                original_id = row["original_id"]
                if original_id in expected_by_id and row.get("category") != expected_by_id[original_id]["subset"]:
                    errors.append(f"{side}: category mismatch for {original_id}")
                for key in ("original_id", "source_case_id", "variant_case_id"):
                    if not isinstance(row.get(key), str) or not row[key]:
                        errors.append(f"{side}: empty {key}")
                if row.get("source_case_id") != original_id:
                    errors.append(f"{side}: source_case_id differs from original_id in lab-bench-original-id namespace")
                source_ids.append(row["source_case_id"])
                variant_ids.append(row["variant_case_id"])
                for key in RECORD_FIELDS[2:]:
                    if not SHA256.fullmatch(row.get(key) or ""):
                        errors.append(f"{side}: missing {key} for {original_id}")
            if len(set(source_ids)) != len(source_ids) or len(set(variant_ids)) != len(variant_ids):
                errors.append(f"{side}: case mapping is not one to one")
            if export.get("selected_denominator") != len(expected) or type(export.get("selected_denominator")) is not int:
                errors.append(f"{side}: selected denominator mismatch")
            probes = export["scorer_probes"]
            if set(probes) != set(PROBE_SCORES):
                errors.append(f"{side}: missing or extra scorer probes")
            for name, score in PROBE_SCORES.items():
                probe = probes.get(name, {})
                if probe.get("score") != score:
                    errors.append(f"{side}: unexpected mock score for {name}")
                for key in ("input_sha256", "response_sha256"):
                    if not SHA256.fullmatch(probe.get(key) or ""):
                        errors.append(f"{side}: missing scorer probe {key}: {name}")
            if export.get("probe_aggregate") != {"n_samples": 4, "n_scored": 4, "score_counts": {"C": 1, "I": 2, "N": 1}}:
                errors.append(f"{side}: mock aggregation mismatch")
        if official["preparation"] != candidate["preparation"]:
            errors.append("official and candidate preparation differ")
        for original_id in set(records_by_side["official"]) & set(records_by_side["candidate"]):
            left, right = records_by_side["official"][original_id], records_by_side["candidate"][original_id]
            for key in RECORD_FIELDS:
                if left.get(key) != right.get(key):
                    errors.append(f"{original_id}: {key} mismatch")
        if official["scorer_probes"] != candidate["scorer_probes"]:
            errors.append("official and candidate scorer probes differ")
        if candidate.get("engine_location") not in ("local", "hosted"):
            errors.append("candidate engine location missing")
        if not REVISION.fullmatch(candidate.get("engine_revision") or ""):
            errors.append("candidate engine revision missing")
        cache = candidate["cache_identity"]
        if not isinstance(cache.get("variant_id"), str) or not cache["variant_id"]:
            errors.append("candidate variant identity missing")
        if not SHA256.fullmatch(cache.get("variant_revision") or ""):
            errors.append("candidate variant revision missing")
        for key, value in (("split", split), ("selection_sha256", manifest["selection"]["items_sha256"]),
                           ("preparation_sha256", candidate["preparation_sha256"])):
            if cache.get(key) != value:
                errors.append(f"candidate cache identity does not bind {key}")
        result["selected_ids"] = sorted(expected_by_id)
        result["selected_count"] = len(expected)
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        errors.append(f"malformed backend export: {exc}")
    result["errors"] = sorted(set(errors))
    result["passed"] = not errors
    result["coverage"] = {key: not errors for key in COVERAGE}
    return result
