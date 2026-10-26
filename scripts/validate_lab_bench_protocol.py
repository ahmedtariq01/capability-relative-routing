"""Offline structural checks. Does not run models or certify external evidence."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def proposal_metadata() -> dict:
    folder = ROOT / "docs/experiment-01"
    plan = json.loads((folder / "method-plan.json").read_text())
    return {"feature_definition": "within_category_visible_structure_v1",
            "profile_estimator": plan["method_version"],
            "threshold_rule": plan["selection"],
            "analysis_plan_revision": plan["analysis_version"],
            "plan_sha256": digest(plan),
            "documents_sha256": {name: hashlib.sha256((folder / name).read_bytes()).hexdigest()
                                 for name in ("METHOD.md", "ANALYSIS.md")}}


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode()).hexdigest()


def check_manifest(m: dict, require_frozen: bool = False) -> list[str]:
    errors = []
    items = m["selection"]["items"]
    ids = [r["original_id"] for r in items]
    if len(ids) != len(set(ids)):
        errors.append("duplicate original IDs")
    if len(items) != 180:
        errors.append("expected 180 assigned items")
    if m["selection"]["items_sha256"] != digest(items):
        errors.append("selection digest mismatch")
    counts = Counter((r["subset"], r["split"]) for r in items)
    expected = {(s, split): n for s in ("LitQA2", "ProtocolQA", "SeqQA")
                for split, n in (("development", 20), ("held_out", 40))}
    if dict(counts) != expected:
        errors.append("expected 20 development and 40 held-out items per subset")
    for subset in ("LitQA2", "ProtocolQA", "SeqQA"):
        if sum(r["smoke"] is True for r in items if r["subset"] == subset) != 5:
            errors.append(f"{subset}: expected 5 smoke items")
    groups = defaultdict(set)
    contents = []
    for r in items:
        if type(r["smoke"]) is not bool:
            errors.append("smoke must be boolean")
        if r["smoke"] and r["split"] != "development":
            errors.append("smoke item is outside development")
        groups[r["source_group"]].add(r["split"])
        contents.append(r["full_input_sha256"])
    if any(len(sides) > 1 for sides in groups.values()):
        errors.append("source group crosses the split")
    if len(contents) != len(set(contents)):
        errors.append("duplicate full-input content")
    dev = {r["original_id"] for r in items if r["split"] == "development"}
    fit_ids = m["method"]["calibration_item_ids"]
    if not fit_ids or len(fit_ids) != len(set(fit_ids)) or not set(fit_ids) <= dev:
        errors.append("calibration IDs must be unique development IDs")
    if m["method"]["held_out_outcomes_seen"] is not False:
        errors.append("held-out outcomes already seen or status unknown")
    for key, expected_value in proposal_metadata().items():
        if m["method"].get(key) != expected_value:
            errors.append(f"method.{key} differs from the reviewed proposal files")
    seq = [r for r in items if r["subset"] == "SeqQA"]
    if len({r["subtask"] for r in seq}) != 15 or set(Counter(r["subtask"] for r in seq).values()) != {4}:
        errors.append("expected four SeqQA items from each of 15 subtasks")
    if len({r["subtask"] for r in seq if r["split"] == "development"}) != 15:
        errors.append("development does not cover all SeqQA subtasks")
    if m["status"] not in ("draft", "frozen"):
        errors.append("unknown manifest status")
    if require_frozen or m["status"] == "frozen":
        if m["status"] != "frozen":
            errors.append("manifest remains a draft")
        for key in ("protocol_approved", "method_approved"):
            if m["review"][key] is not True:
                errors.append(f"review.{key} unresolved")
        if not m["review"]["freeze_record"]:
            errors.append("freeze record missing")
        models = m["models"]
        if len(models) != 4 or len({v["slot"] for v in models}) != 4:
            errors.append("expected four distinct model slots")
        for model in models:
            for key in ("api_id", "version", "provider_route", "settings"):
                if not model.get(key):
                    errors.append(f"{model['slot']}.{key} unresolved")
        backend = m["backend"]
        loc = backend["execution_location"]
        if loc not in ("local", "hosted"):
            errors.append("execution location unresolved")
        if loc == "local" and backend["local_engine_verified"] is not True:
            errors.append("local engine unverified")
        if loc == "hosted" and backend["hosted_access_confirmed"] is not True:
            errors.append("hosted access unverified")
        if not backend["variant_revision"]:
            errors.append("backend.variant_revision unresolved")
        for key in ("id_mapping_verified", "scorer_equivalence_verified"):
            if backend[key] is not True:
                errors.append(f"backend.{key} unresolved")
        for key in ("feature_definition", "profile_estimator", "threshold_rule", "analysis_plan_revision"):
            if not m["method"][key]:
                errors.append(f"method.{key} unresolved")
        for key in ("fit_artifact_sha256", "overhead_measurement_sha256"):
            if not re.fullmatch(r"[a-f0-9]{64}", m["method"].get(key) or ""):
                errors.append(f"method.{key} unresolved")
        if not re.fullmatch(r"[a-f0-9]{40}", m["method"].get("implementation_revision") or ""):
            errors.append("method.implementation_revision unresolved")
        cpu_rate = m["method"].get("router_cpu_usd_per_second")
        if type(cpu_rate) not in (float, int) or not math.isfinite(cpu_rate) or cpu_rate <= 0:
            errors.append("positive router CPU price missing for the full-cost comparison")
        limit = m["billing"]["approved_limit_usd"]
        if type(limit) not in (int, float) or not math.isfinite(limit) or limit <= 0:
            errors.append("approved positive spend limit missing")
        if not re.fullmatch(r"[a-f0-9]{64}", m["billing"]["pricing_sha256"] or ""):
            errors.append("pricing snapshot hash missing")
    return sorted(set(errors))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("manifest", type=Path)
    p.add_argument("--require-frozen", action="store_true")
    a = p.parse_args()
    try:
        m = json.loads(a.manifest.read_text())
        errors = check_manifest(m, a.require_frozen)
    except (KeyError, TypeError, ValueError) as e:
        errors = [f"malformed manifest: {e}"]
    print(json.dumps({"check": "freeze_prerequisites" if a.require_frozen else "draft_integrity",
                      "passed": not errors, "errors": errors,
                      "scope": "offline structural check only; no engine run or external approval verified"}, indent=2))
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
