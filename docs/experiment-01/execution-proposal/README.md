# Model configuration and cost proposal

Research date: 29 October 2026. Prepared for Ahmed Tariq and Leo Guinan. Operational update: 30 October 2026.

The public documentation supports the four candidates below. Retain the existing method, 0.80 primary target, 60/120 split and official task preparation. This package proposes the remaining execution choices. Account access, deployed engine behavior, funding and execution approval remain open.

## Candidate roster

| Slot | OpenRouter request ID | Preferred standard endpoint | Input / output USD per million tokens |
| --- | --- | --- | ---: |
| 1 | `google/gemini-3.5-flash-lite` | `google-ai-studio` | 0.30 / 2.50 |
| 2 | `anthropic/claude-haiku-5.5` | `anthropic` | 0.10 / 0.50 |
| 3 | `openai/gpt-5.6-luna` | `openai` | 0.20 / 1.20 |
| 4 | `anthropic/claude-sonnet-5.5` | `anthropic` | 2.00 / 10.00 |

Sources: [Google pricing](https://ai.google.dev/gemini-api/docs/pricing), [Haiku 5.5](https://platform.claude.com/docs/en/models/haiku-5-5/overview), [GPT-5.6 Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna), [Sonnet 5.5](https://platform.claude.com/docs/en/models/sonnet-5-5/overview) and the [OpenRouter catalogue](https://openrouter.ai/api/v1/models). The saved public snapshot includes endpoint prices, parameter lists and canonical identities.

This uses Leo's later Gemini 3.5 suggestion and retains the other provisional candidates. Haiku currently costs less per token than Gemini, so determine the cheap/strong pair from development observations and total costs. Model names and brand tiers cannot establish that ordering or predict this study's accuracy.

Gemini 2.5 Flash-Lite has prior-use access restrictions. Keep it as an optional, access-dependent alternative. GPT-6 Luna is another documented alternative at $0.10/$0.50, but adopting it needs an explicit roster decision. Do not silently substitute it for GPT-5.6 Luna. The initial roster offers three providers and distinct prices. Development data must establish whether their errors create useful routing opportunity.

The OpenRouter API ID differs from its permanent catalogue `canonical_slug`. Preserve both. A canonical date in metadata does not prove that the same string accepts a completion request or that all serving components stay immutable. Anthropic's direct dateless IDs identify fixed snapshots. Google's stable model guarantee is weaker. Preserve requested and returned identities, endpoint, tier, source revision and run dates.

## Proposed generation and collection settings

Use supported `low` reasoning effort and an 8,192-token total generation cap for each configured model. Through the captured ScreamingFace OpenRouter contract, the proposed scalar parameter map is `{"max_tokens":8192,"reasoning.effort":"low"}`. Confirm the actual emitted request before relying on this spelling. The gateway constructs the nested reasoning object upstream. Avoid sending both reasoning spellings.

Low effort maps to Gemini thinking level low, Claude adaptive thinking with output effort low, and OpenAI low reasoning. Equal effort labels and caps do not equalize computation. The study compares these four configured systems. Retain the official visible reasoning instruction, multiple-choice format and scorer. Do not replace the task with a short answer-only prompt. The proposed cap may truncate difficult answers; the development smoke must check this before collection.

Omit temperature, top-p and top-k. Gemini 3.5 ignores these controls, Sonnet rejects them, and Haiku instructs omission. Public OpenRouter endpoint metadata also omits sampling controls for GPT and Claude. Omit provider seeds rather than claiming cross-provider determinism. Preserve the separate declared split, choice-shuffle, fit and bootstrap seeds. Sources: [Google migration behavior](https://ai.google.dev/gemini-api/docs/whats-new-gemini-3.6), [Claude effort](https://platform.claude.com/docs/en/build-with-claude/effort), [OpenAI reasoning](https://developers.openai.com/api/docs/guides/reasoning).

Thinking consumes the total output budget and output charges. An empty visible answer can still incur a bill. Never add reasoning tokens again when completion usage already includes them. Record finish reason, truncation, malformed answers, refusals and every failed attempt. Public parameter support does not prove actual engine translation. Source: [OpenRouter reasoning accounting](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens).

Retain initial concurrency one and predeclare the interleaved model-call schedule. Permit at most three total attempts for transient transport/rate errors, matching the existing protocol proposal. Let one gateway layer own retries and disable outer automatic retries. The captured gateway defaults are 600 seconds active execution, 0.5-second base backoff, eight-second maximum backoff, 30 seconds total wait and 0.25 seconds jitter. These are proposed operational values, with queue/client deadlines and actual deployed settings still to verify. Reconcile an ambiguous timed-out attempt before a blind resubmission. Incorrect, abstained, malformed and truncated answers do not receive retries to improve their score.

Honor the provider's `Retry-After`. If that delay exceeds the individual or total waiting allowance, defer or stop the run. Do not shorten the provider's delay to fit the backoff cap.

The model, pricing and budget JSON files remain proposals and have distinct evidence kinds. The active execution-readiness manifest still contains unresolved evidence references. No proposal file closes an execution gate.

## Engine integration finding

The preferred path is native selected-case execution on the frozen stock LAB-Bench. The feature is under development. The original dataset IDs and split remain unchanged; verify the delivered selector and source revision before execution. A separate registered benchmark is unnecessary when native selection preserves the task. Selected-case per-question reports suffice for this study, with no selected-case public leaderboard submission. This design direction does not resolve the independent provider/settings controls below.

Current public ScreamingFace source at `a7e5d85770d775ab05c5fef4b43d61bd2d5a2d1d` explicitly rejects OpenRouter's raw `provider`, `only`, `order` and `allow_fallbacks` controls. It strips `extra_body`. Its five permitted price/privacy controls apply to direct gateway chat and do not currently travel through URL4. A raw OpenRouter fixed-endpoint example therefore cannot serve as a working ScreamingFace configuration. Source: [pinned gateway routing contract](https://github.com/ScreamingFace/screamingface/blob/a7e5d85770d775ab05c5fef4b43d61bd2d5a2d1d/apps/aigateway/docs/openrouter-routing-controls.md).

Exact native-provider routes are an option to investigate within the shared engine. They do not automatically resolve the settings issue: the captured direct OpenAI gateway contract exposes only `max_tokens`, and native providers have different parameter contracts. Confirm the actual route catalogue, parameter contract, API-key path and outbound payload. A scoped gateway/URL4 extension is the alternative if the existing engine cannot preserve the agreed endpoint, tier and reasoning settings. Preserve ScreamingFace's preparation, scorer and reproducibility infrastructure in either case.

Record the agreed data-collection/ZDR policy, current account guardrails and engine/cache/log retention before freezing the route. Strict ZDR can exclude the preferred first-party endpoints, so it may require an agreed endpoint change and revised price. Training restrictions, provider retention and engine caching describe different policies. Source: [OpenRouter ZDR routing](https://openrouter.ai/docs/guides/features/zdr). This proposal leaves those choices unresolved.

Khoa already received the variant-registration question. Before a run, the integration needs answers to these concrete points:

1. Which delivered native-selection path gives the local and hosted engines the same original-ID mapping, frozen source/preparation and selected denominator?
2. Which path carries the exact endpoint, standard tier and reasoning settings without silent fallback or dropped fields?
3. How can fresh collection avoid engine response reuse while preserving capture and per-attempt provider/tier/usage receipts?

`Model.prompt` has an SDK default distinct from benchmark formatting. The backend comparison must reject an extra SDK prefix or changed instruction as well as changed IDs, choices, targets, categories and scorer behavior. Repository source support does not establish the deployed engine revision. Source: [pinned SDK model contract](https://github.com/ScreamingFace/screamingface/blob/a7e5d85770d775ab05c5fef4b43d61bd2d5a2d1d/public-docs/src/pages/sf-client/api/ModelsCatalogPage.vue).

## Prompt audit and budget

The reproducible offline audit reconstructed the pinned official preparation and matched all 60 development prompt hashes against the committed reference. It rendered no held-out prompts and exported no prompt or answer text.

| Scope, per model | Questions | Official content bytes | Local GPT-family content-token estimate |
| --- | ---: | ---: | ---: |
| Smoke | 15 | 52,096 | 16,218 |
| Complete development | 60 | 173,797 | 53,931 |
| Largest development prompt, already in smoke | 1 | 15,560 | 4,755 |

The local tokenizer uses tiktoken 0.14.0's generic GPT-5 mapping to `o200k_base`, with the public encoding bytes hash-verified. It is a content-only estimate. It does not establish exact GPT-5.6 billing, include provider wrappers or describe Gemini/Claude tokenization. Provider-billed input counts remain unknown. A 4,096-token input cap would already be smaller than the largest local estimate, so do not adopt that cap from a generic cost example.

For review, declare a 20,000-token input guard per complete provider request and the 8,192 total generated-token cap. Validate that guard with the actual selected tokenizer/request wrapper. Stop on an oversized task rather than truncate the official input. The table below computes the same conservative allowance for every call. It is a funding scenario, not an expected bill or a verified billing bound.

| Scope | First attempts | Base token cost, one attempt per cell | Base token cost, every cell uses all three attempts |
| --- | ---: | ---: | ---: |
| Smoke | 60 | $2.524896 | $7.574688 |
| Complete development, including reusable smoke | 240 | $10.099584 | $30.298752 |
| Held out, only after artifact lock | 480 | $20.199168 | $60.597504 |
| Complete matrix, including reusable smoke | 720 | $30.298752 | $90.896256 |

Formula: questions per model multiplied by `(20,000 × 2.60 + 8,192 × 14.20) / 1,000,000`. The sums use the four standard input and output prices above. Multiply by three only for the full-retry scenario. Smoke is part of development and must not be counted twice. Uniform routing and cascade replay use the existing matrix and add no provider runs when their independent-prompt conditions hold.

These amounts exclude cache-write/storage premiums, engine/gateway/CPU charges, credit-purchase fees, tax and separately approved reruns or sensitivity repetitions. Any serving-tier or endpoint-price change requires a revised estimate. GPT-5.6 can incur automatic cache-write charges. Regional Claude endpoints may cost more. Haiku's rates rise at the long-context boundary, which the proposed input guard stays below. Sources: [OpenRouter caching](https://openrouter.ai/docs/guides/best-practices/prompt-caching), [service tiers](https://openrouter.ai/docs/guides/features/service-tiers), [Haiku endpoint prices](https://openrouter.ai/api/v1/models/anthropic/claude-haiku-5.5/endpoints).

Retain Leo's earlier $20 smoke ceiling as a proposed discussion cap. Confirm a funded account and approval tied to actual model, price and scope hashes before execution. The earlier suggestion and historical account balance are not a current authorization. Estimate the remaining development and held-out budget from reconciled smoke usage before seeking their separate approvals. No top-up, paid call or full-study spending approval follows from this document.

Reserve the verified maximum cost of the next attempt, outstanding unresolved charges and known fees before dispatch. Pause when those would exceed the approved cap or when a required bill, identity or route remains unresolved. A provider unit-price filter does not cap total spending.

## Cost boundary and remaining decisions

Keep the actual all-model collection bill, replayed selected-policy inference cost and frozen-price comparison separate. Charge every selected retry/failure. Normalize provider input/cache counters explicitly because native usage fields differ. Preserve unknown costs. The generation record can reconcile served provider, tier and cost later; it requires authorized account access, which this research did not use. Source: [OpenRouter usage accounting](https://openrouter.ai/docs/cookbook/administration/usage-accounting).

Oracle opportunity remains an inference-only retrospective comparison. Deployable CRR includes feature extraction, prediction, selection and actual dispatch. Setup, fitting and calibration stay separate without an agreed amortization horizon. The existing synthetic timing excludes the real backend dispatch and cannot settle total routing cost.

As a concrete positive CPU-price proposal, AWS currently publishes $0.000011244 per vCPU-second for Linux/x86 Fargate in US East (N. Virginia). This can serve as a declared nominal comparison reference if Leo agrees. It is not the cost of our Mac, a deployment plan or proof that Mac timings transfer to cloud hardware. Record runtime and memory/minimum-billing/engine costs, and measure the real adapter before approving the final full-cost model. Source: [AWS Fargate pricing](https://aws.amazon.com/fargate/pricing/).

Agree the route/settings and funding proposal, obtain the actual selected-ID engine export and pass equivalence, then run only development smoke. Reconcile receipts, finish development, fit using development only, and hash-lock the fitted method, policies, route table and analysis before any held-out outcomes. Public documentation does not establish model performance, novelty, grant access, authorship or a publication result.

## Files and provenance

- [Model/settings proposal](models.proposal.json)
- [Dated price and cost-boundary proposal](pricing.proposal.json)
- [Reproducible budget scenarios](budget-scenarios.json)
- [Source and approved-file hashes](source-evidence.json)

The [public model/endpoint snapshot](evidence/public-model-endpoints.json) and [development prompt audit](evidence/development-prompt-audit.json) travel with this proposal. Local filesystem paths in the audit have been reduced to source basenames. Run `python3 scripts/check_execution_proposal.py` to check prices, budget arithmetic, public evidence bindings and approved specification hashes without network or model calls. `scripts/audit_development_prompts.py` can reproduce the development content audit with the declared pinned dependencies and local source parquet files. Pass `--local-tokenizer-model gpt-5.6-luna` only when permitting the hash-verified public BPE download. Full dated source captures remain in the private project audit. The approved method/analysis and active execution evidence remain unchanged.
