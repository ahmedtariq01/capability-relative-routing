"""Check pinned upstream task preparation and scoring with an offline mock model.

This does not start ScreamingFace or call a provider. Source parquet files must
already be local and hash-verified by build_lab_bench_manifest.py.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import inspect
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from crr.backend_equivalence import selected_items

from build_lab_bench_manifest import FILES, digest


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir", required=True, type=Path)
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--export-split", choices=("development", "smoke"), default="development",
                   help="Only development input/target hashes enter the backend reference export")
    a = p.parse_args()
    expected = {"inspect_ai": "0.3.263", "inspect_evals": "0.20.0", "datasets": "5.0.1"}
    versions = {k: importlib.metadata.version(k) for k in expected}
    if versions != expected:
        raise ValueError(f"Task preparation dependency mismatch: {versions}")

    import hashlib
    from datasets import Dataset
    from inspect_ai import eval as inspect_eval
    from inspect_ai.dataset import MemoryDataset, Sample
    from inspect_ai.model import ModelOutput, get_model
    from inspect_evals.lab_bench.lab_bench import MULTIPLE_CHOICE_TEMPLATE, task_base
    from inspect_evals.lab_bench import lab_bench, record_to_sample_helpers, scorer
    from inspect_ai.solver import multiple_choice
    from inspect_ai.solver._multiple_choice import prompt
    from inspect_ai.solver._task_state import Choices
    from inspect_evals.lab_bench.record_to_sample_helpers import (
        UNCERTAIN_ANSWER_CHOICE, record_to_sample_base, record_to_sample_protocolqa,
    )

    m = json.loads(a.manifest.read_text())
    export_ids = {r["original_id"] for r in selected_items(m, a.export_split)}
    preparation = dict(m["upstream_task"])
    file_hash = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
    preparation.update({
        "task_source_sha256": digest({"task": file_hash(lab_bench.__file__),
                                      "mapper": file_hash(record_to_sample_helpers.__file__)}),
        "solver_source_sha256": file_hash(inspect.getsourcefile(inspect.unwrap(multiple_choice))),
        "scorer_source_sha256": file_hash(scorer.__file__),
        "template_sha256": hashlib.sha256(MULTIPLE_CHOICE_TEMPLATE.encode()).hexdigest(),
    })
    repository = Path(__file__).resolve().parents[1]
    exporter_revision = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                               cwd=repository, text=True).strip()
    exporter_dirty = bool(subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=normal"],
        cwd=repository, text=True).strip())
    backend_export = {
        "schema_version": 1, "role": "official", "evidence_kind": "upstream_task_mock",
        "provider_calls": 0, "real_outcomes_collected": False,
        "split": a.export_split, "dataset_revision": m["dataset"]["revision"],
        "selection_sha256": m["selection"]["items_sha256"],
        "exporter_revision": exporter_revision,
        "exporter_worktree_dirty": exporter_dirty,
        "exporter_revision_kind": ("checkout_base_with_uncommitted_changes" if exporter_dirty
                                   else "clean_checkout_commit"),
        "exporter_source_sha256": file_hash(__file__),
        "source_case_id_namespace": "lab-bench-original-id",
        "preparation": preparation, "preparation_sha256": digest(preparation),
        "selected_denominator": len(export_ids), "records": [],
    }
    report = {"versions": versions, "model": "mockllm/model",
              "provider_calls": 0, "scope": "upstream task only; no engine equivalence claim",
              "template_sha256": hashlib.sha256(MULTIPLE_CHOICE_TEMPLATE.encode()).hexdigest(),
              "subsets": {}, "selected_samples": []}
    for subset, expected_hash in FILES.items():
        path = a.data_dir / f"{subset}_train-00000-of-00001.parquet"
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
            raise ValueError(f"Source hash changed: {subset}")
        # Same dataset shuffle then official mapping then choice-shuffle order as
        # inspect_ai.dataset.hf_dataset at the pinned versions. Local input only.
        records = Dataset.from_parquet(str(path)).shuffle(seed=7).to_list()
        mapper = record_to_sample_protocolqa if subset == "ProtocolQA" else record_to_sample_base
        prepared = MemoryDataset([mapper(row) for row in records], shuffled=True)
        prepared.shuffle_choices(seed=7)
        wanted = {r["original_id"] for r in m["selection"]["items"] if r["subset"] == subset}
        selected = [sample for sample in prepared if sample.id in wanted]
        if len(selected) != 60 or {s.id for s in selected} != wanted:
            raise ValueError(f"Selection mismatch: {subset}")
        # Demonstrate the concrete permutation risk from filtering first.
        premature = MemoryDataset([mapper(row) for row in records if row["id"] in wanted])
        premature.shuffle_choices(seed=7)
        premature_map = {s.id: s for s in premature}
        changed = sum(s.choices != premature_map[s.id].choices for s in selected)
        if changed == 0:
            raise ValueError("Expected the filter-order check to detect a changed permutation")
        for sample in selected:
            if sample.id in export_ids:
                backend_export["records"].append({
                    "original_id": str(sample.id), "category": subset,
                    "source_case_id": str(sample.id), "variant_case_id": str(sample.id),
                    "prepared_input_sha256": digest([{
                        "role": "user", "content": prompt(sample.input, Choices(sample.choices), MULTIPLE_CHOICE_TEMPLATE)}]),
                    "ordered_choices_sha256": digest(sample.choices),
                    "target_mapping_sha256": digest({"target": sample.target,
                        "ordered_choices_sha256": digest(sample.choices)}),
                })
            report["selected_samples"].append({"subset": subset, "original_id": sample.id,
                "input_sha256": digest(sample.input), "ordered_choices_sha256": digest(sample.choices),
                "prepared_sample_sha256": digest([sample.id, sample.input, sample.choices])})
        if subset == "ProtocolQA":
            by_id = {r["id"]: r for r in records}
            assert all(s.input == "Protocol: " + by_id[s.id]["protocol"] + "\n\n" + by_id[s.id]["question"] for s in selected)
        report["subsets"][subset] = {"prepared": len(prepared), "selected": len(selected),
                                    "filter_before_shuffle_changed_choice_order": changed}

    cases = {"correct": ("ANSWER: A", "C"), "incorrect": ("ANSWER: B", "I"),
             "abstain": ("ANSWER: C", "N"), "malformed": ("No option selected.", "I")}
    fixtures = MemoryDataset([Sample(id=name, input=f"OFFLINE_FIXTURE_{name}: Which option is a colour?",
                    choices=["blue", "stone", UNCERTAIN_ANSWER_CHOICE], target="A") for name in cases])

    def output(messages, tools, tool_choice, config):
        content = str(messages)
        name = next(name for name in cases if f"OFFLINE_FIXTURE_{name}:" in content)
        return ModelOutput.from_content(model="mockllm/model", content=cases[name][0])

    a.output_dir.mkdir(parents=True, exist_ok=True)
    model = get_model("mockllm/model", custom_outputs=output)
    logs = inspect_eval(task_base(fixtures), model=model, log_dir=str(a.output_dir / "mock-logs"),
                        display="none", max_connections=1)
    if len(logs) != 1 or logs[0].status != "success":
        raise ValueError("Upstream mock evaluation did not complete")
    observed = {}
    for sample in logs[0].samples or []:
        observed[str(sample.id)] = next(iter(sample.scores.values())).value
    assert observed == {name: pair[1] for name, pair in cases.items()}, observed
    backend_export["scorer_probes"] = {
        str(sample.id): {
            "input_sha256": digest({"input": sample.input, "choices": sample.choices, "target": sample.target}),
            "response_sha256": digest(cases[str(sample.id)][0]),
            "score": observed[str(sample.id)],
        } for sample in fixtures
    }
    backend_export["probe_aggregate"] = {"n_samples": len(observed), "n_scored": len(observed),
        "score_counts": {score: list(observed.values()).count(score) for score in ("C", "I", "N")}}
    backend_export["records"].sort(key=lambda row: (row["category"], row["original_id"]))
    (a.output_dir / f"official_{a.export_split}_export.json").write_text(json.dumps(backend_export, indent=2) + "\n")
    report["backend_reference_export"] = f"official_{a.export_split}_export.json"
    report["mock_scores"] = observed
    report["selected_samples"].sort(key=lambda x: (x["subset"], x["original_id"]))
    (a.output_dir / "upstream_task_checks.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "selected_samples"}, indent=2))


if __name__ == "__main__":
    main()
