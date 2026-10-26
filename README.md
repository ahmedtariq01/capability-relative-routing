# Capability-Relative Routing (CRR)

Research repository for **Capability-Relative Routing: Finding the Cheapest Viable Path Through a Network of Models**.

Researcher: Leo Guinan  
Primary benchmark: LAB-Bench  
Status: prospective. The repository includes an empirical-method reference implementation and generated-fixture checks. No benchmark model outcomes have fitted or evaluated it yet.

## Grant application summary

Grant proposal: [Capability-Relative Routing on LAB-Bench](docs/PROPOSAL.md)

Hypothesis: heterogeneous model capabilities can be exploited to reduce inference cost at matched quality after routing overhead.

Current status: synthetic infrastructure validated; empirical frontier experiment proposed.

First empirical test proposed in the current protocol: 180 LAB-Bench items with four provisional model slots, comparing fixed-model and retrospective oracle frontiers.

A [protocol review package](docs/experiment-01/README.md) proposes the agreed 180-item slice, a 60/120 development/held-out split, and ScreamingFace compatibility checks. Leo endorsed the foundation on 26 October. The next [method](docs/experiment-01/METHOD.md) and [analysis](docs/experiment-01/ANALYSIS.md) proposal implements development-only category shrinkage, regularized visible-feature routing and separate oracle/incremental comparisons. Model access, a real development fit and the execution freeze remain unresolved.

Prior trajectory: [dynamic and semantic routing experiments](docs/PRIOR-WORK.md) established the motivating tension between improved outcomes and coordination cost.

## Research question

When heterogeneous models have different local strengths, can a router select the least expensive route that reaches a declared quality threshold after charging routing overhead?

The repository is intentionally evidence-bounded:

- implemented: the original routing primitive, proposed empirical v0 estimator, development-only threshold selection, cost replay and paired analysis;
- locally verified: deterministic unit tests and a one-shot synthetic smoke run;
- not yet evidence: LAB-Bench results, provider costs, model heterogeneity estimates, or claims about frontier movement;
- private data: no credentials, prompts from private corpora, or provider responses are committed.

## Quickstart

```text
python3 -m unittest discover -s tests -v
python3 verify.py
python3 scripts/check_empirical_method.py
```

These commands use only the Python standard library.

## Layout

```text
src/crr/                 Core routing primitive
 tests/                  Executable invariants
configs/                 Explicit model/cost fixture
claims/                  Claim ledger and falsifiers
docs/                    Research charter and protocol boundary
data/fixtures/          Synthetic inputs only
artifacts/               Generated receipts (ignored unless deliberately added)
```

## Planned experimental sequence

1. Reproduce fixed-model baselines and a cheap-to-strong cascade.
2. Freeze a LAB-Bench task/model/cost manifest and calculate the retrospective oracle frontier.
3. Implement provider-backed capability profiles and charge routing tokens, dollars, and latency.
4. Add uncertainty-aware escalation and model-set perturbation tests.
5. Publish receipts, ablations, negative results, and a paper only after independent readback.

The repository is public at https://github.com/leo-guinan/capability-relative-routing. External publication does not imply empirical validity; the evidence boundary above remains unchanged.
