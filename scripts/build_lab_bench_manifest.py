"""Build an ID-only review manifest from pinned local LAB-Bench parquet files.

No model calls. Requires pyarrow only for reading source files. Selection never
uses answer correctness, generated responses, or model scores.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

REVISION = "5c77cec648430f30611808808861eb86f81d5eaa"
SALT = "crr-lab-bench-experiment-01-review-v1"
FILES = {
    "LitQA2": "3e578fdaaa4728a77e884954dbf85ae0e3899791631a3be0838313b3e2334114",
    "ProtocolQA": "d48d455638ff49b0c02ae96135703f239ea865a5936233045ee010a5d819239a",
    "SeqQA": "5864776d3d85774f91d82432e30ac31e9222f1670621e8ea141414173c5e9b46",
}
COUNTS = {"LitQA2": 199, "ProtocolQA": 108, "SeqQA": 600}


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode()).hexdigest()


def rank(subset: str, key: str) -> str:
    return digest([SALT, subset, key])


def source_groups(rows: list[dict]) -> dict[str, str]:
    """Connected components of exact available source references, without gold."""
    parent = {r["id"]: r["id"] for r in rows}

    def root(key: str) -> str:
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    owners = {}
    for row in rows:
        for source in row.get("sources") or []:
            key = str(source).strip()
            if not key:
                continue
            if key in owners:
                a, b = root(row["id"]), root(owners[key])
                parent[max(a, b)] = min(a, b)
            else:
                owners[key] = row["id"]
    return {key: digest(["source-component", root(key)]) for key in parent}


def build(data_dir: Path) -> dict:
    import pyarrow.parquet as pq

    items, sources, audit = [], [], {}
    for subset, expected in FILES.items():
        path = data_dir / f"{subset}_train-00000-of-00001.parquet"
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"{subset}: source SHA-256 mismatch")
        rows = pq.read_table(path).to_pylist()
        if len(rows) != COUNTS[subset] or len({r['id'] for r in rows}) != len(rows):
            raise ValueError(f"{subset}: unexpected count or duplicate IDs")
        rows.sort(key=lambda r: rank(subset, r["id"]))
        groups = source_groups(rows)
        if subset == "SeqQA":
            buckets = defaultdict(list)
            for row in rows:
                buckets[row["subtask"]].append(row)
            if len(buckets) != 15 or any(len(v) != 40 for v in buckets.values()):
                raise ValueError("SeqQA subtask structure changed")
            extra_dev = set(sorted(buckets, key=lambda k: rank(subset, k))[:5])
            dev, held = [], []
            for subtask in sorted(buckets):
                selected = buckets[subtask][:4]
                n_dev = 2 if subtask in extra_dev else 1
                dev.extend(selected[:n_dev])
                held.extend(selected[n_dev:])
        else:
            dev = rows[:20]
            dev_groups = {groups[r["id"]] for r in dev}
            held = [r for r in rows if groups[r["id"]] not in dev_groups][:40]
        smoke = {r["id"] for r in sorted(dev, key=lambda r: rank(subset, r["id"]))[:5]}
        full_inputs = []
        for split, selected in (("development", dev), ("held_out", held)):
            for row in selected:
                # Hash the full visible MCQ content. Sorting options avoids mistaking
                # a permutation for a new question. This is not a prompt/target hash.
                content_hash = digest([row.get("protocol"), row["question"],
                                       sorted([row["ideal"], *row["distractors"]])])
                full_inputs.append(content_hash)
                items.append({"subset": subset, "original_id": row["id"],
                              "split": split, "smoke": row["id"] in smoke,
                              "subtask": row["subtask"],
                              "source_group": groups[row["id"]],
                              "full_input_sha256": content_hash})
        if len(set(full_inputs)) != 60:
            raise ValueError(f"{subset}: selected full-input duplicates")
        audit[subset] = {"available_items": len(rows), "selected_items": 60,
                         "development": len(dev), "held_out": len(held),
                         "smoke": len(smoke), "selected_full_input_duplicates": 0,
                         "selected_source_groups_crossing_split": 0}
        sources.append({"subset": subset, "sha256": actual,
                        "url": f"https://huggingface.co/datasets/futurehouse/lab-bench/resolve/{REVISION}/{subset}/train-00000-of-00001.parquet"})
    items.sort(key=lambda r: (r["subset"], r["split"], r["original_id"]))
    return {
        "schema_version": 1, "status": "draft", "date": "2026-10-25",
        "dataset": {"name": "futurehouse/lab-bench", "revision": REVISION,
                    "license": "CC-BY-SA-4.0", "files": sources},
        "selection": {"salt": SALT, "algorithm": "source-separated-hash-and-seqqa-stratified-v1",
                      "items_sha256": digest(items), "audit": audit, "items": items},
        "upstream_task": {"inspect_ai": "0.3.263", "inspect_evals": "0.20.0",
                          "dataset_shuffle_seed": 7, "choice_shuffle_seed": 7},
        "models": [{"slot": f"model_{i}", "api_id": None, "version": None,
                    "provider_route": None, "settings": None} for i in range(1, 5)],
        "backend": {"source_revision": "3f2b3a6efacf9b9b4604de49f49b69130b36a847",
                    "execution_location": None, "variant_revision": None,
                    "hosted_access_confirmed": False, "local_engine_verified": False,
                    "id_mapping_verified": False, "scorer_equivalence_verified": False},
        "method": {"feature_definition": None, "profile_estimator": None,
                   "threshold_rule": None, "analysis_plan_revision": None,
                   "calibration_item_ids": sorted(r["original_id"] for r in items if r["split"] == "development"),
                   "held_out_outcomes_seen": False},
        "billing": {"approved_limit_usd": None, "pricing_sha256": None},
        "review": {"protocol_approved": False, "method_approved": False,
                   "freeze_record": None},
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    manifest = build(a.data_dir)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"items": len(manifest["selection"]["items"]),
                      "items_sha256": manifest["selection"]["items_sha256"],
                      "status": manifest["status"]}, indent=2))


if __name__ == "__main__":
    main()
