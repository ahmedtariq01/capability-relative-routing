"""Check the review proposal against its captured evidence, entirely offline.

This checks cross-artifact consistency, not provider access, deployed behavior,
authentic approvals, measured billing, or permission to execute the study.
It reads files only and performs no network or model calls.
"""
from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import sys


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def obj(value: object, name: str) -> dict:
    require(isinstance(value, dict), f"{name} must be an object")
    return value


def array(value: object, name: str) -> list:
    require(isinstance(value, list), f"{name} must be an array")
    return value


def load(path: Path) -> dict:
    def reject_constant(value: str) -> None:
        raise ValueError(f"Non-finite JSON constant: {value}")
    return obj(json.loads(path.read_text(), parse_constant=reject_constant), str(path))


def number(value: object, name: str) -> Decimal:
    require(not isinstance(value, bool) and isinstance(value, (str, int, float, Decimal)),
            f"{name} must be numeric")
    result = Decimal(str(value))
    require(result.is_finite() and result >= 0, f"{name} must be finite and nonnegative")
    return result


def positive_int(value: object, name: str) -> int:
    require(type(value) is int and value > 0, f"{name} must be a positive integer")
    return value


def relative_file(root: Path, name: str) -> Path:
    require(isinstance(name, str) and bool(name), "Evidence path must be a nonempty string")
    path = (root / name).resolve()
    require(path.is_relative_to(root.resolve()), f"Evidence path escapes its root: {name}")
    return path


def check(repo: Path) -> dict:
    experiment = repo / "docs/experiment-01"
    proposal_dir = experiment / "execution-proposal"
    models = load(proposal_dir / "models.proposal.json")
    pricing = load(proposal_dir / "pricing.proposal.json")
    budget = load(proposal_dir / "budget-scenarios.json")
    evidence = load(proposal_dir / "source-evidence.json")
    catalogue_path = proposal_dir / "evidence/public-model-endpoints.json"
    audit_path = proposal_dir / "evidence/development-prompt-audit.json"
    catalogue = load(catalogue_path)
    audit = load(audit_path)
    manifest_path = experiment / "manifest.draft.json"
    manifest = load(manifest_path)
    freeze = load(experiment / "spec-freeze.json")
    reference = load(experiment / "backend/official-development.json")

    checks = []
    for name, expected_kind in (("models", "execution_model_proposal"),
                                ("pricing", "public_pricing_proposal"),
                                ("budget", "budget_scenarios")):
        record = {"models": models, "pricing": pricing, "budget": budget}[name]
        require(record.get("evidence_kind") == expected_kind, f"Wrong {name} evidence kind")
    require(models.get("execution_authorized") is False, "Model proposal must not authorize execution")
    require(freeze.get("execution_authorized") is False, "Specification approval must remain execution-disabled")
    require("UNAPPROVED" in str(models.get("status")), "Model proposal must remain unapproved")
    require("UNAPPROVED" in str(pricing.get("status")), "Price proposal must remain unapproved")
    require(budget.get("status") == "PROPOSAL_ONLY_NO_SPENDING_APPROVAL", "Budget must remain a proposal")
    funding = obj(budget.get("funding_proposal"), "funding_proposal")
    for name in ("approved_by", "approval_source", "approved_at", "funded_account", "full_collection_ceiling"):
        require(funding.get(name) is None, f"Proposal unexpectedly asserts funding field {name}")
    require(funding.get("current_balance_verified") is False, "No current balance is verified")
    require(obj(pricing.get("cpu_rate_proposal"), "CPU rate").get("approved") is False,
            "CPU rate must remain a proposal")
    checks.append("proposal_only_execution_and_funding_status")

    for name, expected in obj(freeze.get("documents"), "approved documents").items():
        require(sha(relative_file(repo, name)) == expected, f"Approved document changed: {name}")
    required_approved = {"docs/experiment-01/METHOD.md", "docs/experiment-01/ANALYSIS.md",
                         "docs/experiment-01/method-plan.json"}
    require(required_approved <= set(freeze["documents"]), "Missing approved method/analysis hashes")
    require(models.get("approved_manifest_sha256_unchanged") == sha(manifest_path), "Manifest binding mismatch")
    require(freeze.get("selection_sha256") == manifest["selection"]["items_sha256"], "Frozen selection changed")
    require(digest(manifest["selection"]["items"]) == manifest["selection"]["items_sha256"],
            "Selection membership does not match its frozen hash")
    checks.append("approved_method_analysis_plan_and_selection_preserved")

    for group, root in (("proposal_files", proposal_dir), ("source_files", proposal_dir),
                        ("approved_files_unchanged", experiment)):
        refs = obj(evidence.get(group), group)
        require(bool(refs), f"No {group} hashes")
        for name, expected in refs.items():
            require(sha(relative_file(root, name)) == expected, f"Recorded {group} hash mismatch: {name}")
    require({"models.proposal.json", "pricing.proposal.json", "budget-scenarios.json"}
            <= set(evidence["proposal_files"]), "Proposal hash coverage incomplete")
    require({"evidence/public-model-endpoints.json", "evidence/development-prompt-audit.json"}
            <= set(evidence["source_files"]), "Portable source evidence hashes missing")
    if "audit_script_sha256" in evidence:
        require(sha(repo / "scripts/audit_development_prompts.py") == evidence["audit_script_sha256"],
                "Development audit script hash mismatch")
    require(models.get("source_catalogue_sha256") == sha(catalogue_path), "Catalogue binding mismatch")
    require(pricing.get("models_proposal_sha256") == sha(proposal_dir / "models.proposal.json"),
            "Pricing/model proposal hash mismatch")
    checks.append("portable_source_and_proposal_hashes")

    proposal_models = array(models.get("models"), "models")
    require(len(proposal_models) == len(manifest["models"]) == 4, "Expected four model slots")
    slots = {row["slot"] for row in proposal_models}
    require(len(slots) == 4 and slots == {row["slot"] for row in manifest["models"]}, "Model slot mismatch")
    require(set(obj(pricing.get("models"), "price models")) == slots, "Price slot mismatch")
    catalogue_rows = array(catalogue.get("models"), "catalogue models")
    by_id = {obj(row, "catalogue row")["catalogue"]["id"]: row for row in catalogue_rows}
    require(len(by_id) == len(catalogue_rows), "Duplicate captured model IDs")
    input_rates, output_rates = [], []
    op = obj(models.get("proposed_operation"), "proposed_operation")
    cap = positive_int(op.get("max_total_generated_tokens_per_attempt"), "Output cap")
    for model in proposal_models:
        obj(model, "proposed model")
        api_id = model["candidate_openrouter_api_id"]
        require(api_id in by_id, f"Uncaptured proposed model: {api_id}")
        captured = by_id[api_id]
        tag = model["preferred_downstream_endpoint_tag"]
        endpoints = [row for row in captured["standard_endpoints"] if row["tag"] == tag]
        require(len(endpoints) == 1, f"Missing or ambiguous captured endpoint: {api_id}/{tag}")
        endpoint = endpoints[0]
        require(endpoint["model_id"] == api_id, f"Endpoint/model mismatch: {api_id}")
        require(model["observed_catalogue_canonical_slug"] == captured["catalogue"]["canonical_slug"],
                f"Canonical identity mismatch: {api_id}")
        for field in ("account_access_verified", "actual_engine_payload_verified", "canonical_slug_callable_snapshot_verified"):
            require(model.get(field) is False, f"Public proposal claims unverified {field}: {api_id}")
        params = obj(model.get("proposed_screamingface_params"), "model parameters")
        require(params.get("max_tokens") == cap, f"Per-model output cap mismatch: {api_id}")
        efforts = captured["catalogue"].get("reasoning", {}).get("supported_efforts")
        if efforts:
            require(params.get("reasoning.effort") in efforts, f"Unsupported captured reasoning effort: {api_id}")
        require(cap <= positive_int(endpoint["max_completion_tokens"], "Endpoint output limit"),
                f"Output cap exceeds captured endpoint limit: {api_id}")
        price = pricing["models"][model["slot"]]
        require(price["api_id"] == api_id and price["endpoint_tag"] == tag, "Price identity mismatch")
        require(price["raw_endpoint_pricing"] == endpoint["pricing"], f"Raw endpoint pricing mismatch: {api_id}")
        for output_key, source_key in (("input_per_million_tokens_usd", "prompt"),
                                        ("output_per_million_tokens_usd", "completion"),
                                        ("cache_read_per_million_tokens_usd", "input_cache_read")):
            require(number(price[output_key], output_key) == number(endpoint["pricing"][source_key], source_key) * 1000000,
                    f"Price conversion mismatch: {api_id}/{output_key}")
        require(price["source_url"] == captured["endpoint_source"], f"Price source mismatch: {api_id}")
        require(price["retrieved_at"] == catalogue["captured_at_utc"], f"Price timestamp mismatch: {api_id}")
        input_rates.append(number(price["input_per_million_tokens_usd"], "input price"))
        output_rates.append(number(price["output_per_million_tokens_usd"], "output price"))
    require(len({row["candidate_openrouter_api_id"] for row in proposal_models}) == 4, "Duplicate proposed model IDs")
    checks.append("four_models_endpoints_and_prices_match_captured_catalogue")

    items = manifest["selection"]["items"]
    require(len({(row["subset"], row["original_id"]) for row in items}) == len(items), "Duplicate selected items")
    dev = [row for row in items if row["split"] == "development"]
    held = [row for row in items if row["split"] == "held_out"]
    smoke = [row for row in dev if row["smoke"]]
    require((len(dev), len(held), len(smoke), len(items)) == (60, 120, 15, 180), "Frozen scope count mismatch")
    scopes = {"smoke": len(smoke), "development_including_reusable_smoke": len(dev),
              "held_out_only_after_lock": len(held), "complete_matrix_including_reusable_smoke": len(items)}
    rows = array(budget.get("rows"), "budget rows")
    require(len(rows) == len(scopes) and {row["scope"] for row in rows} == set(scopes), "Budget scopes mismatch")
    incoming = positive_int(budget.get("input_allowance_tokens_per_call"), "Input allowance")
    attempts = positive_int(budget.get("max_attempts"), "Maximum attempts")
    require(incoming == op["input_budget_guard_tokens_per_call"] and cap == budget["output_cap_tokens_per_call"],
            "Budget/model token allowance mismatch")
    require(attempts == op["max_total_attempts_per_item_model"] == 3, "Retry scenario mismatch")
    require(number(budget["input_price_sum_per_million"], "Input sum") == sum(input_rates), "Input price sum mismatch")
    require(number(budget["output_price_sum_per_million"], "Output sum") == sum(output_rates), "Output price sum mismatch")
    for row in rows:
        n = scopes[row["scope"]]
        require(row["questions_per_model"] == n and row["first_attempt_calls"] == n * 4
                and row["maximum_calls_at_three_attempts"] == n * 4 * attempts, f"Budget call count mismatch: {row['scope']}")
        i = Decimal(n * incoming) * sum(input_rates) / 1000000
        o = Decimal(n * cap) * sum(output_rates) / 1000000
        for field, expected in (("input_at_declared_allowance_usd", i),
                                ("output_if_every_attempt_reaches_cap_usd", o),
                                ("one_attempt_base_token_scenario_usd", i + o),
                                ("three_attempt_base_token_scenario_usd", (i + o) * attempts)):
            require(number(row[field], field) == expected, f"Budget arithmetic mismatch: {row['scope']}/{field}")
    require(scopes["complete_matrix_including_reusable_smoke"] == len(dev) + len(held), "Smoke double-counted")
    require(pricing.get("currency") == budget.get("currency") == "USD", "Currency mismatch")
    checks.append("decimal_budget_arithmetic_and_scope_without_double_counting_smoke")

    require(audit.get("provider_calls") == 0 and audit.get("model_outcomes_collected") is False
            and audit.get("held_out_prompts_rendered") == 0 and audit.get("held_out_outcomes_inspected") is False,
            "Prompt audit has wrong lifecycle scope")
    require(audit.get("billable_token_counts") is None, "Local audit must not claim provider-billed token counts")
    require(audit.get("all_60_prepared_input_hashes_match_committed_reference") is True,
            "Development prepared-input audit did not pass")
    require(audit["selection_sha256"] == freeze["selection_sha256"], "Prompt-audit selection mismatch")
    require(audit["reference_sha256"] == sha(experiment / "backend/official-development.json"),
            "Prompt-audit official reference mismatch")
    require(audit["manifest_sha256"] == sha(manifest_path), "Prompt-audit manifest mismatch")
    reference_ids = {(row["category"], row["original_id"]) for row in reference["records"]}
    require(reference_ids == {(row["subset"], row["original_id"]) for row in dev}, "Official reference is not exact development selection")
    input_hashes = sorted([{"original_id": row["original_id"], "prepared_input_sha256": row["prepared_input_sha256"]}
                           for row in reference["records"]], key=lambda row: row["original_id"])
    require(audit["measured_development_input_hashes_sha256"] == digest(input_hashes), "Audited prepared-input hashes differ")
    budget_audit = obj(budget.get("actual_development_input_audit"), "budget audit")
    require(budget_audit.get("source_sha256") == sha(audit_path), "Budget/audit hash mismatch")
    require(budget_audit.get("provider_billable_input_tokens") is None
            and budget_audit.get("held_out_prompt_measurement") is False, "Budget mislabels local input evidence")
    for scope, count in (("development", len(dev)), ("smoke", len(smoke))):
        summary = audit[scope]["all"]
        require(summary["items"] == count, f"Audit {scope} size mismatch")
        require(budget_audit[f"{scope}_utf8_content_bytes"] == summary["utf8_bytes_total"], "Budget/content-byte mismatch")
        require(sum(audit[scope][subset]["utf8_bytes_total"] for subset in ("LitQA2", "ProtocolQA", "SeqQA"))
                == summary["utf8_bytes_total"], f"Audit {scope} byte aggregation mismatch")
    require(budget_audit["local_gpt_family_token_estimates"] == audit["local_tokenizer_estimate"], "Local token estimate mismatch")
    require(audit["local_tokenizer_estimate"]["provenance"]["provider_request_wrapper_included"] is False,
            "Local content token estimate unexpectedly includes provider wrappers")
    checks.append("development_only_hash_bound_audit_and_nonbillable_local_token_estimates")
    return {"passed": True, "execution_authorized": False, "provider_calls": 0,
            "checks": checks, "proof_limit": "Offline consistency only. Public source captures and local estimates do not prove model access, engine parity, provider billing, funding or authorization."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        result = check(args.repo.resolve())
    except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError, InvalidOperation) as exc:
        result = {"passed": False, "execution_authorized": False, "provider_calls": 0,
                  "error": str(exc)}
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
