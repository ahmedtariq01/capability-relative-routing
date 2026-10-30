"""Measure frozen development prompt content without provider calls or answer output.

This repeats the pinned full-source dataset/choice preparation before selecting
development IDs, because filtering first changes choice order. Only development
prompts are rendered or measured. Gold target text, prompt text and held-out
prompt statistics are never written. Sizes exclude provider request wrappers.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import inspect
import json
import math
import os
from pathlib import Path
import re
import statistics

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["HF_DATASETS_DISABLE_PROGRESS_BARS"] = "1"


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def file_hash(path: Path | str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sizes(rows: list[dict]) -> dict:
    chars = sorted(row["characters"] for row in rows)
    return {
        "items": len(rows),
        "characters_total": sum(chars),
        "characters_min": min(chars),
        "characters_median": statistics.median(chars),
        "characters_p95_nearest_rank": chars[math.ceil(0.95 * len(chars)) - 1],
        "characters_max": max(chars),
        "utf8_bytes_total": sum(row["utf8_bytes"] for row in rows),
        "utf8_bytes_max": max(row["utf8_bytes"] for row in rows),
    }


def token_sizes(rows: list[dict]) -> dict:
    values = sorted(row["local_tokens"] for row in rows)
    return {"items": len(rows), "local_tokens_total": sum(values),
            "local_tokens_min": min(values), "local_tokens_median": statistics.median(values),
            "local_tokens_p95_nearest_rank": values[math.ceil(0.95 * len(values)) - 1],
            "local_tokens_max": max(values)}


def local_tokenizer(model: str) -> tuple:
    """Resolve installed tiktoken, permitting its public OpenAI BPE download only.

    A broad family-prefix resolution is recorded as such; it does not verify the
    named model exists or that a provider uses identical request tokenization.
    """
    import tiktoken
    import tiktoken.model
    from tiktoken.load import read_file_cached
    import tiktoken_ext.openai_public as public

    exact = tiktoken.model.MODEL_TO_ENCODING.get(model)
    prefix_matches = [(prefix, name) for prefix, name in tiktoken.model.MODEL_PREFIX_TO_ENCODING.items()
                      if model.startswith(prefix)]
    if exact:
        encoding_name = exact
        mapping = {"kind": "exact_model_mapping", "key": model}
    elif prefix_matches:
        prefix, encoding_name = prefix_matches[0]
        mapping = {"kind": "model_family_prefix_mapping", "key": prefix}
    else:
        encoding_name = "o200k_base"
        mapping = {"kind": "explicit_surrogate", "key": "o200k_base"}
    if encoding_name != "o200k_base":
        raise ValueError("This audited downloader supports only the official o200k_base resource")
    constructor_source = inspect.getsource(public.o200k_base)
    source_url = "https://openaipublic.blob.core.windows.net/encodings/o200k_base.tiktoken"
    if source_url not in constructor_source:
        raise ValueError("Installed constructor no longer uses the audited OpenAI resource")
    match = re.search(r'expected_hash="([0-9a-f]{64})"', constructor_source)
    if not match:
        raise ValueError("Installed constructor must pin the public BPE SHA-256")
    expected_hash = match.group(1)
    # tiktoken's own reader verifies the pinned SHA and uses its ordinary cache.
    # This public resource fetch uses no API key or provider generation endpoint.
    bpe_bytes = read_file_cached(source_url, expected_hash=expected_hash)
    encoding = (tiktoken.get_encoding(encoding_name) if mapping["kind"] == "explicit_surrogate"
                else tiktoken.encoding_for_model(model))
    if encoding.name != encoding_name:
        raise ValueError("Tokenizer resolution changed during audit")
    provenance = {
        "package": "tiktoken", "package_version": importlib.metadata.version("tiktoken"),
        "requested_model": model, "encoding": encoding.name, "mapping": mapping,
        "method": "encode_ordinary on official rendered user-message content",
        "source_url": source_url, "source_sha256": hashlib.sha256(bpe_bytes).hexdigest(),
        "source_expected_sha256": expected_hash,
        "encoding_constructor_sha256": hashlib.sha256(constructor_source.encode()).hexdigest(),
        "model_mapping_source_sha256": file_hash(tiktoken.model.__file__),
        "encoding_pattern_sha256": hashlib.sha256(encoding._pat_str.encode()).hexdigest(),
        "encoding_special_tokens_sha256": digest(encoding._special_tokens),
        "api_credentials_used": False, "token_count_api_calls": 0, "model_calls": 0,
        "provider_request_wrapper_included": False,
        "proof_limit": "Local family-prefix/surrogate content tokenization is not a provider-billed count or a verification of the named model's availability. Provider headers, message wrappers and output/reasoning usage are excluded.",
    }
    return encoding, provenance


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--local-tokenizer-model", default=None,
                        help="Optional local tiktoken estimate; may download its pinned public OpenAI BPE resource")
    args = parser.parse_args()
    expected_versions = {"inspect_ai": "0.3.263", "inspect_evals": "0.20.0", "datasets": "5.0.1"}
    versions = {name: importlib.metadata.version(name) for name in expected_versions}
    if versions != expected_versions:
        raise ValueError(f"Dependency mismatch: {versions}")
    encoding, tokenizer_provenance = (local_tokenizer(args.local_tokenizer_model)
                                      if args.local_tokenizer_model else (None, None))

    import pyarrow.parquet as pq
    from datasets import Dataset
    from inspect_ai.dataset import MemoryDataset
    from inspect_ai.solver import multiple_choice
    from inspect_ai.solver._multiple_choice import prompt
    from inspect_ai.solver._task_state import Choices
    from inspect_evals.lab_bench import lab_bench, record_to_sample_helpers, scorer
    from inspect_evals.lab_bench.lab_bench import MULTIPLE_CHOICE_TEMPLATE
    from inspect_evals.lab_bench.record_to_sample_helpers import (
        record_to_sample_base, record_to_sample_protocolqa,
    )

    manifest_path = args.repo / "docs/experiment-01/manifest.draft.json"
    reference_path = args.repo / "docs/experiment-01/backend/official-development.json"
    manifest = json.loads(manifest_path.read_text())
    reference = json.loads(reference_path.read_text())
    if reference["split"] != "development" or reference["provider_calls"] != 0:
        raise ValueError("Reference must be development-only with no provider calls")
    if reference["dataset_revision"] != manifest["dataset"]["revision"]:
        raise ValueError("Dataset revision mismatch")
    if reference["selection_sha256"] != manifest["selection"]["items_sha256"]:
        raise ValueError("Frozen selection mismatch")
    preparation = dict(manifest["upstream_task"])
    preparation.update({
        "task_source_sha256": digest({"task": file_hash(lab_bench.__file__),
                                      "mapper": file_hash(record_to_sample_helpers.__file__)}),
        "solver_source_sha256": file_hash(inspect.getsourcefile(inspect.unwrap(multiple_choice))),
        "scorer_source_sha256": file_hash(scorer.__file__),
        "template_sha256": hashlib.sha256(MULTIPLE_CHOICE_TEMPLATE.encode()).hexdigest(),
    })
    if preparation != reference["preparation"] or digest(preparation) != reference["preparation_sha256"]:
        raise ValueError("Official preparation sources changed")
    ref_by_id = {row["original_id"]: row for row in reference["records"]}
    selected = [row for row in manifest["selection"]["items"] if row["split"] == "development"]
    if len(selected) != 60 or set(ref_by_id) != {row["original_id"] for row in selected}:
        raise ValueError("Expected precisely the frozen 60 development IDs")

    entries = []
    source_files = []
    for source in manifest["dataset"]["files"]:
        subset = source["subset"]
        path = args.data_dir / f"{subset}_train-00000-of-00001.parquet"
        if file_hash(path) != source["sha256"]:
            raise ValueError(f"Source hash mismatch: {subset}")
        # In-memory source preparation uses the same Arrow/Dataset shuffle route
        # as the reference exporter; no dataset downloads or cache writes.
        rows = Dataset.from_list(pq.read_table(path).to_pylist()).shuffle(
            seed=preparation["dataset_shuffle_seed"], keep_in_memory=True).to_list()
        mapper = record_to_sample_protocolqa if subset == "ProtocolQA" else record_to_sample_base
        prepared = MemoryDataset([mapper(row) for row in rows], shuffled=True)
        prepared.shuffle_choices(seed=preparation["choice_shuffle_seed"])
        wanted = {row["original_id"]: row for row in selected if row["subset"] == subset}
        source_files.append({"subset": subset, "path": str(path.resolve()),
                             "sha256": source["sha256"], "source_rows_prepared": len(rows)})
        for sample in prepared:
            if sample.id not in wanted:
                continue
            rendered = prompt(sample.input, Choices(sample.choices), MULTIPLE_CHOICE_TEMPLATE)
            prompt_hash = digest([{"role": "user", "content": rendered}])
            if prompt_hash != ref_by_id[sample.id]["prepared_input_sha256"]:
                raise ValueError(f"Prepared development prompt hash mismatch: {sample.id}")
            entry = {"category": subset, "original_id": sample.id,
                     "smoke": wanted[sample.id]["smoke"],
                     "prepared_input_sha256": prompt_hash,
                     "characters": len(rendered), "utf8_bytes": len(rendered.encode("utf-8"))}
            if encoding is not None:
                entry["local_tokens"] = len(encoding.encode_ordinary(rendered))
            entries.append(entry)
    if len(entries) != 60 or sum(row["smoke"] for row in entries) != 15:
        raise ValueError("Development/smoke selection count mismatch")

    report = {
        "schema_version": 1,
        "evidence_kind": "offline_development_prompt_content_size_audit",
        "provider_calls": 0,
        "model_outcomes_collected": False,
        "held_out_prompts_rendered": 0,
        "held_out_outcomes_inspected": False,
        "versions": versions,
        "source_files": source_files,
        "preparation": preparation,
        "preparation_sha256": digest(preparation),
        "script_sha256": file_hash(__file__),
        "manifest_sha256": file_hash(manifest_path),
        "reference_sha256": file_hash(reference_path),
        "selection_sha256": manifest["selection"]["items_sha256"],
        "all_60_prepared_input_hashes_match_committed_reference": True,
        "measured_development_input_hashes_sha256": digest(sorted(
            [{"original_id": row["original_id"], "prepared_input_sha256": row["prepared_input_sha256"]}
             for row in entries], key=lambda row: row["original_id"])),
        "billable_token_counts": None,
        "billable_token_counts_status": "not_measured_provider_specific_tokenizer_and_request_wrapper_unresolved",
        "provider_request_wrapper_included": False,
        "proof_limit": "Characters and UTF-8 bytes measure official user-message content only. They are not billable tokens, output/reasoning usage, an exact provider request size or a dollar estimate. Whole source tasks are prepared for upstream choice-order parity, but only frozen development prompts are rendered and measured; no prompt or answer text is exported.",
        "development": {},
        "smoke": {},
    }
    for subset in ("LitQA2", "ProtocolQA", "SeqQA"):
        report["development"][subset] = sizes([row for row in entries if row["category"] == subset])
        report["smoke"][subset] = sizes([row for row in entries if row["category"] == subset and row["smoke"]])
    report["development"]["all"] = sizes(entries)
    report["smoke"]["all"] = sizes([row for row in entries if row["smoke"]])
    if encoding is not None:
        report["local_tokenizer_estimate"] = {"provenance": tokenizer_provenance,
                                              "development": {}, "smoke": {}}
        for subset in ("LitQA2", "ProtocolQA", "SeqQA"):
            report["local_tokenizer_estimate"]["development"][subset] = token_sizes(
                [row for row in entries if row["category"] == subset])
            report["local_tokenizer_estimate"]["smoke"][subset] = token_sizes(
                [row for row in entries if row["category"] == subset and row["smoke"]])
        report["local_tokenizer_estimate"]["development"]["all"] = token_sizes(entries)
        report["local_tokenizer_estimate"]["smoke"]["all"] = token_sizes(
            [row for row in entries if row["smoke"]])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"output": str(args.output.resolve()), "development": report["development"]["all"],
                      "smoke": report["smoke"]["all"], "reference_hashes_match": True}, indent=2))


if __name__ == "__main__":
    main()
