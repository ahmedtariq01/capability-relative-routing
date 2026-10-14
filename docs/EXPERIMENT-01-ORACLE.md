# Experiment 01 — Retrospective oracle frontier

Status: executable synthetic fixture; not LAB-Bench evidence.

## Purpose

Before evaluating whether CRR can recognize local model strengths, measure whether useful heterogeneity exists at all. The oracle receives observed per-item outcomes for a fixed model set and chooses the cheapest model that solved each item.

The oracle is an analytical upper bound, not a deployable router. It has access to outcomes unavailable at decision time.

## Contract

Each item must have exactly one `ModelOutcome` row for every model. Each row records `item_id`, `model_name`, `solved`, `cost_dollars`, and `latency_ms`. Incomplete matrices, negative costs, and negative latencies fail closed.

For each item, the oracle selects the lowest-cost successful model. If every model misses, it selects the cheapest available route and preserves the miss in the solved rate. Fixed policies run one model over every item.

## Frontier quantities

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
