# Experiment 01 analysis policy

Revision `crr-analysis-v0.2`, updated 27 October 2026 for [Leo's conditional review](https://github.com/leo-guinan/capability-relative-routing/pull/1#issuecomment-6445333948). This revision adds the uniform-mixture control and clarifies the primary target and interpretation. Final specification review and execution prerequisites remain open. Freeze this policy and the fitted method before collecting or inspecting held-out outcomes. The empirical method and analysis checks use generated outcome fixtures. No real model outcomes accompany this revision.

Label the planned results a single-draw finite-matrix evaluation conditional on provider stochasticity. Each item/model cell contributes one observed outcome under the frozen attempt policy. The two measurements below have different cost boundaries.

## Oracle opportunity

At each declared target `q`, use the complete 120-item by four-model outcome matrix. Every assigned item stays in the denominator. Let `C_fixed(q)` be the minimum all-attempt inference cost among the four individual fixed models whose observed accuracy meets `q`. Let `C_oracle(q)` be the minimum cost of an item-wise assignment meeting `ceil(120*q)` observed successes. The primary opportunity is `C_fixed(q) - C_oracle(q)`.

Both references select retrospectively from the same matrix. Neither is a deployable policy trained on test outcomes. The oracle assumes free knowledge of outcomes and zero oracle decision cost. All-model-miss items still incur their cheapest attempted call. An unattainable target, incomplete matrix or unknown cost produces an explicit unavailable result, never a zero saving. Report both raw costs, accuracies, assigned count, missing-cost count and scope with the gap.

Use the same frozen price snapshot and attempt boundary on both sides. Oracle opportunity is an inference-cost-only retrospective upper bound on savings relative to the eligible individual fixed-model reference, within this finite matrix. It assumes free oracle knowledge and excludes routing overhead. A single lucky response can increase the apparent opportunity. It does not estimate reliable future success probabilities or an achievable deployable saving. The development-selected fixed model remains a separate deployable baseline.

## Incremental CRR improvement

For each target, compare the category router and CRR policies selected on development under [METHOD.md](METHOD.md). Route the same held-out inputs with each frozen policy before looking at any outcomes. Replay each committed selection on the common matrix. Evaluate CRR improvement on total deployable cost: feature extraction, prediction, selection, dispatch and the selected model's complete attempt chain, including retries and failed attempts.

Report mean per-query saving `cost_category - cost_CRR`, accuracy difference `accuracy_CRR - accuracy_category`, raw successes/assigned items, failures and each policy's achieved accuracy. Positive cost saving alone does not establish improvement at matched quality. Two policies both exceeding a common target also need not have equal accuracy.

The primary target is 0.80, as declared in the 26 October proposal before any real collection recorded in this package. If either router cannot attain it on development, leave the primary incremental result unavailable. Do not replace the target after inspecting development or held-out results. Report every declared secondary target, including unavailable selections and target failures, without promoting one into the primary comparison. Do not select a new operating point or interpolate a deployable router using held-out accuracy. A test-selected cost/quality frontier may appear only as a labelled retrospective diagnostic.

For this exploratory pilot, report a conservative zero-loss check: both frozen policies meet the target, the paired accuracy-difference interval lies entirely at or above zero, and the paired saving interval lies above zero. Require nondegenerate intervals and at least two source clusters per subset. The result field is `exploratory_zero_loss_rule_met`. It never sets `confirmatory_matched_quality_claim=true`. A confirmatory non-inferiority claim needs a justified margin, power/design review and an approved analysis amendment before held-out collection. Lack of significance does not establish equal quality.

Do not use an oracle capture fraction as the incremental CRR measure. If shown secondarily, the fraction `(C_fixed - C_CRR)/(C_fixed - C_oracle)` requires consistent cost units and target eligibility. It is undefined for zero or negative headroom, missing costs or unattainable targets. Do not clip negative or greater-than-one values to hide a failed comparison.

## Frozen baseline definitions

| Baseline | Definition and boundary |
| --- | --- |
| Individual fixed models | Run each roster model for every assigned item. Show all four points. |
| Development-selected fixed | At each target, choose the lowest development mean-cost model meeting it. Break ties by higher accuracy then model slot. If none qualifies, mark unavailable. Never reselect it from test outcomes. |
| Category router | Beta-smoothed category profiles, shared expected-cost table and development-selected threshold. |
| CRR | Same procedure plus the six within-category features and fixed regularized estimator. |
| Cheap-to-strong cascade | Choose cheap by development mean cost, then higher accuracy, then slot. Choose strong by best development accuracy among models strictly more accurate than cheap, then cost, then slot. If no such model exists, report no cascade. Escalate only on observable abstention, malformed output or terminal failure. An answered-but-wrong output never triggers the gate. Strong receives the original independent task prompt. Charge both stages on escalation. |
| Uniform mixture | Secondary control that selects one of the four declared model slots with probability 0.25 each, independently of the item, category, outcomes and costs. Use the analytic expected accuracy and cost on the complete matrix. No fitted weights or additional model runs. |
| Fixed mixtures | Secondary expected points for every pair of models at weights 0, 0.05, ..., 1. Model choice is independent of the item and response. These integrate external randomisation. They do not belong to the primary deterministic, integer-success oracle denominator. Label any test-selected hull retrospective. |
| Hindsight oracle | Retrospective item-wise minimum-cost assignment, as defined above. |

Fine SeqQA subtask lookup is excluded from v0's primary policies. It has only one or two development items per subtask, and it uses metadata outside the visible-feature contract. Adding it requires a declared secondary amendment before test outcomes. Do not relabel category routing as a within-category capability result.

For the uniform control, average the four observed correctness values and all-attempt inference costs for each item. Add the measured expected selection/dispatch overhead for that item to obtain expected total deployable cost. Then average within each subset and give the three subset means equal weight. Report per-subset values too. The expected values integrate only the uniform model-selection randomisation conditional on the observed matrix. They are neither a new provider draw nor realised random-routing outcomes. Preserve failures and all-model-miss items. An incomplete matrix is invalid. An unknown contributing inference cost makes expected inference and total cost unavailable. Unknown overhead makes total cost unavailable while preserving expected accuracy and known inference cost. Require explicit overhead records, without a default zero. Keep the uniform control outside the primary oracle denominator and primary target selection.

## Cost and latency ledger

Keep three amounts separate: actual collection bill, hypothetical selected-policy bill under the measured attempt records, and cost repriced under the frozen schedule. The implemented analysis consumes the third, plus an explicit local-compute price for routing overhead. Never replace a missing billed amount with an estimate in a billed column.

Charge every retry and failed attempt. A timeout with an unknown bill remains unknown until reconciliation. Count a terminal failure as incorrect while retaining its cost. Preserve all assigned rows when costs are missing. Missing selected-call or overhead costs make the corresponding dollar comparison unavailable. Preserve accuracy comparisons and missingness counts.

Record local feature/prediction/dispatch elapsed and CPU time, hardware/runtime, measurement repetitions and the declared CPU dollar rate. Measure category and CRR separately after warm-up. No routing LLM or embedding calls belong to v0. A zero local-dollar rate can appear as an explicitly labelled sensitivity assumption, not as the primary full-cost result. The artifact checker uses known synthetic overhead and never substitutes it for real measurement.

Report collection, calibration, fitting and one-time setup costs separately from per-query deployable cost. Any amortized result requires a query-count horizon declared before evaluation, with the components and allocation rule stated. Retain obsolete smoke attempts in the collection ledger. Do not add matrix-collection costs again when computing hypothetical policy replay. Credits and discounts remain a separate billing fact.

Report measured provider/queue/parsing time and local routing overhead separately. Cascade latency sums sequential stages. Matrix replay cannot establish live routing latency under a different load or cache regime. Engine response reuse provides no new provider latency measurement. This implementation's dollar comparison does not produce a latency claim.

## Paired uncertainty

Use 5,000 paired bootstrap resamples with seed 261026. Within each subset, resample recorded source groups with replacement and retain all items in each sampled group. Use the same draw for both policies. Compute the mean within each subset, then average the three subset means equally. This preserves the intended balanced target population even if group sizes produce unequal resample sizes.

Report the percentile 2.5% and 97.5% interval for accuracy differences and per-query savings, along with valid/invalid counts. Zero-width intervals carry `degenerate` status. Fewer than two groups in a subset blocks the exploratory zero-loss check. Cross-category source groups stop this version pending a design amendment. Do not silently discard bad rows or exceptions. Missing cost makes the cost interval unavailable without deleting accuracy observations.

The interval conditions on the fitted development policies and observed provider draws. Do not refit the policies on a bootstrap of held-out outcomes. The interval excludes training uncertainty and model/provider stochastic variation. One draw per item/model cannot measure the latter. Source metadata also cannot identify every scientific dependency. Report per-subset results alongside the balanced aggregate.

A repeated development subset may supply a separate sensitivity check if its IDs, repetition count and settings are declared before the repeats. Keep repeated outcomes out of primary fitting, threshold selection and policy revision. Report their costs separately. This revision authorises no such collection.

The 0.80 comparison is primary. The remaining targets, uniform control, pairwise mixtures, cascade and calibration plots are exploratory, with no multiplicity-adjusted significance claims. A larger study or new target chosen after inspecting this test set needs new evaluation data.

## Required result bundle

Every later result bundle needs the manifest, implementation, fitted-method, price-table and committed-route hashes. Include target/status rows for both measurements, all baseline points, per-subset counts, unknown costs, failures, expected versus realised costs, threshold fallbacks, bootstrap seed/status/counts and scope limitations. Preserve the complete raw attempt ledger separately from the terminal table. Do not put credentials or billing-account identifiers in published artifacts.

`analysis.py` provides replay, the observable cascade gate, fixed/uniform/pairwise-mixture/oracle references and paired cluster intervals. It accepts already-defined policies. `scripts/check_empirical_method.py` exercises fitting, route planning and analysis using generated fixtures only. Provider adapters, a reconciled real terminal table and a reviewed freeze remain necessary before any experimental claim.

The separate treatment of a routing policy and its retrospective frontier follows the evaluation problem studied in [RouterBench](https://arxiv.org/abs/2403.12031). The exact definitions above are this project's proposed analysis choices, not a reproduction of that paper.
