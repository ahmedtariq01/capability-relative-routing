# Decisions before execution

Leo's 26 October review supports the protocol foundation, development-calibrated category profiles, a small regularized feature estimator and separate oracle/incremental comparisons. The implementation now supplies a concrete proposal. These remaining choices need review before their relevant stage.

| Decision | Prepared proposal | Needed before |
| --- | --- | --- |
| Numerical method | Beta(1,1) category profiles, six visible features, within-category centering, ridge 1, five source-group folds and no extra calibrator or routing LLM | Development collection and method review |
| Policy selection | 0.80 primary target, 0.50/0.60/0.70/0.90 secondary targets, threshold steps of 0.05, minimum out-of-fold cost among eligible candidates | Method freeze |
| Backend selection | Prefer native frozen-ID selection if Khoa confirms it. Otherwise use the versioned ScreamingFace variant with official preparation, formatting and scorer | Engine smoke |
| Hosted access | Treat grant/engine access as unavailable until confirmed. Continue local preparation. | Hosted run |
| Dataset selection | Review the deterministic ID manifest, source-overlap checks and balanced SeqQA subtask coverage. | First development call |
| Model roster | Four slots, exact model IDs/settings/provider routes pending. Do not silently convert conversational names into API versions. | Cost estimate and smoke |
| Quality claim | Paired source-cluster intervals and exploratory zero-loss check. No confirmatory non-inferiority claim without a justified margin and suitable design | Analysis freeze |
| Cascade | Development-selected cheap/strong pair, escalate on abstention, malformed output or terminal failure. Use the original independent strong-model prompt and charge all stages | Method freeze |
| Controls | Individual fixed models in the primary oracle reference, mixtures secondary. Fine subtask lookup excluded from v0 | Method freeze |
| Research contribution | Compare explicitly with protocol routing on LAB-Bench and capability-based model routing. Test whether CRR predicts useful within-category differences. | Paper framing |
| Spend | Price the actual frozen settings and agree a ceiling after access is confirmed. | Any provider call |
| Cost records | Reconcile all attempts and freeze prices. Measure routing CPU time and declare a positive primary CPU-dollar rate | Cost fit and final analysis |
| Real fit | Complete development only, preserve obsolete smoke costs, fit profiles and commit the fit hash and selected policies | Held-out collection |

No personal-information question for Ahmed blocks this deliverable. Leo reviews the numerical method and analysis choices. Khoa/backend checks and verified provider access resolve execution dependencies. Ahmed decides the spending limit once there is a concrete roster and cost estimate.

## Suggested order of discussion

Review the concrete method and analysis extension, then resolve model access/settings and the supported selection mechanism. The source pins, original IDs, 60/120 split and 15 development-only smoke questions remain unchanged. Engine integration, real fitting, spending approval and the final freeze remain separate stages.

This branch remains a review contribution. It does not establish a grant, allocate authorship or produce empirical findings.
