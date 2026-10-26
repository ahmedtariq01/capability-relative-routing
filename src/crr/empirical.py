"""Development-only v0 reference method. No provider or dataset loading code.

Inputs must come from the pinned, prepared task, after choice shuffling. This
module never accepts a gold field in its input view. An adapter must validate
the preparation hashes and reconcile terminal outcomes to attempt receipts.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import re
from statistics import mean

METHOD_VERSION = "crr-empirical-v0.1"
FEATURE_NAMES = (
    "log_input_chars", "digit_fraction", "sequence_fraction",
    "log_choice_count", "log_mean_choice_chars", "choice_length_range",
)
THRESHOLDS = tuple(i / 20 for i in range(21))
TARGETS = (0.5, 0.6, 0.7, 0.8, 0.9)
PRIMARY_TARGET = 0.8
FOLDS = 5
RIDGE = 1.0
GRADIENT_TOLERANCE = 1e-9
MAX_ITERATIONS = 10000


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def nonnegative(value: float, name: str) -> None:
    if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and non-negative")


@dataclass(frozen=True)
class Question:
    item_id: str
    subset: str
    source_group: str
    input_text: str
    choices: tuple[str, ...]

    def __post_init__(self):
        if not all(isinstance(x, str) and x for x in
                   (self.item_id, self.subset, self.source_group, self.input_text)):
            raise ValueError("question identity and prepared input must be non-empty strings")
        if not isinstance(self.choices, tuple) or len(self.choices) < 2 or not all(
                isinstance(x, str) and x for x in self.choices):
            raise ValueError("choices must contain at least two non-empty strings")

    @classmethod
    def from_dict(cls, value: dict) -> "Question":
        if set(value) != {"item_id", "subset", "source_group", "input_text", "choices"}:
            raise ValueError("input view contains unexpected fields or lacks required fields")
        if not isinstance(value["choices"], (list, tuple)):
            raise ValueError("choices must be a sequence of option strings")
        return cls(**{**value, "choices": tuple(value["choices"])})


@dataclass(frozen=True)
class Observation:
    item_id: str
    model: str
    solved: bool
    response_status: str  # observable: answered, abstained, malformed, failed
    cost_usd: float | None  # all attempts, repriced at the frozen price table

    def __post_init__(self):
        if not all(isinstance(v, str) and v for v in (self.item_id, self.model)):
            raise ValueError("item and model identifiers must be non-empty strings")
        if type(self.solved) is not bool:
            raise ValueError("solved must be boolean")
        if self.response_status not in {"answered", "abstained", "malformed", "failed"}:
            raise ValueError("unknown response status")
        if self.solved and self.response_status != "answered":
            raise ValueError("only an answered item can be solved")
        if self.cost_usd is not None:
            nonnegative(self.cost_usd, "cost")


def features(question: Question) -> tuple[float, ...]:
    """Lengths/structure of the complete visible input and ordered options.

    Sequence = whole ASCII-letter tokens of >=8 A/C/G/T/U/N characters. This
    deliberately narrow proxy is not a sequence recognizer or a difficulty label.
    Include all options, including the upstream abstention option, unchanged.
    """
    text = question.input_text
    sequence_chars = sum(len(m[0]) for m in re.finditer(
        r"(?<![A-Za-z])[ACGTUNacgtun]{8,}(?![A-Za-z])", text))
    lengths = [len(s) for s in question.choices]
    average = mean(lengths)
    return (math.log1p(len(text)), sum(c.isdecimal() for c in text) / len(text),
            sequence_chars / len(text), math.log1p(len(lengths)),
            math.log1p(average), (max(lengths) - min(lengths)) / max(1, average))


def validate_matrix(questions: tuple[Question, ...], observations: tuple[Observation, ...],
                    models: tuple[str, ...]) -> dict[tuple[str, str], Observation]:
    ids = [q.item_id for q in questions]
    if not ids or len(ids) != len(set(ids)) or not models or len(models) != len(set(models)):
        raise ValueError("questions and model slots must be non-empty and unique")
    by_key = {(r.item_id, r.model): r for r in observations}
    if len(by_key) != len(observations):
        raise ValueError("duplicate item/model observation")
    if set(by_key) != {(item, model) for item in ids for model in models}:
        raise ValueError("incomplete or unexpected outcome matrix")
    return by_key


def validate_development(manifest: dict, questions: tuple[Question, ...],
                         observations: tuple[Observation, ...]) -> tuple[str, ...]:
    if manifest["method"]["held_out_outcomes_seen"] is not False:
        raise ValueError("held-out exposure must be explicitly false")
    entries = manifest["selection"]["items"]
    if len({r["original_id"] for r in entries}) != len(entries):
        raise ValueError("duplicate manifest IDs")
    dev = {r["original_id"]: r for r in entries if r["split"] == "development"}
    if {q.item_id for q in questions} != set(dev):
        raise ValueError("fit requires exactly the manifest development IDs")
    held_groups = {r["source_group"] for r in entries if r["split"] == "held_out"}
    for q in questions:
        if (q.subset, q.source_group) != (dev[q.item_id]["subset"], dev[q.item_id]["source_group"]):
            raise ValueError("question metadata differs from the manifest")
        if q.source_group in held_groups:
            raise ValueError("source group crosses the development/held-out split")
    models = tuple(sorted(m["slot"] for m in manifest["models"]))
    validate_matrix(questions, observations, models)
    if any(r.cost_usd is None for r in observations):
        raise ValueError("missing development costs: reconcile receipts before cost fitting")
    return models


def grouped_folds(questions: tuple[Question, ...]) -> dict[str, int]:
    groups: dict[str, list[Question]] = defaultdict(list)
    for q in questions:
        groups[q.source_group].append(q)
    if any(len({q.subset for q in group}) != 1 for group in groups.values()):
        raise ValueError("cross-category source group needs an explicit fold-design amendment")
    assignment = {}
    for subset in sorted({q.subset for q in questions}):
        candidates = [g for g in groups if groups[g][0].subset == subset]
        if len(candidates) < FOLDS:
            raise ValueError("need at least five source groups per category")
        loads = [0] * FOLDS
        # Largest groups first, then a declared hash independent of all outcomes.
        for group in sorted(candidates, key=lambda g: (-len(groups[g]), digest([METHOD_VERSION, g]))):
            fold = min(range(FOLDS), key=lambda k: (loads[k], k))
            loads[fold] += len(groups[group])
            assignment.update({q.item_id: fold for q in groups[group]})
    return assignment


@dataclass(frozen=True)
class CategoryEstimate:
    n: int
    successes: int
    probability: float
    posterior_sd: float
    expected_cost_usd: float


def sigmoid(value: float) -> float:
    if value >= 0:
        return 1 / (1 + math.exp(-value))
    e = math.exp(value)
    return e / (1 + e)


@dataclass(frozen=True)
class FittedModel:
    model: str
    categories: dict[str, CategoryEstimate]
    means: dict[str, tuple[float, ...]]
    scales: tuple[float, ...]
    coefficients: tuple[float, ...]
    iterations: int
    gradient_max: float

    def __post_init__(self):
        if not self.categories or set(self.categories) != set(self.means):
            raise ValueError("profile categories and feature centers differ")
        vectors = [self.coefficients, self.scales, *self.means.values()]
        if any(len(v) != len(FEATURE_NAMES) or any(type(x) not in (float, int) or not math.isfinite(x)
               for x in v) for v in vectors) or any(x <= 0 for x in self.scales):
            raise ValueError("invalid fitted feature vectors")
        for category in self.categories.values():
            if (type(category.n) is not int or category.n < 1 or type(category.successes) is not int
                    or not 0 <= category.successes <= category.n
                    or not 0 < category.probability < 1):
                raise ValueError("invalid category estimate")
            nonnegative(category.posterior_sd, "category uncertainty")
            nonnegative(category.expected_cost_usd, "expected cost")

    def predict(self, question: Question) -> dict:
        if question.subset not in self.categories:
            raise ValueError("unseen category")
        category = self.categories[question.subset]
        z = [(x - mu) / scale for x, mu, scale in zip(features(question), self.means[question.subset], self.scales)]
        offset = math.log(category.probability / (1 - category.probability))
        return {"model": self.model, "category_probability": category.probability,
                "category_posterior_sd": category.posterior_sd,
                "crr_probability": sigmoid(offset + sum(w * x for w, x in zip(self.coefficients, z))),
                "expected_cost_usd": category.expected_cost_usd}


def _fit(questions: tuple[Question, ...], observations: tuple[Observation, ...],
         models: tuple[str, ...]) -> tuple[FittedModel, ...]:
    """Internal fold fit. The public entry point validates split membership."""
    index = validate_matrix(questions, observations, models)
    x = [features(q) for q in questions]
    means = {subset: tuple(mean(column) for column in zip(*(row for q, row in zip(questions, x) if q.subset == subset)))
             for subset in sorted({q.subset for q in questions})}
    centered = [tuple(v - mu for v, mu in zip(row, means[q.subset])) for q, row in zip(questions, x)]
    scales = tuple(math.sqrt(mean(v * v for v in column)) or 1.0 for column in zip(*centered))
    z = [tuple(v / scale for v, scale in zip(row, scales)) for row in centered]
    # Logistic Hessian <= (X'X)/(4n) + lambda I. Trace bounds its largest eigenvalue.
    step = 1 / (RIDGE + sum(sum(v * v for v in row) for row in z) / (4 * len(z)))
    fitted = []
    for model in models:
        categories = {}
        for subset in sorted({q.subset for q in questions}):
            rows = [index[q.item_id, model] for q in questions if q.subset == subset]
            n, successes = len(rows), sum(r.solved for r in rows)
            a, b = successes + 1, n - successes + 1
            categories[subset] = CategoryEstimate(n, successes, a / (a + b),
                math.sqrt(a * b / ((a + b)**2 * (a + b + 1))), mean(r.cost_usd for r in rows))
        offsets = [math.log(categories[q.subset].probability / (1 - categories[q.subset].probability))
                   for q in questions]
        y = [index[q.item_id, model].solved for q in questions]
        weights = [0.0] * len(FEATURE_NAMES)
        for iteration in range(1, MAX_ITERATIONS + 1):
            residuals = [sigmoid(off + sum(w * v for w, v in zip(weights, row))) - outcome
                         for row, off, outcome in zip(z, offsets, y)]
            gradient = [mean(r * row[j] for r, row in zip(residuals, z)) + RIDGE * weights[j]
                        for j in range(len(weights))]
            maximum = max(abs(v) for v in gradient)
            if maximum <= GRADIENT_TOLERANCE:
                break
            weights = [w - step * g for w, g in zip(weights, gradient)]
        else:
            raise ValueError("regularized fit did not converge")
        fitted.append(FittedModel(model, categories, means, scales, tuple(weights), iteration, maximum))
    return tuple(fitted)


def choose(predictions: list[dict], family: str, threshold: float) -> dict:
    if family not in {"category", "crr"} or threshold not in THRESHOLDS:
        raise ValueError("unknown routing family or threshold")
    if not predictions or len({p["model"] for p in predictions}) != len(predictions):
        raise ValueError("predictions must contain unique models")
    for p in predictions:
        nonnegative(p["expected_cost_usd"], "expected cost")
        for field in ("category_probability", "crr_probability"):
            if type(p[field]) not in (int, float) or not math.isfinite(p[field]) or not 0 <= p[field] <= 1:
                raise ValueError("invalid predicted probability")
    key = family + "_probability"
    viable = [p for p in predictions if p[key] >= threshold]
    if viable:
        selected = min(viable, key=lambda p: (p["expected_cost_usd"], -p[key], p["model"]))
    else:
        selected = min(predictions, key=lambda p: (-p[key], p["expected_cost_usd"], p["model"]))
    return {"model": selected["model"], "probability": selected[key],
            "expected_cost_usd": selected["expected_cost_usd"], "threshold_met": bool(viable)}


def select_threshold(questions: tuple[Question, ...], observations: tuple[Observation, ...],
                     predictions: dict[str, list[dict]], family: str, target: float) -> dict:
    if target not in TARGETS:
        raise ValueError("target is outside the declared grid")
    models = tuple(sorted({p["model"] for rows in predictions.values() for p in rows}))
    index = validate_matrix(questions, observations, models)
    if set(predictions) != {q.item_id for q in questions}:
        raise ValueError("prediction IDs differ from the development questions")
    if any(len(rows) != len(models) or {p["model"] for p in rows} != set(models) for rows in predictions.values()):
        raise ValueError("incomplete prediction matrix")
    candidates = []
    for threshold in THRESHOLDS:
        selected = [index[q.item_id, choose(predictions[q.item_id], family, threshold)["model"]]
                    for q in questions]
        if any(r.cost_usd is None for r in selected):
            raise ValueError("unknown calibration cost")
        candidates.append({"threshold": threshold, "accuracy": mean(r.solved for r in selected),
                           "mean_cost_usd": mean(r.cost_usd for r in selected)})
    eligible = [c for c in candidates if c["accuracy"] >= target]
    selected = min(eligible, key=lambda c: (c["mean_cost_usd"], -c["accuracy"], c["threshold"])) if eligible else None
    return {"target": target, "status": "selected" if selected else "unattainable_on_development",
            "selected": selected, "candidates": candidates}


def fit_development(manifest: dict, questions: tuple[Question, ...],
                    observations: tuple[Observation, ...]) -> dict:
    models = validate_development(manifest, questions, observations)
    questions = tuple(sorted(questions, key=lambda q: q.item_id))
    observations = tuple(sorted(observations, key=lambda r: (r.item_id, r.model)))
    folds = grouped_folds(questions)
    oof, audits = {}, []
    for fold in range(FOLDS):
        training = tuple(q for q in questions if folds[q.item_id] != fold)
        validation = tuple(q for q in questions if folds[q.item_id] == fold)
        train_ids = {q.item_id for q in training}
        profiles = _fit(training, tuple(r for r in observations if r.item_id in train_ids), models)
        for q in validation:
            oof[q.item_id] = [profile.predict(q) for profile in profiles]
        audits.append({"fold": fold, "train_ids": sorted(train_ids),
                       "validation_ids": [q.item_id for q in validation],
                       "profiles": [asdict(profile) for profile in profiles]})
    index = {(r.item_id, r.model): r for r in observations}
    brier = {family: {model: mean((next(p for p in oof[q.item_id] if p["model"] == model)
                    [family + "_probability"] - index[q.item_id, model].solved)**2 for q in questions)
                    for model in models} for family in ("category", "crr")}
    profiles = _fit(questions, observations, models)
    from .analysis import fixed_selection
    model_accuracy = {m: mean(r.solved for r in observations if r.model == m) for m in models}
    model_cost = {m: mean(r.cost_usd for r in observations if r.model == m) for m in models}
    cheap = min(models, key=lambda m: (model_cost[m], -model_accuracy[m], m))
    stronger = [m for m in models if model_accuracy[m] > model_accuracy[cheap]]
    strong = min(stronger, key=lambda m: (-model_accuracy[m], model_cost[m], m)) if stronger else None
    return {"method_version": METHOD_VERSION, "status": "development_fit_not_execution_approval",
            "training_ids": [q.item_id for q in questions], "training_inputs_sha256": digest([asdict(q) for q in questions]),
            "training_outcomes_sha256": digest([asdict(r) for r in observations]),
            "folds": folds, "fold_audits": audits, "oof_predictions": oof,
            "oof_brier": brier, "profiles": [asdict(p) for p in profiles],
            "fixed_model_selections": {str(q): fixed_selection(observations, q, model_roster=models) for q in TARGETS},
            "cascade": {"cheap": cheap, "strong": strong,
                        "status": "selected" if strong else "no_more_accurate_development_model",
                        "gate": "abstained_or_malformed_or_failed"},
            "selections": {f: [select_threshold(questions, observations, oof, f, q) for q in TARGETS]
                           for f in ("category", "crr")},
            "limitations": ["OOF selection scores are tuning diagnostics, not unbiased policy performance.",
                            "Posterior SD assumes independent Bernoulli trials within a category.",
                            "No fitted probability calibration or held-out performance is established."]}


def restore_profiles(artifact: dict) -> tuple[FittedModel, ...]:
    if artifact["method_version"] != METHOD_VERSION:
        raise ValueError("method version mismatch")
    return tuple(FittedModel(**{**p, "categories": {k: CategoryEstimate(**v) for k, v in p["categories"].items()},
                     "means": {k: tuple(v) for k, v in p["means"].items()}, "scales": tuple(p["scales"]),
                     "coefficients": tuple(p["coefficients"])}) for p in artifact["profiles"])


def plan_routes(artifact: dict, questions: tuple[Question, ...], family: str, target: float) -> dict:
    """Plan from visible inputs and a frozen fit. No outcomes argument exists.

    Planning itself is not approval to collect. The caller must verify the
    fit hash, assigned IDs, task hashes, manifest freeze and budget separately.
    """
    if family not in {"category", "crr"} or target not in TARGETS:
        raise ValueError("unknown family or target")
    if not questions or len(questions) != len({q.item_id for q in questions}):
        raise ValueError("route inputs must be non-empty and unique")
    selection = next(s for s in artifact["selections"][family] if s["target"] == target)
    if selection["selected"] is None:
        return {"status": "unattainable_on_development", "family": family, "target": target, "routes": None}
    threshold = selection["selected"]["threshold"]
    profiles = restore_profiles(artifact)
    rows = {q.item_id: choose([p.predict(q) for p in profiles], family, threshold)
            for q in sorted(questions, key=lambda q: q.item_id)}
    return {"status": "planned_not_execution_approval", "family": family, "target": target,
            "threshold": threshold, "fit_sha256": digest(artifact),
            "visible_inputs_sha256": digest([asdict(q) for q in sorted(questions, key=lambda q: q.item_id)]),
            "routes": rows, "routes_sha256": digest(rows)}
