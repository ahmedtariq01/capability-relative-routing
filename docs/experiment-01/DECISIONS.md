# Decisions before execution

Leo's [27 October review](https://github.com/leo-guinan/capability-relative-routing/pull/1#issuecomment-6445333948) conditionally supports the v0 method. This revision addresses his five points: the fixed 0.80 primary target, distinct cost boundaries, pre-inference category availability and source-group limits, a uniform-routing control, and the single-draw interpretation. Final specification agreement and execution prerequisites remain open.

| Decision | Prepared proposal | Needed before |
| --- | --- | --- |
| Numerical method | Beta(1,1) category profiles, six visible features, within-category centering, ridge 1, five source-group folds and no extra calibrator or routing LLM | Development collection and method review |
| Policy selection | Retain the 0.80 primary target declared on 26 October. An unattainable development target leaves the primary result unavailable. Never promote a secondary target. Retain threshold steps of 0.05 and minimum out-of-fold cost among eligible candidates | Final specification review |
| Input availability | Category comes from the selected LitQA2/ProtocolQA/SeqQA task before inference. Verify backend propagation. Source groups serve split checks, grouped folds and resampling only | Engine smoke |
| Backend selection | Prefer native frozen-ID selection if Khoa confirms it. Otherwise use the versioned ScreamingFace variant with official preparation, formatting and scorer | Engine smoke |
| Hosted access | Treat grant/engine access as unavailable until confirmed. Continue local preparation. | Hosted run |
| Dataset selection | Review the deterministic ID manifest, source-overlap checks and balanced SeqQA subtask coverage. | First development call |
| Model roster | Four slots, exact model IDs/settings/provider routes pending. Do not silently convert conversational names into API versions. | Cost estimate and smoke |
| Quality claim | Paired source-cluster intervals and exploratory zero-loss check. No confirmatory non-inferiority claim without a justified margin and suitable design | Analysis freeze |
| Cascade | Development-selected cheap/strong pair, escalate on abstention, malformed output or terminal failure. Use the original independent strong-model prompt and charge all stages | Method freeze |
| Controls | Individual fixed models in the primary oracle reference. Uniform 0.25 weights across the four slots and pairwise mixtures remain secondary expected controls. Fine subtask lookup excluded from v0 | Final specification review |
| Research contribution | Compare explicitly with protocol routing on LAB-Bench and capability-based model routing. Test whether CRR predicts useful within-category differences. | Paper framing |
| Spend | Price the actual frozen settings and agree a ceiling after access is confirmed. | Any provider call |
| Cost records | Oracle opportunity covers inference cost only. Deployable CRR includes routing and all selected attempts. Reconcile receipts, freeze prices, measure overhead and declare a positive primary CPU-dollar rate. Keep collection/calibration/setup separate without a predeclared amortization horizon | Cost fit and final analysis |
| Interpretation | Single-draw finite-matrix evaluation conditional on provider stochasticity. Optional predeclared development repeats remain separate sensitivity data and cannot change the primary policy | Final specification review |
| Real fit | Complete development only, preserve obsolete smoke costs, fit profiles and commit the fit hash and selected policies | Held-out collection |

No personal-information question for Ahmed blocks this deliverable. Leo reviews the numerical method and analysis choices. Khoa/backend checks and verified provider access resolve execution dependencies. Ahmed decides the spending limit once there is a concrete roster and cost estimate.

## Suggested order of discussion

Review these clarifications, then resolve backend equivalence, model access/settings and the supported selection mechanism. The source pins, original IDs, 60/120 split and 15 development-only smoke questions remain unchanged. After spending approval and the development-only smoke test, complete development collection and fitting. Hash-lock the fitted method, selected policies, route table and analysis artifacts before collecting or inspecting any held-out outcomes.

This branch remains a review contribution. It does not establish a grant, allocate authorship or produce empirical findings.
