# Grant proposal: Capability-Relative Routing on LAB-Bench

Researcher: Leo Guinan
Primary benchmark: LAB-Bench
Method: Capability-Relative Routing (CRR)
Status: prospective proposal; the repository currently contains validated synthetic infrastructure, not LAB-Bench evidence.

## Summary

Most model routers ask which model is best for a request. CRR asks a narrower, operational question: what is the least expensive route through the available capabilities that can reliably solve this particular problem?

Frontier models are heterogeneous. Their relative performance can vary by task while inference costs differ substantially. A globally stronger model therefore need not be the locally cheapest model that reaches a declared quality target. CRR represents each model with a capability profile, maps an incoming problem into the same capability space, and selects the least expensive predicted viable route. When the route estimate is uncertain, CRR can escalate to a stronger model or composition.

The central hypothesis is that capability heterogeneity is an exploitable computational resource, provided the benefit of selecting a route exceeds the cost of discovering and traversing it.

## Proposed experiment

The primary benchmark is LAB-Bench. I will compare:

1. each available model independently, establishing the fixed-model frontier;
2. the best fixed model under each matched-quality budget;
3. a cheap-to-strong confidence/uncertainty cascade;
4. CRR using capability-relative profiles;
5. CRR with uncertainty-triggered escalation.

A retrospective oracle will first choose the cheapest successful model for each item. The oracle frontier measures the maximum available opportunity before testing whether CRR can recognize it. This separates three questions:

```text
Does useful heterogeneity exist?      retrospective oracle frontier
Can CRR recognize it?                 CRR frontier
Does recognition survive overhead?    overhead-adjusted CRR frontier
```

The first empirical slice will target 100–200 LAB-Bench items and 3–4 models, with a complete item/model outcome matrix, frozen scoring rules, model identifiers, token and dollar prices, latency boundaries, and a manifest hash.

## Method and accounting

For model m, the capability profile is:

```text
P_m = (p_m1, ..., p_mk)
```

The problem representation is `phi(x)`. The router estimates quality `Q_hat(m, x)` and uncertainty `U(m, x)` separately. It selects the lowest-cost route satisfying the quality threshold, where cost includes model inference and routing overhead.

All results will report benchmark score, solved rate, dollar cost, token usage, end-to-end latency, routing overhead, escalation rate, and the quality–cost–latency Pareto frontier. Missing provider telemetry will remain unknown rather than being imputed as zero.

At matched quality q:

```text
Delta C(q) = C_best-fixed(q) - C_CRR(q)
```

Oracle opportunity is:

```text
O(q) = C_best-fixed(q) - C_oracle(q)
```

When the denominator is nonzero, opportunity capture is:

```text
eta(q) = [C_best-fixed(q) - C_CRR(q)] / [C_best-fixed(q) - C_oracle(q)]
```

## Hypotheses and falsifiers

H1: after routing overhead is included, CRR reduces cost at one or more matched quality levels relative to the best fixed-model strategy.

H2: uncertainty-triggered escalation recovers difficult cases without routing nearly every item to the strongest model.

H3: routing benefit increases with measurable disagreement in model rankings across capability regions.

The hypotheses are falsified if no matched-quality cost advantage remains after overhead, if the oracle shows negligible opportunity, if gains disappear under held-out tasks or model-set perturbations, or if escalation approaches strong-model cost without recovering quality.

## Contribution and evidence boundary

The immediate contribution will be a reproducible routing method, oracle frontier, cost/latency accounting contract, and public receipts. The broader contribution is a test of whether heterogeneous model ecosystems can be treated as capability networks rather than as a ranking of globally stronger and weaker models.

The current repository establishes executable mechanics and synthetic invariants. It does not yet establish LAB-Bench performance, provider pricing, calibration, generalization, or a moved empirical frontier. Those are the proposed work.

## 12-week path

Weeks 1–2: reproduce fixed-model baselines, a basic cascade, and the required baseline composition.

Weeks 3–4: construct capability profiles, freeze the item/model manifest, and calculate the oracle frontier.

Weeks 5–6: implement CRR v0 with routing cost and latency included; publish the first method iteration.

Weeks 7–8: add uncertainty-aware escalation and quality/cost thresholds.

Weeks 9–10: run ablations, model-set perturbations, and heterogeneity analysis.

Weeks 11–12: perform the final frontier sweep, robustness checks, reproducible recipes, code release, and write-up.

Application context: https://openmined.org/research/grants/
