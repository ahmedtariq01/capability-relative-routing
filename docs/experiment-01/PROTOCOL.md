# Experiment 01: LAB-Bench routing pilot

Status: draft for review, 25 October 2026. No model calls or empirical routing results accompany this proposal. The files preserve the agreed 180-question scope. The proposals below still need Leo's review before a freeze.

## Question and interpretation

For a fixed model roster on LitQA2, ProtocolQA and SeqQA, how much cost reduction does a retrospective oracle suggest at a given accuracy, and how much can a router recover using information available before inference?

The useful comparison is CRR against a development-selected fixed model and a task-category router, after charging the router's own work. A premium-only comparison can exaggerate the benefit. An oracle gap alone does not show that the gap is predictable. Existing routing literature already covers oracle comparisons, cost frontiers and capability-based selection. See [related work](RELATED-WORK.md) before claiming novelty.

This is an exploratory pilot. A successful result could justify a larger study. It would establish a result for this model roster and public multiple-choice slice, without establishing scientific utility, a new routing method, or generalisation beyond the selected tasks.

## Data and split

- Pin `futurehouse/lab-bench` to `5c77cec648430f30611808808861eb86f81d5eaa`.
- Use 60 items per subset: 20 development and 40 held out. Total: 60 development and 120 held out.
- Keep the smoke test at five development items per subset. Those 15 items are part of development, not an additional test set.
- Record original dataset IDs. Engine case numbers are a separate namespace. Require a checked mapping before an engine run.
- The proposed selection uses a declared hash ordering, with four SeqQA items from each of its 15 source subtasks. Development includes each SeqQA subtask. Treat this as within-subtask evaluation, not transfer to unseen capabilities.
- Keep selected LitQA2 items sharing a source reference on one side of the split. The available metadata cannot certify independence between all biological concepts or paraphrases. Audit exact full-input duplicates and report the remaining limits.
- Do not pass answers, key passages, source URLs, original IDs, or post-run outcomes as routing features. IDs remain bookkeeping keys. Approved features can include the task category and visible question/context/options. A finer SeqQA subtask lookup is a useful secondary baseline if the metadata is allowed at deployment.

The committed manifest contains IDs and hashes, not task text or answer keys. The source dataset marks its content CC BY-SA 4.0. A published benchmark variant must retain attribution, licence and canary metadata. The public data may already occur in model training. Our internal holdout does not resolve that contamination risk.

## Official task behaviour

The source engine pins `inspect-evals==0.20.0` and `inspect-ai==0.3.263`. Its LAB-Bench imports declare dataset and choice shuffle seeds of 7. Preserve the prepared task, prompt template, choice ordering, parser and scorer from that route.

ProtocolQA includes the `protocol` field before the question. LitQA2 and SeqQA use the question field. The upstream loader initially places the correct option first, then shuffles choices. Filtering and rebuilding samples can change that permutation. Prepare the whole pinned task first, then select the frozen IDs while preserving each sample's choices and target mapping.

Keep the upstream multiple-choice format, its abstention option and its reasoning instruction. No external retrieval or tools. Do not quietly replace this with a letter-only prompt. Store the exact prepared prompt hash and ordered-choice hashes for every item. Test correct, incorrect, abstained and malformed mock answers against the pinned scoring route before inference. This protocol does not authorise an alternate scorer.

Report accuracy over all assigned items, plus precision and coverage using the upstream definitions. An abstention, malformed answer or terminal call failure earns no correctness credit in the operational accuracy denominator. Keep those categories separate. A missing observation is not a zero-cost completed attempt.

## Collection and freeze stages

1. **Protocol review.** Agree source pins, selection, receipt fields, candidate model slots and the backend plan. Leave hosted availability explicitly unresolved until checked.
2. **Development smoke.** After model access, settings and a spend limit are agreed, run only the 15 development questions. Check prompt/answer mapping, parser behaviour, effective model identity, receipts and realistic cost. Any settings change creates a new configuration version.
3. **Development collection.** Complete the 60-by-model matrix. Reuse smoke outcomes only when their full task/model configuration matches. Preserve obsolete smoke attempts and their cost separately.
4. **Method freeze.** Fit profiles and select routing parameters using development only. Commit the feature construction, estimator, cost predictor, thresholds, baselines, failure policy and analysis plan before collecting or inspecting held-out outcomes. Document changes from this draft.
5. **Held-out collection.** Commit CRR's pre-inference choices before exposing held-out correctness or costs to its selection code. Keep gold scoring separate. Then collect the matched model matrix and analyse the frozen policies once.

A limit of 60 on the canonical engine board does not implement this split. The [compatibility note](SCREAMINGFACE-COMPATIBILITY.md) proposes a versioned selected-ID variant inside ScreamingFace. Local and hosted variants must use the same dataset, prepared samples, scorer and manifest. Results from this subset need their own benchmark identity. They are not directly comparable with a full canonical leaderboard score.

## Model and execution controls

Keep four candidate slots until exact API identifiers and access are verified. Conversational names are not frozen model versions. For each slot, record requested and effective model/version, provider route, inference settings, reasoning effort/budget, maximum output tokens, context limit, pricing snapshot and seed support. Unsupported controls need an explicit record. A changed model snapshot or fallback creates a new condition.

Use the same task presentation across models. Reasoning settings need a stated fairness policy because equal output limits need not imply equal computation. Store truncation, refusals and finish reasons. Do not silently replace a failed or unavailable model.

Proposed operational defaults: fixed concurrency of one for initial collection, a predeclared interleaving of model calls, and at most two retries after the first attempt for transient transport/rate errors. Charge every attempt. Do not retry an incorrect, abstained or malformed answer just to obtain a better score. Final timeout values and retry backoff belong in the frozen configuration. Resume from durable attempt records without duplicating completed calls.

For fresh collection, disable engine response reuse where supported and keep capture enabled. Record provider prompt-cache usage separately from engine replay. A replay has no new provider execution and cannot supply a fresh provider latency measurement. Local wall time, queue time, provider time and parsing/scoring time must remain distinguishable.

## Routing and baselines

The current `ModelProfile` and `Problem` objects require empirical capability estimates and task weights. The repository currently supplies synthetic profiles. It does not yet define a validated way to estimate these from the 60 development items. Leo needs to choose the method. An implementation that uses only category-level profiles is a category router and cannot support an additional within-category capability claim.

Compare the following on identical held-out items:

| Policy | Selection information | Interpretation |
| --- | --- | --- |
| Every fixed model | No per-item adaptation | All individual cost/quality points |
| Development-selected fixed model | Development results only | Deployable baseline with a declared selection rule |
| Task-category router | Three subset labels and development results | Tests whether category recognition explains the benefit |
| Finer subtask lookup, if allowed | Source subtask metadata and development results | Secondary control, sparse with this sample |
| CRR | Frozen pre-inference features and development profiles | Candidate method under test |
| Cheap-to-strong cascade | Cheap model output plus an observable gate | Separate sequential policy, with both calls charged when escalating |
| Fixed-model mixtures | A declared random mixture independent of item content | Cost/quality reference. A test-selected convex hull is retrospective |
| Hindsight oracle | Observed answers and costs for all models | Optimistic reference on this finite outcome matrix |

For each accuracy target, choose thresholds or mixtures on development and freeze them. Plot the predeclared grid on held out. Do not select a new threshold using held-out results and call it a deployable improvement.

The cascade gate must use observable evidence such as abstention or a predeclared confidence signal. It must never escalate because the cheap answer is known to be wrong. A confidence-generation call also costs money. Matrix replay is valid only if the strong model receives the same independent prompt as its collected call. If it sees the cheap answer or critique, that is another execution condition requiring new data. CRR's current uncertainty escalation happens before execution and is not this cascade.

Charge feature extraction, embeddings, profiling calls, router inference and escalation. Separate one-time calibration cost from per-query cost and report both. A single scalar model cost needs an explicit approximation policy when output length varies across questions.

## Oracle and accounting

Build an outcome matrix for every assigned item and every frozen model. Include failed and all-model-miss items. At target accuracy `q`, compare the least-cost fixed policy or allowed mixture with CRR and the retrospective oracle under the same denominator and price table. Report unattainable targets as undefined.

The current oracle uses observed outcomes and per-item costs. This selects successes after seeing them, including lucky single samples. It does not estimate reliable per-item success probabilities or an achievable future saving. Any capture fraction `(C_fixed - C_CRR) / (C_fixed - C_oracle)` is undefined when the denominator is zero, negative or based on an unattainable target. Report raw costs and accuracies alongside it.

Maintain three separate amounts: the actual bill for collecting all models, the replayed cost of a chosen policy, and its modelled cost under a frozen price table. Missing usage or price remains null with a reason. Never turn it into zero. Do not issue a dollar-savings claim while required amounts are unresolved. Trials that fail still count their known charges. Credits and discounts do not make inference computationally free.

With four models, the matrix contains 720 first attempts: 240 development and 480 held out. The 60 smoke attempts are included in the 240 when reusable. Router calls, retries and changed-condition reruns add to that figure. This is a request count, not a dollar budget. Set a hard agreed spend ceiling and stop on missing billing evidence or identity drift.

## Uncertainty and stopping rules

Use paired item-level comparisons, stratified by subset. Where selected items share a recorded source, keep the cluster together in resampling and record the independent-unit count. Proposed reporting uses 5,000 bootstrap resamples with a fixed seed, alongside raw numerators, denominators and paired accuracy differences. Report invalid or degenerate intervals instead of silently dropping them. Finite-data intervals do not measure model/provider stochastic variation with one draw per cell.

With 120 held-out items, small gains have substantial uncertainty, especially within 40-item subsets. An overlapping interval or a non-significant accuracy difference does not establish equivalent quality. A confirmatory matched-quality claim requires an agreed non-inferiority margin and adequate design, which this draft does not supply.

Stop or narrow the claim if the cheapest fixed model dominates, oracle headroom is negligible, category routing explains the gain, routing overhead removes the saving, or the data cannot support a reliable comparison. A null result remains useful. Do not expand the study after seeing test results and continue presenting the same holdout as untouched.

## Artifacts and outstanding decisions

Keep the manifest, selected IDs, prepared-input and choice-order hashes, versioned configuration, route decisions, per-attempt receipts, scoring outputs and analysis commands together. The [receipt contract](RECEIPTS.md) specifies the join keys and missing-data handling. The offline validator checks selection and freeze prerequisites. It is not an engine or model evaluation.

The review questions in [DECISIONS.md](DECISIONS.md) concern the empirical CRR mapping, backend/variant acceptance, model settings and the claim the pilot should test. No paid run follows from passing local checks.
