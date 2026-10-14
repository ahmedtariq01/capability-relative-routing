# Capability-Relative Routing (CRR)

Research repository for **Capability-Relative Routing: Finding the Cheapest Viable Path Through a Network of Models**.

Researcher: Leo Guinan  
Primary benchmark: LAB-Bench  
Status: prospective; the current executable layer is a deterministic synthetic routing fixture, not benchmark evidence.

## Research question

When heterogeneous models have different local strengths, can a router select the least expensive route that reaches a declared quality threshold after charging routing overhead?

The repository is intentionally evidence-bounded:

- implemented: capability-profile data model, cost-aware route selection, and confidence-triggered escalation;
- locally verified: deterministic unit tests and a one-shot synthetic smoke run;
- not yet evidence: LAB-Bench results, provider costs, model heterogeneity estimates, or claims about frontier movement;
- private data: no credentials, prompts from private corpora, or provider responses are committed.

## Quickstart

```text
python3 -m unittest discover -s tests -v
python3 verify.py
```

Both commands use only the Python standard library.

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

No external repository has been created or pushed by this local scaffold.
