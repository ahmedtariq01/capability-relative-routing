# Experiment 01 — Retrospective oracle frontier

Status: executable synthetic fixture; not LAB-Bench evidence.

## Purpose

Before evaluating whether CRR can recognize local model strengths, measure whether useful heterogeneity exists at all. The oracle receives observed per-item outcomes for a fixed model set and chooses the cheapest model that solved each item.

The oracle is an analytical upper bound, not a deployable router. It has access to outcomes unavailable at decision time.

## Contract

Each item must have exactly one `ModelOutcome` row for every model. Duplicate `(item_id, model_name)` keys are rejected. Each row records `item_id`, `model_name`, `solved`, `cost_dollars`, and `latency_ms`. Incomplete matrices, negative costs, and negative latencies fail closed.

## Frontier construction

The oracle frontier is not a single maximum-quality point. It starts with the cheapest available model on every item, then identifies each missed item’s cheapest successful upgrade. If `b_i` is the cheapest baseline cost and `s_i` is the cheapest successful cost, the upgrade cost is `Delta_i = s_i - b_i`. Solvable upgrades are sorted by `Delta_i` and purchased incrementally. This produces the cheapest oracle policy at each attainable solved rate. Items that every model misses remain misses and are never silently removed from the denominator.

For the committed fixture, the frontier is:

```text
solved rate    oracle cost
1/3            $3
2/3            $6
```

The maximum-quality endpoint still corresponds to choosing the cheapest successful model per item. The frontier additionally answers matched-quality questions at lower targets. Fixed policies run one model over every item for the comparison.

For a target solved rate `q`, define:

```text
C_oracle(q)       = oracle cost if oracle solved_rate >= q
C_best-fixed(q)   = minimum fixed-model cost among policies with solved_rate >= q
O(q)              = C_best-fixed(q) - C_oracle(q)
```

If no policy reaches `q`, the matched cost is undefined rather than imputed. A zero oracle denominator is reported as no measurable opportunity, not infinite capture.

For a routed policy with cost `C_routed(q)`, opportunity capture is:

```text
eta(q) = (C_best-fixed(q) - C_routed(q)) / (C_best-fixed(q) - C_oracle(q))
```

This measures captured available savings only when the oracle establishes a nonzero opportunity. It does not establish causality, generalization, or production performance.

## Next empirical slice

Freeze 100–200 LAB-Bench items, 3–4 models, exact scoring rules, model identifiers, token/dollar prices, and latency measurement boundaries. Preserve raw per-model outcomes and a manifest hash before calculating the oracle. Then compare the oracle frontier with fixed baselines, CRR v0, and CRR plus routing overhead.
