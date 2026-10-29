"""Offline execution evidence checks, separate from specification approval.

This module never calls a model or reads a held-out outcome file. It verifies
local files and their declared provenance, not the authenticity of an approval,
provider bill, engine export or wall-clock timestamp. A passing report is not an
execution command or new permission to spend money.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
from collections import defaultdict
from statistics import mean

from .empirical import PRIMARY_TARGET, TARGETS, digest


STAGES = ("specification", "development_smoke", "development_collection", "held_out")
COMMON = ("manifest", "specification")
EXECUTION = ("backend_equivalence", "model_manifest", "pricing_manifest", "spending_approval")
FINAL = ("development_collection", "fitted_method", "routing_overhead", "selected_policies",
         "route_table", "analysis_bundle", "held_out_lock")
REQUIRED = {
    "specification": COMMON,
    "development_smoke": COMMON + EXECUTION,
    "development_collection": COMMON + EXECUTION + ("development_smoke",),
    "held_out": COMMON + EXECUTION + ("development_smoke",) + FINAL,
}
HASH = re.compile(r"[a-f0-9]{64}\Z")
COMMIT = re.compile(r"[a-f0-9]{40}\Z")
REQUIRED_SOURCE_FILES = {"src/crr/empirical.py", "src/crr/analysis.py", "src/crr/oracle.py"}


class EvidenceError(ValueError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value.strip().lower() not in {
        "pending", "unknown", "tbd", "placeholder", "unresolved"}


def _number(value: object, *, positive: bool = False) -> bool:
    return (type(value) in (int, float) and math.isfinite(value)
            and (value > 0 if positive else value >= 0))


def _same_ids(actual: object, expected: set[str]) -> bool:
    return (isinstance(actual, list) and all(isinstance(x, str) for x in actual)
            and len(actual) == len(set(actual)) and set(actual) == expected)


def _load(reference: object, root: Path) -> tuple[dict, str]:
    _require(isinstance(reference, dict) and set(reference) == {"path", "sha256"},
             "requires a path and file-byte SHA-256 reference")
    _require(_text(reference["path"]) and isinstance(reference["sha256"], str)
             and HASH.fullmatch(reference["sha256"]) is not None, "malformed artifact reference")
    path = Path(reference["path"])
    path = path if path.is_absolute() else root / path
    _require(path.is_file(), "referenced artifact is missing")
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    _require(actual == reference["sha256"], "artifact file-byte hash mismatch")
    try:
        value = json.loads(raw, parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    except (UnicodeError, ValueError) as exc:
        raise EvidenceError("artifact must contain finite JSON") from exc
    _require(isinstance(value, dict), "artifact must contain a JSON object")
    return value, actual


def _check_file_hashes(documents: object, root: Path) -> None:
    _require(isinstance(documents, dict) and bool(documents), "document hashes are missing")
    for name, expected in documents.items():
        _require(_text(name) and isinstance(expected, str) and HASH.fullmatch(expected) is not None,
                 "invalid document hash reference")
        path = Path(name)
        path = path if path.is_absolute() else root / path
        _require(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == expected,
                 f"document changed or is missing: {name}")


def _check_method_source_hashes(documents: object, root: Path) -> None:
    _require(isinstance(documents, dict) and REQUIRED_SOURCE_FILES <= set(documents),
             "implementation hashes must include empirical.py, analysis.py and oracle.py")
    _check_file_hashes(documents, root)


def _check_specification(spec: dict, manifest: dict, root: Path) -> None:
    _require(spec.get("status") == "specification_approved", "specification approval is not recorded")
    _require(spec.get("execution_authorized") is False, "specification approval must not authorize execution")
    _require(COMMIT.fullmatch(spec.get("approved_commit", "")) is not None,
             "approved commit is missing")
    for field in ("approved_by", "approval_url", "approved_at"):
        _require(_text(spec.get(field)), f"specification {field} is missing")
    required = {"docs/experiment-01/METHOD.md", "docs/experiment-01/ANALYSIS.md",
                "docs/experiment-01/method-plan.json"}
    _require(set(spec.get("documents", {})) == required, "approval must bind method, analysis and method plan")
    _check_file_hashes(spec["documents"], root)
    _require(spec.get("selection_sha256") == manifest["selection"]["items_sha256"],
             "approval selection differs from manifest")


def _check_backend(value: dict, manifest: dict, root: Path) -> None:
    _require(value.get("check") == "backend_export_equivalence" and value.get("passed") is True,
             "backend equivalence comparison has not passed")
    _require(value.get("evidence_kind") == "engine_mock_export_comparison",
             "synthetic backend fixtures cannot establish engine equivalence")
    _require(value.get("provider_calls") == 0, "backend equivalence must use mock scoring, not provider outcomes")
    _require(value.get("engine_location") in {"local", "hosted"}, "backend location is unresolved")
    _require(value.get("selection_sha256") == manifest["selection"]["items_sha256"],
             "backend selection differs from manifest")
    split = value.get("split")
    _require(split in {"development", "smoke"}, "backend equivalence must use development or smoke selection")
    expected = {x["original_id"] for x in manifest["selection"]["items"]
                if x["split"] == "development" and (split == "development" or x["smoke"])}
    _require(_same_ids(value.get("selected_ids"), expected), "backend selected IDs differ from manifest")
    _require(value.get("selected_count") == len(expected), "backend selected denominator differs")
    checks = value.get("coverage", {})
    for key in ("category", "selected_ids", "prepared_input", "choice_order", "target_mapping",
                "scorer", "aggregation", "cache_identity"):
        _require(checks.get(key) is True, f"backend equivalence lacks {key} comparison")
    sources = value.get("source_files", {})
    _require(set(sources) == {"official", "candidate", "manifest"}, "backend source export references are missing")
    exports = {name: _load(reference, root)[0] for name, reference in sources.items()}
    _require(exports["manifest"] == manifest, "backend source manifest differs from readiness manifest")
    from .backend_equivalence import compare_exports
    computed = compare_exports(manifest, exports["official"], exports["candidate"])
    _require(computed["passed"] is True, "backend source exports fail recomputed comparison: " + "; ".join(computed["errors"]))
    for key in ("evidence_kind", "engine_location", "split", "selection_sha256", "selected_count",
                "coverage", "official_export_sha256", "candidate_export_sha256"):
        _require(value.get(key) == computed[key], f"backend report differs from recomputed {key}")
    _require(set(value["selected_ids"]) == set(computed["selected_ids"]), "backend report selected IDs differ from recomputation")


def _check_models(value: dict, manifest: dict) -> None:
    _require(value.get("evidence_kind") == "model_configuration_manifest", "model manifest has wrong evidence kind")
    models = value.get("models", [])
    slots = {x["slot"] for x in manifest["models"]}
    _require(isinstance(models, list) and len(models) == 4 and all(isinstance(x, dict) for x in models) and
             {x.get("slot") for x in models} == slots, "four exact model slots are required")
    for model in models:
        for key in ("api_id", "version", "provider_route"):
            _require(_text(model.get(key)), f"{model.get('slot')}: {key} unresolved")
        settings = model.get("generation_settings")
        _require(isinstance(settings, dict) and bool(settings), "explicit generation settings are required")
        _require("reasoning" in settings and "max_output_tokens" in settings,
                 "generation settings must declare reasoning and max_output_tokens behavior")
        _require(type(settings["max_output_tokens"]) is int and settings["max_output_tokens"] > 0,
                 "max_output_tokens must be an explicit positive integer")
        reasoning = settings["reasoning"]
        _require(_text(reasoning) or (isinstance(reasoning, dict) and bool(reasoning)
                 and all(_text(k) and (_text(v) or type(v) is bool or (type(v) is int and v >= 0))
                         for k, v in reasoning.items())),
                 "reasoning configuration must be explicit, including disabled or unsupported")
        defaults = model.get("declared_provider_defaults", {})
        _require(isinstance(defaults, dict), "declared_provider_defaults must be an object")
        for name, setting in settings.items():
            if setting is None:
                _require(_text(defaults.get(name)), f"null {name} requires an explicit provider-default declaration")
            if name == "temperature" and setting is not None:
                _require(_number(setting), "temperature must be finite and nonnegative")
            if name == "seed" and setting is not None:
                _require(type(setting) is int, "seed must be an integer or an explicit provider default")
        retry = model.get("retry", {})
        _require(isinstance(retry, dict), "retry must be an object")
        _require(type(retry.get("max_attempts")) is int and retry["max_attempts"] >= 1,
                 "retry max_attempts must be explicit")
        _require(_number(model.get("timeout_seconds"), positive=True), "positive timeout_seconds is required")
        _require(isinstance(retry.get("retryable_errors"), list)
                 and all(_text(x) for x in retry["retryable_errors"]), "retryable_errors must be explicit strings")
        _require(isinstance(model.get("route_fallbacks"), list)
                 and all(_text(x) for x in model["route_fallbacks"]), "route_fallbacks must be explicit strings, including an empty list")
        if "backoff_seconds" in retry:
            _require(_number(retry["backoff_seconds"]), "retry backoff must be finite and nonnegative")


def _check_prices(value: dict, models: dict, hashes: dict[str, str]) -> None:
    _require(value.get("evidence_kind") == "pricing_manifest" and value.get("currency") == "USD",
             "a USD pricing manifest is required")
    _require(value.get("model_manifest_sha256") == hashes["model_manifest"], "pricing uses a different model manifest")
    rates = value.get("models", {})
    _require(set(rates) == {x["slot"] for x in models["models"]}, "pricing must cover every model slot")
    for slot, entry in rates.items():
        for key in ("input_per_million_tokens_usd", "output_per_million_tokens_usd"):
            _require(_number(entry.get(key)), f"{slot}: missing or invalid {key}")
        for key in ("source_url", "retrieved_at", "reasoning_billing", "cache_billing", "failed_attempt_billing"):
            _require(_text(entry.get(key)), f"{slot}: missing {key}")
    boundary = value.get("cost_boundary", {})
    _require(boundary.get("inference") == "all_attempts" and boundary.get("credits") == "billing_only"
             and boundary.get("routing") == "feature_prediction_selection_dispatch",
             "pricing must preserve all-attempt, credit and routing cost boundaries")


def _check_spending(value: dict, stage: str, hashes: dict[str, str]) -> None:
    _require(value.get("evidence_kind") == "spending_approval", "spending approval is not recorded")
    for key in ("approved_by", "approved_at", "source"):
        _require(_text(value.get(key)), f"spending approval {key} is missing")
    _require(isinstance(value.get("scopes"), list) and stage in value["scopes"],
             f"spending approval does not cover {stage}")
    _require(_number(value.get("limits_usd", {}).get(stage), positive=True),
             f"approved positive {stage} spending limit is missing")
    for name in ("model_manifest", "pricing_manifest"):
        _require(value.get(name + "_sha256") == hashes[name], f"spending approval refers to a different {name}")


def _ledger_observations(ledger: dict, manifest: dict, ids: set[str], models: dict,
                         price_hash: str) -> list[dict]:
    """Recheck the concrete attempt graph and derive every terminal matrix row."""
    _require(ledger.get("evidence_kind") == "provider_attempt_ledger"
             and ledger.get("data_kind") == "measured_development", "receipt ledger is not measured development")
    rows = ledger.get("receipts")
    _require(isinstance(rows, list) and bool(rows) and all(isinstance(r, dict) for r in rows),
             "receipt ledger must contain nonempty attempt records")
    entries = {x["original_id"]: x for x in manifest["selection"]["items"]}
    roster = {x["slot"]: x for x in models["models"]}
    calls, chains = set(), defaultdict(list)
    for row in rows:
        call = row.get("call_id")
        _require(_text(call) and call not in calls, "receipt call IDs must be present and unique")
        calls.add(call)
        item, slot = row.get("original_item_id"), row.get("model_slot")
        _require(item in ids and slot in roster, "receipt has an unexpected item or model")
        _require(row.get("split") == "development" and row.get("subset") == entries[item]["subset"]
                 and row.get("purpose") == "answer", "receipt split/category/purpose differs")
        _require(row.get("manifest_sha256") == digest(manifest), "receipt manifest hash differs")
        _require(type(row.get("attempt_index")) is int and row["attempt_index"] >= 1, "invalid attempt index")
        _require(row.get("status") in {"success", "error", "timeout", "refusal", "parse_error", "abstained"},
                 "invalid receipt attempt status")
        model = roster[slot]
        identity = row.get("model", {})
        expected_settings = {key: model[key] for key in
                             ("generation_settings", "retry", "timeout_seconds", "route_fallbacks")}
        _require(identity.get("requested_id") == model["api_id"]
                 and identity.get("provider_route") == model["provider_route"]
                 and identity.get("effective_id") == model["api_id"]
                 and identity.get("effective_version") == model["version"]
                 and identity.get("settings_sha256") == digest(expected_settings), "receipt model/settings mismatch")
        cost = row.get("cost", {})
        _require(cost.get("currency") == "USD" and cost.get("pricing_sha256") == price_hash
                 and _number(cost.get("estimated_usd")) and _text(cost.get("source")),
                 "receipt all-attempt frozen-price amount is unresolved")
        _require(cost.get("billed_usd") is None or _number(cost["billed_usd"]), "invalid actual billed amount")
        grade = row.get("outcome", {}).get("grade")
        if row["status"] == "success":
            _require(grade in {"C", "I"}, "successful terminal parsing needs an official correct/incorrect grade")
        elif row["status"] == "abstained":
            _require(grade == "N", "abstained receipt must retain upstream N grade")
        else:
            _require(grade in {None, "I"}, "failed or malformed attempt cannot claim a correct grade")
        chains[item, slot].append(row)
    _require(set(chains) == {(item, model) for item in ids for model in roster},
             "receipt ledger does not cover the complete assigned item/model matrix")
    terminal = []
    for (item, slot), chain in sorted(chains.items()):
        chain.sort(key=lambda x: x["attempt_index"])
        _require([x["attempt_index"] for x in chain] == list(range(1, len(chain) + 1)),
                 "receipt attempt indices are duplicated or not contiguous")
        _require(len(chain) <= roster[slot]["retry"]["max_attempts"], "receipt exceeds frozen retry maximum")
        previous = None
        for index, row in enumerate(chain):
            _require(row.get("previous_attempt_id") == previous, "receipt retry links are broken")
            if index < len(chain) - 1:
                _require(row["status"] in {"error", "timeout", "refusal", "parse_error"},
                         "a completed answered/abstained call was retried as the same observation")
            previous = row["call_id"]
        final = chain[-1]
        status = {"success": "answered", "abstained": "abstained", "parse_error": "malformed"}.get(final["status"], "failed")
        terminal.append({"item_id": item, "model": slot, "solved": final["outcome"]["grade"] == "C",
                         "response_status": status, "cost_usd": sum(x["cost"]["estimated_usd"] for x in chain)})
    return terminal


def _check_development(value: dict, manifest: dict, hashes: dict[str, str], root: Path,
                       models: dict, *, smoke: bool) -> None:
    expected_kind = "measured_development_smoke" if smoke else "reconciled_development_collection"
    _require(value.get("evidence_kind") == expected_kind and value.get("data_kind") == "measured_development",
             "real development evidence is required; synthetic fixtures do not clear this gate")
    _require(value.get("passed") is True and value.get("held_out_outcomes_seen") is False,
             "development validation failed or held-out exposure is not explicitly false")
    ids = {x["original_id"] for x in manifest["selection"]["items"]
           if x["split"] == "development" and (not smoke or x["smoke"])}
    _require(_same_ids(value.get("selected_ids"), ids), "development record does not cover the exact assigned IDs")
    _require(value.get("terminal_rows") == len(ids) * 4, "development terminal matrix is incomplete")
    for name in ("model_manifest", "pricing_manifest", "backend_equivalence"):
        _require(value.get(name + "_sha256") == hashes[name], f"development record uses a different {name}")
    ledger, ledger_hash = _load(value.get("receipt_ledger"), root)
    terminal = _ledger_observations(ledger, manifest, ids, models, hashes["pricing_manifest"])
    reconciliation, _ = _load(value.get("reconciliation"), root)
    _require(reconciliation.get("evidence_kind") == "development_receipt_reconciliation"
             and reconciliation.get("data_kind") == "measured_development"
             and reconciliation.get("passed") is True, "measured receipt reconciliation is missing")
    _require(reconciliation.get("receipt_ledger_sha256") == ledger_hash, "receipt reconciliation uses a different ledger")
    _require(reconciliation.get("terminal_rows") == len(ids) * 4, "reconciliation terminal denominator differs")
    _require(reconciliation.get("terminal_observations_sha256") == digest(terminal),
             "reconciliation terminal observations differ from concrete attempt records")
    for key in ("missing_cost_rows", "configuration_mismatches", "duplicate_calls", "broken_attempt_chains",
                "unexpected_items", "missing_terminal_rows"):
        _require(type(reconciliation.get(key)) is int and reconciliation[key] == 0,
                 f"receipt reconciliation unresolved: {key}")
    if not smoke:
        bundle, _ = _load(value.get("terminal_bundle"), root)
        _require(bundle.get("data_kind") == "measured_development", "terminal bundle is not measured development")
        observations = bundle.get("observations", [])
        _require(isinstance(observations, list) and all(isinstance(r, dict) for r in observations),
                 "terminal observations must be a list of records")
        _require(sorted(observations, key=lambda x: (x["item_id"], x["model"])) == terminal,
                 "terminal bundle differs from receipt-derived outcomes/costs")


def _check_fit(fit: dict, manifest: dict, hashes: dict[str, str], collection: dict, root: Path) -> None:
    _require(fit.get("provenance", {}).get("data_kind") == "measured_development",
             "final fit must use real development data, not fixtures")
    _require(fit.get("status") == "development_fit_not_execution_approval", "unrecognized fitted-method status")
    ids = {x["original_id"] for x in manifest["selection"]["items"] if x["split"] == "development"}
    _require(_same_ids(fit.get("training_ids"), ids), "final fit training IDs differ from development selection")
    _require(fit.get("manifest_sha256") == digest(manifest), "final fit uses a different manifest")
    _require(fit.get("method_plan_sha256") == manifest["method"]["plan_sha256"], "final fit method plan differs")
    bundle, bundle_hash = _load(collection.get("terminal_bundle"), root)
    _require(bundle.get("data_kind") == "measured_development", "terminal bundle is not real development")
    _require(collection.get("terminal_bundle_sha256") == bundle_hash, "collection terminal-bundle binding differs")
    questions, observations = bundle.get("questions", []), bundle.get("observations", [])
    _require(_same_ids([x.get("item_id") for x in questions], ids), "terminal bundle input IDs differ")
    expected = {(i, x["slot"]) for i in ids for x in manifest["models"]}
    actual = [(x.get("item_id"), x.get("model")) for x in observations]
    _require(len(actual) == len(expected) and set(actual) == expected, "terminal bundle matrix differs")
    _require(fit.get("training_inputs_sha256") == digest(sorted(questions, key=lambda x: x["item_id"])),
             "fit input hash differs from reconciled development bundle")
    _require(fit.get("training_outcomes_sha256") == digest(sorted(observations, key=lambda x: (x["item_id"], x["model"]))),
             "fit outcome hash differs from reconciled development bundle")
    _require(fit.get("provenance", {}).get("pricing_sha256") == hashes["pricing_manifest"],
             "fit frozen prices differ from operational price artifact")
    _check_method_source_hashes(fit.get("source_sha256"), root)


def _check_overhead(value: dict, fit: dict, root: Path | None = None) -> None:
    _require(value.get("record_type") == "local_routing_overhead", "routing overhead record is missing")
    _require(value.get("data_kind") == value.get("fit_data_kind") == "measured_development",
             "synthetic timings are preliminary and cannot satisfy the full overhead gate")
    _require(value.get("fit_sha256") == digest(fit), "routing overhead was measured for a different fitted method")
    _require(value.get("split") == "development" and _same_ids(value.get("input_ids"), set(fit["training_ids"])),
             "routing overhead needs the exact development input set")
    _require(value.get("input_sha256") == fit.get("training_inputs_sha256")
             and HASH.fullmatch(value.get("input_sha256", "")) is not None,
             "routing measurement inputs differ from final fitted development inputs")
    _require(_number(value.get("router_cpu_usd_per_second"), positive=True),
             "positive primary CPU-dollar rate is missing")
    _require(type(value.get("warmup_passes")) is int and value["warmup_passes"] >= 1
             and type(value.get("measurement_passes")) is int and value["measurement_passes"] >= 2,
             "routing measurement needs warm-up and repeated measurements")
    _require(isinstance(value.get("environment"), dict) and bool(value["environment"]),
             "routing measurement environment is missing")
    _require({"category", "crr"} <= set(value.get("families", {})), "routing families were not measured separately")
    _require(value.get("backend_dispatch_measured") is True
             and value.get("total_deployable_overhead_available") is True,
             "local serialization timing does not cover actual backend dispatch")
    _require(root is not None, "backend dispatch evidence root is required")
    dispatch, _ = _load(value.get("backend_dispatch_evidence"), root)
    _require(dispatch.get("record_type") == "backend_dispatch_measurement"
             and dispatch.get("data_kind") == "measured_development"
             and dispatch.get("boundary") == "backend_adapter_dispatch"
             and dispatch.get("fit_sha256") == digest(fit)
             and dispatch.get("input_sha256") == value["input_sha256"],
             "backend dispatch evidence has the wrong provenance, boundary, fit or inputs")
    _check_file_hashes(dispatch.get("source_sha256"), root)
    families = value["families"]
    raw, dispatch_raw = value.get("raw_samples"), dispatch.get("raw_samples")
    _require(isinstance(raw, list) and bool(raw) and all(isinstance(r, dict) for r in raw),
             "overhead needs actual nonempty per-query timing records")
    _require(isinstance(dispatch_raw, list) and bool(dispatch_raw) and all(isinstance(r, dict) for r in dispatch_raw),
             "backend dispatch needs actual nonempty timing records")
    expected = {(family, item, repeat) for family in ("category", "crr")
                for item in fit["training_ids"] for repeat in range(value["measurement_passes"])}
    def indexed(records):
        result = {(r.get("family"), r.get("item_id"), r.get("repeat")): r for r in records}
        _require(len(result) == len(records) and set(result) == expected, "timing records have missing/duplicate family-item-repetition cells")
        for row in records:
            _require(type(row.get("repeat")) is int, "timing repetition must be an integer")
        return result
    timed, dispatched = indexed(raw), indexed(dispatch_raw)
    for key, row in timed.items():
        _require(row.get("backend_dispatch") == {k: dispatched[key].get(k) for k in ("elapsed_ns", "cpu_ns")},
                 "combined overhead dispatch times differ from backend measurements")
        for component in ("prediction", "selection", "local_dispatch_preparation", "backend_dispatch", "total"):
            part = row.get(component, {})
            _require(isinstance(part, dict) and all(type(part.get(k)) is int and part[k] >= 0
                     for k in ("elapsed_ns", "cpu_ns")), "overhead component timing is missing or invalid")
        for clock in ("elapsed_ns", "cpu_ns"):
            _require(row["total"][clock] == sum(row[c][clock] for c in
                     ("prediction", "selection", "local_dispatch_preparation", "backend_dispatch")),
                     "overhead total does not sum measured components")
    for family in ("category", "crr"):
        rows = [r for key, r in timed.items() if key[0] == family]
        totals = families[family].get("components", {}).get("total", {})
        _require(totals.get("samples") == len(rows), "overhead family summary denominator differs")
        for clock in ("elapsed_ns", "cpu_ns"):
            observed = totals.get(clock, {}).get("mean")
            expected_mean = mean(r["total"][clock] for r in rows)
            _require(_number(observed) and math.isclose(observed, expected_mean, rel_tol=1e-12, abs_tol=1e-9),
                     "overhead family summary differs from raw timings")
        _require(totals["elapsed_ns"]["mean"] > 0, "overhead elapsed timing cannot be identically zero")
        cost = totals.get("mean_local_cpu_cost_usd")
        expected_cost = totals["cpu_ns"]["mean"] / 1e9 * value["router_cpu_usd_per_second"]
        _require(_number(cost) and math.isclose(cost, expected_cost, rel_tol=1e-12, abs_tol=1e-15),
                 "overhead cost does not match measured CPU time and declared rate")


def _check_policies(value: dict, fit: dict, hashes: dict[str, str]) -> None:
    _require(value.get("evidence_kind") == "frozen_selected_policies", "selected-policy artifact is missing")
    _require(value.get("fit_artifact_sha256") == hashes["fitted_method"], "policies use a different fit artifact")
    _require(value.get("selections") == fit.get("selections") and set(value.get("selections", {})) == {"category", "crr"},
             "selected policies differ from the final development fit")


def _check_routes(value: dict, fit: dict, manifest: dict, hashes: dict[str, str]) -> None:
    _require(value.get("evidence_kind") == "pre_outcome_route_table"
             and value.get("held_out_outcomes_seen") is False, "route table must precede held-out outcomes")
    _require(value.get("fit_artifact_sha256") == hashes["fitted_method"]
             and value.get("selected_policies_sha256") == hashes["selected_policies"], "route table uses another fit or policies")
    ids = {x["original_id"] for x in manifest["selection"]["items"] if x["split"] == "held_out"}
    roster = {p["model"] for p in fit["profiles"]}
    plans = value.get("plans", [])
    _require(isinstance(plans, list) and all(isinstance(p, dict) for p in plans) and len(plans) == 2 * len(TARGETS)
             and {(p.get("family"), p.get("target")) for p in plans} ==
             {(f, t) for f in ("category", "crr") for t in TARGETS}, "route plans must preserve every declared family/target")
    for plan in plans:
        _require(plan.get("target_role") == ("primary" if plan["target"] == PRIMARY_TARGET else "secondary"),
                 "route plan target role differs from frozen designation")
        selected = next(s["selected"] for s in fit["selections"][plan["family"]] if s["target"] == plan["target"])
        if selected is None:
            _require(plan.get("status") == "unattainable_on_development" and plan.get("routes") is None,
                     "unattainable development target was replaced with a route")
            continue
        _require(plan.get("fit_sha256") == digest(fit) and plan.get("threshold") == selected["threshold"],
                 "route plan uses a different fit or threshold")
        rows = plan.get("routes", {})
        _require(isinstance(rows, dict) and set(rows) == ids, "route table lacks the exact held-out assignment")
        _require(plan.get("status") == "planned_not_execution_approval", "unexpected route plan status")
        for row in rows.values():
            _require(isinstance(row, dict) and set(row) == {"model", "probability", "expected_cost_usd", "threshold_met"},
                     "route row has missing or unexpected selection fields")
            _require(row["model"] in roster, "route selected a model outside the fitted roster")
            _require(_number(row["probability"]) and row["probability"] <= 1,
                     "route probability is invalid")
            _require(_number(row["expected_cost_usd"]), "route expected cost is invalid")
            _require(type(row["threshold_met"]) is bool, "route threshold_met must be boolean")
        _require(plan.get("routes_sha256") == digest(rows), "route rows hash mismatch")
        _require(HASH.fullmatch(plan.get("visible_inputs_sha256", "")) is not None, "route input hash is missing")


def _check_analysis(value: dict, spec: dict, hashes: dict[str, str], root: Path) -> None:
    _require(value.get("evidence_kind") == "pre_outcome_analysis_bundle"
             and value.get("held_out_outcomes_seen") is False, "analysis bundle must precede held-out outcomes")
    _require(value.get("primary_target") == PRIMARY_TARGET and value.get("targets") == list(TARGETS),
             "analysis target designations changed")
    _require(value.get("documents") == spec["documents"], "analysis documents differ from the approved specification")
    _require(COMMIT.fullmatch(value.get("implementation_revision", "")) is not None, "analysis implementation revision is missing")
    for name in ("fitted_method", "selected_policies", "route_table", "pricing_manifest"):
        _require(value.get(name + "_sha256") == hashes[name], f"analysis refers to another {name}")
    _check_method_source_hashes(value.get("source_sha256"), root)


def _check_lock(value: dict, hashes: dict[str, str]) -> None:
    _require(value.get("evidence_kind") == "held_out_precollection_lock"
             and value.get("held_out_outcomes_seen") is False, "held-out precollection lock is missing")
    _require(_text(value.get("locked_at")) and _text(value.get("recorded_by")), "lock timestamp/recorder are missing")
    expected = {name: hashes[name] for name in REQUIRED["held_out"] if name != "held_out_lock"}
    _require(value.get("artifacts") == expected, "lock must bind every current evidence file, including selected policies/routes/analysis")


def check_readiness(config: dict, root: Path) -> dict:
    """Read only referenced evidence; never fetch approvals or execute anything."""
    root = Path(root)
    documents, hashes, load_errors = {}, {}, {}
    references = config.get("evidence", {}) if isinstance(config, dict) else {}
    config_errors = []
    if not isinstance(config, dict) or type(config.get("schema_version")) is not int or config.get("schema_version") != 1:
        config_errors.append("readiness configuration schema_version must be 1")
    if not isinstance(references, dict):
        config_errors.append("evidence must be an object")
        references = {}
    if not isinstance(config, dict) or config.get("held_out_outcomes_seen") is not False:
        config_errors.append("held-out outcome exposure must be explicitly false")
    for name in set().union(*map(set, REQUIRED.values())):
        if references.get(name) is None:
            load_errors[name] = "unresolved artifact"
            continue
        try:
            documents[name], hashes[name] = _load(references[name], root)
        except (EvidenceError, OSError) as exc:
            load_errors[name] = str(exc)

    results = {}
    for stage, needed in REQUIRED.items():
        errors = list(config_errors)
        errors.extend(f"{name}: {load_errors[name]}" for name in needed if name in load_errors)
        checks = []
        if "manifest" in documents:
            manifest = documents["manifest"]
            try:
                _require(manifest["selection"]["items_sha256"] == digest(manifest["selection"]["items"]),
                         "selection hash mismatch")
                _require(manifest["method"]["held_out_outcomes_seen"] is False, "manifest does not attest untouched held-out outcomes")
                checks.append(("specification", lambda: _check_specification(documents["specification"], manifest, root)))
                if stage != "specification":
                    checks += [
                        ("backend_equivalence", lambda: _check_backend(documents["backend_equivalence"], manifest, root)),
                        ("model_manifest", lambda: _check_models(documents["model_manifest"], manifest)),
                        ("pricing_manifest", lambda: _check_prices(documents["pricing_manifest"], documents["model_manifest"], hashes)),
                        ("spending_approval", lambda: _check_spending(documents["spending_approval"], stage, hashes)),
                    ]
                if stage in {"development_collection", "held_out"}:
                    checks.append(("development_smoke", lambda: _check_development(documents["development_smoke"], manifest, hashes, root, documents["model_manifest"], smoke=True)))
                if stage == "held_out":
                    checks += [
                        ("development_collection", lambda: _check_development(documents["development_collection"], manifest, hashes, root, documents["model_manifest"], smoke=False)),
                        ("fitted_method", lambda: _check_fit(documents["fitted_method"], manifest, hashes, documents["development_collection"], root)),
                        ("routing_overhead", lambda: _check_overhead(documents["routing_overhead"], documents["fitted_method"], root)),
                        ("selected_policies", lambda: _check_policies(documents["selected_policies"], documents["fitted_method"], hashes)),
                        ("route_table", lambda: _check_routes(documents["route_table"], documents["fitted_method"], manifest, hashes)),
                        ("analysis_bundle", lambda: _check_analysis(documents["analysis_bundle"], documents["specification"], hashes, root)),
                        ("held_out_lock", lambda: _check_lock(documents["held_out_lock"], hashes)),
                    ]
            except (EvidenceError, KeyError, TypeError, ValueError, AttributeError) as exc:
                errors.append(f"manifest: malformed or invalid ({exc})")
        for name, check in checks:
            if name not in documents:
                continue
            try:
                check()
            except KeyError as exc:
                errors.append(f"{name}: missing evidence field or prerequisite {exc}")
            except (EvidenceError, OSError, TypeError, ValueError, AttributeError, StopIteration) as exc:
                errors.append(f"{name}: {exc}")
        results[stage] = {"local_prerequisites_satisfied": not errors, "blockers": sorted(set(errors))}
    return {"schema_version": 1, "check": "execution_readiness", "stages": results,
            "artifact_file_sha256": hashes, "provider_calls": 0, "execution_authorized_by_this_check": False,
            "proof_limit": "Verifies local file bytes, declared provenance and cross-artifact consistency. Does not independently authenticate external approvals, engine operation, receipts, timestamps or provider availability. Never authorizes model execution."}
