# Empirical CRR v0

Revision `crr-empirical-v0.1`, proposed 26 October 2026 after Leo's protocol review. This is the next method for review, with an offline reference implementation. Nobody has fitted it to real model outcomes. Leo's protocol endorsement does not approve these new numerical choices or authorise execution.

The primary question is whether visible question features improve routing beyond a three-category model profile. Both routers use the same development outcomes, cost estimates, routing rule and threshold grid. CRR adds six numerical features. It makes no routing LLM call and uses no embeddings, external retrieval or model-generated difficulty labels.

## Input boundary

The backend adapter prepares the entire pinned upstream task before selecting IDs. It passes only `item_id`, `subset`, `source_group`, `input_text` and the ordered `choices` to the router input view. `input_text` is the prepared question input, including ProtocolQA's protocol context. Keep the abstention option. Do not change the official solver prompt or scorer.

IDs and source groups serve bookkeeping and split checks only. The feature function never uses them. Gold targets, source references, fine subtask labels, model responses, token usage and observed costs cannot enter the input view. `Question.from_dict` rejects extra fields. The adapter still needs to verify input and ordered-choice hashes against the preparation record. A field allowlist cannot establish that upstream text contains no accidental answer metadata.

`fit_development` requires exactly the manifest's development IDs and their complete item/model matrix. It rejects held-out IDs, metadata mismatches, shared development/held-out source groups, duplicate or missing rows and unknown exposure status. A terminal failure stays in the matrix with correctness zero. Missing costs stop cost fitting until receipt reconciliation supplies them.

## Category profile

For each model and category, use a fixed Beta(1,1) prior. With `s` successes in `n` assigned development items, the estimated success probability is `(s + 1)/(n + 2)`. Abstentions, malformed outputs and terminal failures contribute to `n`, without success credit.

Record `n`, `s`, the posterior mean and posterior standard deviation. This shrinks small samples towards 0.5. The posterior SD describes uncertainty under an independent Bernoulli model. It does not establish frequentist coverage, calibration, or independence of related scientific questions. Routing uses the posterior mean. It does not treat that SD as a verified confidence signal or select a new uncertainty penalty after seeing test results.

## Visible features

Python string lengths count Unicode code points. The sequence proxy counts whole ASCII-letter tokens of eight or more A/C/G/T/U/N characters, ignoring case. These are structural proxies, not claims about task difficulty.

| Feature | Definition |
| --- | --- |
| Input length | `log(1 + len(input_text))`, including any protocol context |
| Numeric structure | Fraction of input characters satisfying `str.isdecimal()` |
| Sequence structure | Fraction of input characters in the sequence tokens defined above |
| Option count | `log(1 + number_of_choices)` |
| Option length | `log(1 + mean_choice_length)` |
| Option length spread | `(max_choice_length - min_choice_length)/max(1, mean_choice_length)` |

Retain every option, including abstention, without identifying which is correct. The features are invariant to option permutation, while the actual model call retains the upstream order. Fix the six features before development collection. Do not inspect held-out text to redesign them.

## Within-category estimator

Use one six-coefficient logistic model per candidate model. Its fixed offset is the log-odds of that model's smoothed category estimate:

`p_CRR(x,m) = sigmoid(logit(p_category[m,c]) + beta[m] dot z(x))`.

Center each feature using its training-category mean. Scale the centered feature using the pooled training root mean square, with a scale of one for a constant feature. This asks whether deviations within a category add information. It prevents a constant category marker from acting as an extra fitted category intercept. Store the means and scales from each fit. Apply them unchanged to validation or held-out inputs.

Minimise mean binary log loss plus `0.5 * ||beta||^2`. The fixed ridge coefficient is 1. There is no additional intercept, category interaction, feature selection, learned embedding or hyperparameter search. The standard-library implementation uses gradient descent with a Hessian-bound step size, maximum absolute gradient tolerance `1e-9` and a 10,000-iteration limit. Failure to converge stops fitting. Save coefficients, iterations and the final gradient norm.

The sample has only 60 development items, 20 per category. This intentionally restrained estimator may find no additional signal. The six features do not define an established new routing algorithm. Treat any benefit as an empirical result that still needs comparison with existing methods.

## Development validation and threshold selection

Use five source-group folds, stratified by the three categories. For each category, order source groups by descending size and then SHA-256 of `[method_version, source_group]`. Allocate the next group to the currently smallest fold, breaking ties by fold number. Save the full assignment. A source group never crosses folds. Fewer than five groups in a category, or a group spanning categories, stops this version rather than silently changing the split.

For each fold, fit category estimates, feature centering/scaling, coefficients and expected costs on the other four folds. Predict both routers for the untouched fold. Save the training and validation IDs and all fold profiles. This produces one out-of-fold prediction per development item/model. Report per-model Brier scores for both probability models as diagnostics. With this sample, v0 does not fit an additional probability calibrator. Smoothed or logistic probabilities are estimates, not a claim of established calibration.

For each router, evaluate thresholds `0, 0.05, ..., 1`. A question goes to the cheapest model whose predicted probability meets the threshold. Break ties by higher probability, then model slot. If no model qualifies, choose the highest predicted probability, then lower expected cost, then slot. Record `threshold_met=false`. This fallback gives every assigned item a route without pretending that a per-question quality requirement succeeded.

The proposed primary policy target is accuracy 0.80. Secondary targets are 0.50, 0.60, 0.70 and 0.90. For each target, select the threshold with the lowest observed out-of-fold policy cost among those meeting the target on development. Break ties by higher development accuracy, then lower threshold. If none meets it, record `unattainable_on_development` and no selected policy. Do not lower the target later because of held-out results.

Routing CPU cost uses one development-measured per-query estimate per family for selection. It is constant across that family's candidate thresholds and therefore does not change their order. Record actual per-query overhead for final analysis. If overhead meaningfully varies by threshold or route, amend the selection policy on development before the freeze.

The out-of-fold values help choose a threshold. They are not an unbiased estimate of the selected policy's performance, since selection uses those same values. Refit both profiles on all 60 development items after selection. Store the selected thresholds, full fit, folds and hashes before generating held-out routes. The 120 held-out outcomes provide the later policy evaluation. No fitting or threshold reselection occurs there.

## Expected inference costs

For each model/category, use the training mean of all-attempt costs under one frozen price snapshot. Include retries, failed calls and cache treatment from the receipt contract. Use only fold-training rows for out-of-fold predictions. Use all development rows for the final cost table. Unknown cost blocks cost fitting. A known zero requires supporting billing/price provenance in the adapter.

The mean is a declared v0 approximation. It does not predict item-specific output length. Both routers use the same approximation, so within-category selection differences come from estimated success probabilities. Record expected and realised policy costs separately. Do not substitute held-out token counts into pre-inference selection.

The input `Observation.cost_usd` is the sum of all attempts repriced at the frozen schedule. It is not the billed balance after credits. The backend adapter must reconcile attempt chains, configurations, usage and pricing before creating this terminal table. The offline method does not certify those external records.

## Fit and route artifacts

`scripts/fit_empirical_method.py` accepts a manifest and a development-only normalized JSON bundle. It writes fit parameters, training hashes, fold audits, out-of-fold predictions, Brier diagnostics and selected policies. It has no network or provider integration. The `plan_routes` function takes the fitted artifact and visible questions only. Its interface has no outcomes argument. It records the fit, input and route hashes, predictions, expected costs and threshold fallbacks.

Before any held-out outcome collection, freeze the reviewed method/analysis files, implementation revision, model/task settings, pricing and spending approval, final development fit hash and selected policy parameters. Then commit the route table before exposing the held-out outcome matrix. A code version or method-plan hash alone is not a fitted-method freeze.

The adapter, real development fit, hosted access and paid execution remain later stages. The implementation here makes those stages testable without pretending they have occurred.

## Sources checked

The design follows the separation of training, model selection and final evaluation described in the [scikit-learn cross-validation guide](https://scikit-learn.org/stable/modules/cross_validation.html). The [calibration guide](https://scikit-learn.org/stable/modules/calibration.html) explains why probability outputs and actual calibration are separate questions. We use these as methodological references, not as software dependencies or evidence that this estimator works. The chosen prior, features, regularization, grid and targets are explicit proposals for Leo to review.
