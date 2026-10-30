# Execution preparation after specification approval

Leo approved the v0 method and analysis at `4dae9b5` on 29 October 2026. The [approval record](spec-freeze.json) binds the original files and selection. METHOD.md, ANALYSIS.md and method-plan.json retain those approved bytes. The 0.80 primary target and 60/120 development/held-out split remain fixed.

The approval covers implementation and preparation for development validation. It does not approve provider calls. This package contains no real development collection or held-out evaluation.

## Current operational status

| Requirement | Evidence prepared | Remaining dependency |
| --- | --- | --- |
| Specification freeze | Live GitHub approval and exact document/selection hashes | Complete |
| Backend equivalence | Comparator for original IDs, categories, prepared input, choice order, target mappings, mock scores, selected denominator and cache identity | Validate the delivered native selected-case feature and its frozen original-ID mapping. Obtain and compare an actual candidate-engine export |
| Model and price manifest | Required fields and cross-file checks below | Exact accessible API IDs, snapshots/routes, generation settings, retry policy, timeouts and dated prices |
| Routing overhead | Local category/CRR measurement command and a separately labelled synthetic measurement | Actual adapter dispatch measurement, declared CPU price and remeasurement with the final development fit |
| Spending | Separate scope-bound approval record required | Agree the funded route and exact cap against the actual model/price manifest |
| Development smoke | The 15 assigned development IDs remain fixed | Backend/configuration/cost review and spending approval before any provider call |
| Development receipts and fit | Existing development-only fitter plus evidence checks | Reconcile every attempt, validate 60 by 4 terminal observations, then fit |
| Held-out lock | Checks for final fit, policies, route table, analysis and all supporting hashes | Create and publish the complete precollection lock before collecting or inspecting held-out outcomes |

Leo proposed a $20 initial smoke ceiling on 23 October. That proposal does not identify a funded provider route or authorize this execution package. No amount has been entered as current spending approval. The full experiment budget remains separate.

## Readiness checks

`execution-readiness.json` references evidence by file path and SHA-256 of its bytes. Missing evidence stays `null`. Run:

```sh
python3 scripts/check_execution_readiness.py docs/experiment-01/execution-readiness.json --stage specification
python3 scripts/check_execution_readiness.py docs/experiment-01/execution-readiness.json --stage development_smoke
python3 scripts/check_execution_readiness.py docs/experiment-01/execution-readiness.json --stage development_collection
python3 scripts/check_execution_readiness.py docs/experiment-01/execution-readiness.json --stage held_out
```

Only the specification stage should pass in this revision. Each report includes all stage results. A nonzero exit for an operational stage records unresolved prerequisites. The tool checks local evidence consistency and cannot authenticate approvals, bills, timestamps or external execution. It never authorizes a run.

The initial smoke cannot depend on a final fit that needs development outcomes. The checks therefore distinguish initial execution prerequisites, smoke reconciliation, and the final fitted-method/overhead lock. This ordering does not waive Leo's cost-boundary review before smoke. It also does not establish that the implementation can run providers: these commands only validate files.

The older `validate_lab_bench_protocol.py --require-frozen` remains a structural final-manifest check. Its draft review fields refer to the final execution manifest. Use the separate specification record for Leo's approved method status.

## Backend evidence

The selected-ID comparator consumes official and candidate exports in the format enforced by `crr.backend_equivalence`. Both exports must represent the same frozen development or smoke selection. It rejects a prefix substitution, mismatched category, duplicate IDs, altered choice order, target mapping changes, differing mock scores and inconsistent selected denominators. Synthetic matching exports only test the comparator.

```sh
python3 scripts/check_backend_equivalence.py --help
```

The 29 October pinned upstream check prepared all 907 source rows, preserved the original selection and exported the 60 development cases (20 per category) in [backend/official-development.json](backend/official-development.json). It exercised correct, incorrect, abstained and malformed mock responses, which scored C, I, N and I. No provider took part. The reference hashes the rendered official messages, choice order and target mappings.

A candidate export must come from the actual ScreamingFace selected-case path, whether native selection or the fallback variant. Copying the official export and changing its label would supply no integration evidence. Keep the official preparation before selection, retain the original/scoped case mapping, and include the selection and configuration in the revision and cache identity. Use separate development and held-out identities.

Native selected-case support is the preferred path for the stock task, with the feature still under development. Confirm the delivered original-ID mapping, frozen task/preparation revision and local/hosted engine behavior before execution. Keep the endpoint and access unresolved until confirmed. The existing selected-ID variant remains a fallback proposal. No current evidence establishes end-to-end engine equivalence.

The [30 October model and cost proposal](execution-proposal/README.md) records public API IDs, prices and supported reasoning/output settings. It also identifies an independent gap in exact OpenRouter endpoint/fallback transport. Those choices and a funded smoke limit remain unapproved.

## Model, price and spending records

Record all four slots against exact accessible API identifiers and versions. A conversational model name is not an API configuration. For each slot record the provider route, permitted fallbacks, generation settings including reasoning and output limits, maximum attempts, retryable errors and timeout. Preserve unsupported/default setting behavior explicitly.

The [model](execution-templates/models.draft.json), [price](execution-templates/pricing.draft.json) and [spending](execution-templates/spending.draft.json) templates make those missing decisions concrete. They contain unresolved fields and cannot satisfy readiness. Complete and version new records once the actual route and approval evidence exist.

The price table binds that model manifest and records USD input/output prices, source URL and retrieval time, reasoning/cache billing and failed-attempt billing. Include every attempt in inference cost. Credits affect the actual bill, not the frozen comparative price. Record the approved spending scope and cap against these exact configuration and price hashes. Keep credentials out of every artifact.

Oracle opportunity remains inference-cost-only. Deployable CRR cost adds feature extraction, prediction, selection and dispatch to all selected-model attempts. Collection, calibration, fitting and setup remain separate. No amortization horizon has been declared.

## Local overhead measurement

```sh
python3 scripts/measure_routing_overhead.py --synthetic --output artifacts/generated/local-overhead.synthetic.json
```

[local-overhead.synthetic.json](local-overhead.synthetic.json) summarizes a real local timing measurement using an invented development fixture. It records warm-up, repetitions, environment, source/fit/input hashes and separate category/CRR timings. The category route now skips CRR features it does not use. Regression tests preserve its decisions.

The measurement includes local request-envelope serialization. It excludes backend dispatch, network and provider time. A missing CPU price leaves dollar cost unavailable. Synthetic-fit timing does not establish final fitted-method timing, engine compatibility or model performance. Repeat with the reconciled development fit and the actual adapter before reporting total deployable cost.

## Before held-out collection

Preserve the raw attempt ledger, including obsolete smoke attempts. Reconcile configurations, selected IDs, failures, usage and costs before creating the development terminal bundle. Fit only that development bundle. Save the fit, every selected policy and unavailable target, the outcome-free route table, and the analysis configuration as separate versioned files. The lock must bind all of them and the evidence used to produce them. Record the lock in the research repository before any held-out outcomes exist.

No offline fixture or local readiness pass establishes an empirical CRR improvement or a publication result.
