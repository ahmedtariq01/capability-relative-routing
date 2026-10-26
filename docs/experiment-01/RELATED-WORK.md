# Research check for Experiment 01

Reviewed 25 October 2026. This is a targeted review, not a systematic-review claim. Paper results below are the authors' reports. We have not reproduced their experiments.

26 October implementation note: [METHOD.md](METHOD.md) now defines the proposed category-plus-feature estimator, and [ANALYSIS.md](ANALYSIS.md) separates oracle opportunity from CRR's incremental comparison. The earlier review below describes the repository state on 25 October. The new reference implementation does not establish novelty or empirical benefit.

## Closest prior work

| Work and source | Relevant overlap | Consequence for CRR |
| --- | --- | --- |
| [Cost-Aware Protocol Routing Across Reasoning Tasks](https://arxiv.org/html/2608.14927v1), with [public code](https://github.com/ChihHsuan-Yang/EMNLP_Cost-Aware-Protocol-Routing) | Includes LAB-Bench under two no-tool conditions, matched outcomes, metadata/text routers, development-only selection and a retrospective oracle. It routes collaboration protocols with a fixed solver within a condition. | Biology routing, an oracle gap and metadata controls already have direct precedent. CRR's cross-model action space differs, but that difference alone does not establish a research contribution. Its token-based cost analysis leaves room for an explicitly priced comparison, without proving that such a comparison is novel. |
| [COMPASS](https://arxiv.org/html/2610.27822v1), 20 October 2026 | Uses capability/performance records, related-task evidence and an LLM routing agent. Some modes preview candidate answers. It separates apparent oracle gains from gains recovered using disjoint trials. | Capability profiles and recoverable headroom are established ideas. Distinguish strictly pre-inference CRR from preview-assisted policies. Its main displayed comparison excludes router inference cost, so direct comparisons require full accounting. No reproduction claim. |
| [IRT-Router, ACL 2025](https://aclanthology.org/2025.acl-long.761/) | Models the interaction between model abilities and question attributes, including a semantic warm-up for new questions. | An interpretable model-capability/task-demand mapping needs comparison with this family. Describing CRR in those terms is not sufficient novelty. |
| [RouterBench](https://arxiv.org/html/2403.12031v2) | Uses a precomputed outcome matrix, oracle frontiers and fixed-model mixtures. | Compare with the fixed-model frontier and mixtures, not only a strong model. Shared offline outcomes are valid only when the policy does not change the actual model prompt or execution. |
| [RouteLLM](https://arxiv.org/html/2406.18665v3) | Learns routing from preference data and studies transfer and routing overhead. | Predicting which model to use and measuring overhead are not new. The later preference-conditioned experiment also needs its own literature and evaluation plan. |
| [FrugalGPT, TMLR 2024](https://lingjiaochen.com/papers/2024_FrugalGPT_TMLR.pdf) | Learns cascades that trade accuracy against cost. | The cheap-to-strong cascade is a necessary comparator. It uses post-answer information and must carry its extra calls and decision cost. |
| [LLMRouterBench, Findings of ACL 2026](https://aclanthology.org/2026.findings-acl.1881/) | Broad multi-model, multi-dataset routing evaluation with fixed and oracle comparisons. | A small bespoke slice needs a narrow reason to exist. Good performance against one premium model does not establish an improved routing frontier. |

The closest LAB-Bench study uses protocol actions, while this proposal uses model actions. That is a scope distinction to investigate, not proof of an untouched gap. The source code currently lacks CRR's empirical profile estimator. Until that choice is concrete, we cannot make a meaningful algorithm-level novelty comparison.

## A defensible pilot question

Can a development-calibrated capability mapping predict useful **within-category** differences on held-out LAB-Bench items, beyond category/subtask lookup, after charging all routing work?

That is a falsifiable question for this project. It is not an established unique question. If category lookup captures the gains, an item-level CRR claim fails. If the observed oracle gap disappears across fresh trials, it mainly reflected lucky samples. One outcome per item/model can quantify a finite-matrix opportunity, but cannot resolve the latter problem. A later repeated-trial study needs its own design and budget.

## Benchmark limitations

[LAB-Bench's paper](https://arxiv.org/html/2407.10362v3) describes a broader scientific-capability benchmark and a public subset. This project's three text-only tasks and internal holdout support a narrower conclusion. [The pinned Inspect task](https://github.com/UKGovernmentBEIS/inspect_evals/tree/v0.20.0/src/inspect_evals/lab_bench) supplies the actual template, abstention option, ProtocolQA context and scorer we propose retaining.

[LABBench2](https://github.com/EdisonScientific/labbench2) now offers a harder successor with different tasks and a separate harness. Its existence matters for the eventual paper's scope and possible saturation. It does not justify changing Leo's agreed original-LAB-Bench pilot without review. Source metadata audit here finds 199 LitQA2, 108 ProtocolQA and 600 SeqQA rows. SeqQA contains 15 subtasks with 40 rows each.

## Reddit: practical checks, not evidence of a new gap

Read the following posts and available comment threads. None validates hosted ScreamingFace behaviour or establishes paper novelty.

- [Routing savings versus a premium baseline](https://www.reddit.com/r/AI_Agents/comments/1wqpq4a/jevbased_model_routing_saved_332_vs_premium_in/): commenters challenge the comparator and statistical interpretation. Use the cheapest adequate fixed model and paired uncertainty. The vendor's numbers were not reproduced.
- [A router that may be learning task categories](https://www.reddit.com/r/mlops/comments/1wr7brd/a_learned_llm_router_scored_084_auc_shuffling_the/): the author's label-shuffle account suggests a useful diagnostic. Keep the category baseline and consider a development-only within-category permutation check. Treat the reported AUC as an unverified account. The available comment view was limited.
- [Routing and cache economics](https://www.reddit.com/r/LLMDevs/comments/1w622ke/perrequest_llm_routing_is_often_a_false_economy/): discussion emphasises cache misses, retries and overhead. Most examples concern multi-turn agents, so they do not directly estimate costs for our single-turn pilot. They motivate separate engine-replay and provider-cache receipts.

## Coverage and remaining uncertainty

The review covered CRR's current implementation, the relevant pinned ScreamingFace SDK/engine paths, the upstream Inspect task/scorer, all three public source files, primary routing literature and the linked Reddit discussions. The COMPASS HTML could not load through the web reader, so the review used the original arXiv HTML downloaded directly. We did not rely on third-party AI summaries for its method claims.

We have not demonstrated a unique gap, reproduced competing routers, obtained hosted access or run provider models. The local artifacts make the next discussion specific: agree the empirical CRR mapping, supported selection mechanism and the pilot's comparison before spending on a matrix.
