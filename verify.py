import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from crr import ModelProfile, Problem, RouterCost, route

ROOT = Path(__file__).resolve().parent
config = json.loads((ROOT / "configs/synthetic_models.json").read_text())
models = tuple(
    ModelProfile(
        name=row["name"],
        capabilities=row["capabilities"],
        inference_cost_dollars=row["cost_dollars"],
        inference_latency_ms=row["latency_ms"],
    )
    for row in config["models"]
)
overhead = RouterCost(**config["routing_overhead"])
problems = (
    Problem("retrieval-1", {"retrieval": 1.0}, 0.80),
    Problem("reasoning-1", {"reasoning": 1.0}, 0.80),
)
for problem in problems:
    decision = route(problem, models, overhead)
    print(json.dumps({"fixture_status": config["fixture_status"], **decision.__dict__, "routing_cost": decision.routing_cost.__dict__}, sort_keys=True))
