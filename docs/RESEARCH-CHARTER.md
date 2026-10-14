# Research charter

## Position

Capability-Relative Routing (CRR) tests whether model heterogeneity can be converted into lower total inference cost at matched quality by routing each task to the cheapest predicted viable capability.

## Unit of analysis

One benchmark item routed through a declared model set under a frozen profile, cost, latency, and quality contract.

## Primary estimand

At matched measured quality q, compare total cost including routing overhead:

`Delta C(q) = C_baseline(q) - C_CRR(q)`

The baseline and CRR must use the same item set, scoring contract, model availability, and accounting units.

## Falsifiers

- CRR does not reduce cost at any matched quality after routing overhead.
- A fixed global model dominates CRR across the measured quality-cost-latency frontier.
- Benefits disappear under held-out tasks or modest model-set changes.
- Oracle routing shows negligible opportunity, indicating insufficient local heterogeneity.
- Escalation recovers quality only by approaching strong-model cost on nearly every item.

## Evidence boundary

The initial fixture is `synthetic_fixture_not_empirical`. It validates routing mechanics and accounting fields only. It does not establish LAB-Bench performance, provider pricing, latency, calibration, or generalization.

## Required receipts for the empirical phase

Every route decision should retain: item identifier, model-set manifest hash, profile version, router version, candidate estimates, selected route, routing tokens/time/cost, inference tokens/time/cost, quality outcome, escalation state, and error status. Missing provider telemetry remains unknown rather than zero.
