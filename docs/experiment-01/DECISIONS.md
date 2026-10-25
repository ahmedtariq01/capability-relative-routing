# Decisions for protocol review

The 180-question scope, 60/120 split, development-only smoke and ScreamingFace preference follow Leo's messages. Everything below is a proposal or an unresolved dependency.

| Decision | Prepared proposal | Needed before |
| --- | --- | --- |
| Empirical CRR method | Leo specifies the capability dimensions, task-to-profile mapping and development-only estimator. Compare with the three-category router. | Method freeze and held-out routes |
| Backend selection | A versioned selected-ID variant inside ScreamingFace. Preserve task preparation before filtering. Maintainers confirm supported deployment/publication path. | Engine smoke |
| Hosted access | Treat grant/engine access as unavailable until confirmed. Continue local preparation. | Hosted run |
| Dataset selection | Review the deterministic ID manifest, source-overlap checks and balanced SeqQA subtask coverage. | First development call |
| Model roster | Four slots, exact model IDs/settings/provider routes pending. Do not silently convert conversational names into API versions. | Cost estimate and smoke |
| Quality claim | Exploratory cost/accuracy curves and paired differences. No non-inferiority claim without a margin and suitable design. | Analysis freeze |
| Cascade | Define its observable escalation gate and whether the strong prompt is independent. Charge all stages. | Method freeze |
| Controls | All fixed models, category router, fixed mixtures and oracle. Add a subtask lookup if its metadata is allowed. | Method freeze |
| Research contribution | Compare explicitly with protocol routing on LAB-Bench and capability-based model routing. Test whether CRR predicts useful within-category differences. | Paper framing |
| Spend | Price the actual frozen settings and agree a ceiling after access is confirmed. | Any provider call |

No question for Ahmed currently blocks local preparation. The technical method and engine decisions need Leo's input. Ahmed need only decide the spending limit when there is a concrete model roster and cost estimate.

## Suggested order of discussion

Lead with the source findings and prepared protocol. Ask Leo to review the capability-estimation method and selected-ID variant, then resolve model access/settings. Share the closest prior work as a research-design issue. Avoid asking him to repeat facts already in the repository or his messages.

The local branch is a review package. It does not change upstream source, establish a grant, allocate authorship or produce empirical findings.
