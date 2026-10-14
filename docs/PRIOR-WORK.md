# Prior work: dynamic and semantic routing experiments

Status: source-bounded research history supplied by the researcher. The numerical results below are recorded as prior-work observations, not as independently replayed evidence in this repository. Original code and artifact URLs should be added when available; no link is invented here.

## Question

When is the value obtained by selecting a better computational route greater than the cost of discovering and traversing that route?

This question emerged from controlled experiments on dynamic computational routing, before the CRR proposal generalized it to heterogeneous frontier language models.

## Controlled communicative-arithmetic experiment

In a controlled communicative-arithmetic experiment:

- semantic routing accepted 494 of 500 outputs;
- fixed FP32 execution accepted 387 of 500 outputs;
- semantic routing had greater mean latency: 1.2935 ms versus 0.8116 ms.

The important result was not only the outcome difference. Routing improved accepted outputs while imposing coordination cost.

## Controls and follow-up measurements

Follow-up experiments removed caching and isolated communication cost:

- no-cache semantic routing accepted 490 of 500 outputs;
- mean latency increased to 1.5426 ms;
- approximately 0.7197 ms of that latency was attributed to communication;
- across 16 tested conditions, cached and uncached routing each won on latency in only 2 conditions.

Further experiments mapped a phase boundary in which dynamic reuse became beneficial as overlap increased relative to environmental drift.

## Interpretation

These experiments support a narrow observation: route selection can improve an outcome metric while losing on latency once communication and coordination are charged. They do not establish that the same pattern transfers to language models, LAB-Bench, or provider-priced inference.

The unresolved question was therefore not “does routing work?” It was:

```text
When does the value of selecting a better route exceed the cost of discovering and traversing it?
```

CRR is the proposed next experiment. It moves the unit of analysis from controlled computational routes to heterogeneous model capabilities, preserves routing overhead in the objective, and adds a retrospective oracle to measure whether useful local heterogeneity exists before evaluating the router.

## Relation to the proposed work

```text
accomplished work
  dynamic/semantic routing experiments
        ↓
observed tension
  better accepted outcomes, sometimes worse latency
        ↓
open question
  when is route selection worth its coordination cost?
        ↓
proposed work
  capability-relative routing on LAB-Bench
        ↓
measurement sequence
  oracle opportunity → CRR capture → overhead-adjusted frontier
```

## Evidence boundary

The prior-work numbers are recorded here exactly as supplied in the research history. This document is not a substitute for source code, raw outputs, benchmark definitions, or independent replay. Before treating these results as formal evidence in a paper or application, add the original artifact links, protocol/version identifiers, seeds, and receipts. The repository currently uses them to document research trajectory and motivation, not to claim external validation.
