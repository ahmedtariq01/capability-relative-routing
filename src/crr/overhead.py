"""Measure local routing work without provider calls or outcome loading.

The final dispatch boundary depends on the backend adapter. This module times
only construction of a local dispatch envelope, never substitutes it for an
actual backend measurement, and cannot approve execution.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
from statistics import mean, median
import time

from .empirical import Question, TARGETS, choose, digest, restore_profiles, routing_predictions


def dispatch_envelope(question: Question, selected: dict) -> bytes:
    """Local serialization only. This is not a provider adapter or network call."""
    return json.dumps({"model_slot": selected["model"], "item_id": question.item_id,
                       "category": question.subset, "input_text": question.input_text,
                       "choices": question.choices}, ensure_ascii=False,
                      separators=(",", ":")).encode()


def _timed(call):
    wall, cpu = time.perf_counter_ns(), time.process_time_ns()
    result = call()
    return result, {"elapsed_ns": time.perf_counter_ns() - wall,
                    "cpu_ns": time.process_time_ns() - cpu}


def _summary(samples: list[dict], rate: float | None) -> dict:
    result = {"samples": len(samples)}
    for name in ("elapsed_ns", "cpu_ns"):
        values = sorted(s[name] for s in samples)
        result[name] = {"mean": mean(values), "median": median(values),
                        "p95": values[max(0, math.ceil(.95 * len(values)) - 1)]}
    result["mean_local_cpu_cost_usd"] = None if rate is None else result["cpu_ns"]["mean"] / 1e9 * rate
    return result


def measure_overhead(artifact: dict, questions: tuple[Question, ...], *,
                     input_data_kind: str, target: float = .8, warmup: int = 5,
                     repetitions: int = 25, cpu_usd_per_second: float | None = None) -> dict:
    if input_data_kind not in {"synthetic", "measured_development"}:
        raise ValueError("only synthetic or measured_development input is allowed")
    fit_kind = artifact.get("provenance", {}).get("data_kind")
    if fit_kind != input_data_kind:
        raise ValueError("fit and input data kinds must be explicit and equal")
    if target not in TARGETS:
        raise ValueError("target is outside the declared grid")
    if type(warmup) is not int or warmup < 1 or type(repetitions) is not int or repetitions < 2:
        raise ValueError("use at least one warm-up and two measurement repetitions")
    if cpu_usd_per_second is not None and (type(cpu_usd_per_second) not in (int, float)
            or not math.isfinite(cpu_usd_per_second) or cpu_usd_per_second <= 0):
        raise ValueError("primary CPU rate must be a positive finite number, or omitted")
    ids = [q.item_id for q in questions]
    if not ids or len(ids) != len(set(ids)) or not set(ids) <= set(artifact["training_ids"]):
        raise ValueError("measurement inputs must be unique fitted development IDs")
    questions = tuple(sorted(questions, key=lambda q: q.item_id))
    input_hash = digest([asdict(q) for q in questions])
    if input_data_kind == "measured_development":
        if set(ids) != set(artifact["training_ids"]):
            raise ValueError("real overhead measurement requires the complete fitted development inputs")
        if input_hash != artifact.get("training_inputs_sha256"):
            raise ValueError("development input bytes differ from the fitted training inputs")
    profiles = restore_profiles(artifact)
    families, raw = {}, []
    for family in ("category", "crr"):
        policy = next(p for p in artifact["selections"][family] if p["target"] == target)
        if policy["selected"] is None:
            families[family] = {"status": "unattainable_on_development", "measurements": None}
            continue
        threshold = policy["selected"]["threshold"]
        for _ in range(warmup):
            for q in questions:
                dispatch_envelope(q, choose(routing_predictions(profiles, q, family), family, threshold))
        for repeat in range(repetitions):
            for q in questions:
                predictions, prediction = _timed(lambda: routing_predictions(profiles, q, family))
                selected, selection = _timed(lambda: choose(predictions, family, threshold))
                envelope, dispatch = _timed(lambda: dispatch_envelope(q, selected))
                # Keep consumption observable and record only safe metadata.
                total = {k: sum(component[k] for component in (prediction, selection, dispatch))
                         for k in ("elapsed_ns", "cpu_ns")}
                raw.append({"family": family, "item_id": q.item_id, "repeat": repeat,
                            "selected_model": selected["model"], "envelope_bytes": len(envelope),
                            "prediction": prediction, "selection": selection,
                            "local_dispatch_preparation": dispatch, "total": total})
        records = [r for r in raw if r["family"] == family]
        components = {k: _summary([r[k] for r in records], cpu_usd_per_second)
                      for k in ("prediction", "selection", "local_dispatch_preparation", "total")}
        per_item = {q.item_id: _summary([r["total"] for r in records if r["item_id"] == q.item_id],
                                        cpu_usd_per_second) for q in questions}
        families[family] = {"status": "local_measurement_only", "threshold": threshold,
                            "components": components, "per_item": per_item}
    root = Path(__file__).resolve().parent
    return {"schema_version": 1, "record_type": "local_routing_overhead",
            "created_at": datetime.now(timezone.utc).isoformat(), "data_kind": input_data_kind,
            "fit_data_kind": fit_kind, "fit_sha256": digest(artifact),
            "input_sha256": input_hash,
            "input_ids": [q.item_id for q in questions], "split": "development",
            "source_sha256": {str(p.name): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in (root / "empirical.py", root / "overhead.py")},
            "target": target, "target_role": "primary" if target == .8 else "secondary",
            "warmup_passes": warmup, "measurement_passes": repetitions,
            "clock": {"elapsed": "perf_counter_ns", "cpu": "process_time_ns"},
            "environment": {"system": platform.system(), "release": platform.release(),
                            "machine": platform.machine(), "processor": platform.processor(),
                            "cpu_count": os.cpu_count(), "python": platform.python_version()},
            "router_cpu_usd_per_second": cpu_usd_per_second,
            "cost_status": "unavailable_no_cpu_rate" if cpu_usd_per_second is None else "local_cpu_component_only",
            "families": families, "raw_samples": raw,
            "boundary": {"prediction": "category lookup only; CRR includes visible feature extraction",
                         "selection": "frozen threshold, expected cost and fallback selection",
                         "dispatch": "local JSON-envelope serialization only",
                         "excluded": ["artifact loading and profile restoration", "fit/calibration/setup",
                                      "backend adapter dispatch", "network/provider/queue time",
                                      "provider attempts/retries and inference costs"]},
            "backend_dispatch_measured": False, "total_deployable_overhead_available": False,
            "execution_gate_satisfied": False, "provider_calls": 0,
            "held_out_outcomes_loaded": 0,
            "limitations": ["Local measurements include Python timing instrumentation overhead.",
                            "Synthetic-fit timing does not establish final fitted-method runtime.",
                            "Re-measure the final fit and adapter boundary before a full-cost claim.",
                            "No USD amount is inferred from absence of billing."]}
