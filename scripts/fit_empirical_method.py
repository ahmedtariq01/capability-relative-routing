"""Fit only a complete development bundle. No providers, networking or holdout reads."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from crr.empirical import Question, Observation, digest, fit_development
from validate_lab_bench_protocol import check_manifest


def fit_bundle(manifest: dict, bundle: dict) -> dict:
    errors = check_manifest(manifest)
    if errors:
        raise ValueError(f"manifest integrity failure: {errors}")
    required = {"questions", "observations", "cost_basis", "pricing_sha256", "preparation_record_sha256", "data_kind"}
    if set(bundle) != required or bundle["data_kind"] not in {"synthetic", "measured_development"}:
        raise ValueError("unexpected development bundle fields or data kind")
    if bundle["cost_basis"] != "frozen_price_all_attempts":
        raise ValueError("cost basis must include all attempts under the frozen price table")
    for key in ("pricing_sha256", "preparation_record_sha256"):
        if not isinstance(bundle[key], str) or not re.fullmatch(r"[a-f0-9]{64}", bundle[key]):
            raise ValueError(f"invalid {key}")
    if bundle["pricing_sha256"] != manifest["billing"]["pricing_sha256"]:
        raise ValueError("pricing snapshot differs from manifest")
    questions = tuple(Question.from_dict(q) for q in bundle["questions"])
    observations = tuple(Observation(**row) for row in bundle["observations"])
    fitted = fit_development(manifest, questions, observations)
    fitted["provenance"] = {k: bundle[k] for k in required - {"questions", "observations"}}
    fitted["manifest_sha256"] = digest(manifest)
    fitted["python_version"] = platform.python_version()
    fitted["method_plan_sha256"] = manifest["method"]["plan_sha256"]
    fitted["source_sha256"] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in (ROOT / "src/crr/empirical.py", ROOT / "src/crr/analysis.py", ROOT / "src/crr/oracle.py")}
    return fitted


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--development-bundle", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output exists; use a new version rather than overwrite a fit")
    artifact = fit_bundle(json.loads(args.manifest.read_text()), json.loads(args.development_bundle.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": artifact["status"], "training_items": len(artifact["training_ids"]),
                      "fit_sha256": digest(artifact), "provider_calls": 0}))


if __name__ == "__main__":
    main()
