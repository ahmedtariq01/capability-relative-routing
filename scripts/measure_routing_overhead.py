"""Time local category/CRR routing. No model calls, networking or held-out inputs."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from crr.empirical import Question, fit_development
from crr.overhead import measure_overhead


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--synthetic", action="store_true", help="use invented development fixtures")
    p.add_argument("--fit", type=Path)
    p.add_argument("--inputs", type=Path, help="JSON with data_kind and development questions only")
    p.add_argument("--target", type=float, default=.8)
    p.add_argument("--warmup", type=int, default=5)
    p.add_argument("--repetitions", type=int, default=25)
    p.add_argument("--cpu-usd-per-second", type=float)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        p.error("output exists; preserve measurements and use a new output path")
    if a.synthetic:
        if a.fit or a.inputs:
            p.error("--synthetic cannot be combined with --fit or --inputs")
        sys.path.insert(0, str(ROOT / "tests"))
        from empirical_fixtures import fixture
        manifest, questions, observations = fixture()
        artifact = fit_development(manifest, questions, observations)
        artifact["provenance"] = {"data_kind": "synthetic"}
        kind = "synthetic"
    else:
        if not a.fit or not a.inputs:
            p.error("provide --synthetic, or both --fit and --inputs")
        artifact = json.loads(a.fit.read_text())
        inputs = json.loads(a.inputs.read_text())
        if set(inputs) != {"data_kind", "questions"}:
            p.error("inputs must contain only data_kind and questions, never outcomes")
        kind = inputs["data_kind"]
        questions = tuple(Question.from_dict(q) for q in inputs["questions"])
    record = measure_overhead(artifact, questions, input_data_kind=kind, target=a.target,
                              warmup=a.warmup, repetitions=a.repetitions,
                              cpu_usd_per_second=a.cpu_usd_per_second)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open("x") as output:
        output.write(json.dumps(record, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: record[k] for k in ("data_kind", "target", "target_role", "cost_status",
                       "execution_gate_satisfied", "provider_calls", "held_out_outcomes_loaded")}, indent=2))


if __name__ == "__main__":
    main()
