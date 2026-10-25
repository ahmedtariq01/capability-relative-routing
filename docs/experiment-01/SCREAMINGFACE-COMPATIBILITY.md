# ScreamingFace capability check

Checked 25 October 2026 at source commit `3f2b3a6efacf9b9b4604de49f49b69130b36a847`. CRR base: `c713f2ab1df4d934a444e2225767271a54e876a1`.

## What the source establishes

| Subset | Board | Cases | Source revision |
| --- | --- | ---: | --- |
| LitQA2 | `inspect-lab_bench_litqa` | 199 | `109142a4408d3f4b` |
| ProtocolQA | `inspect-lab_bench_protocolqa` | 108 | `236b15e7b2c90e9b` |
| SeqQA | `inspect-lab_bench_seqqa` | 600 | `48e1368633436c5a` |

The engine's optional Inspect integration registers all three. The declarations use dataset revision `5c77cec648430f30611808808861eb86f81d5eaa`, row/choice seeds 7, `inspect-evals==0.20.0` and `inspect-ai==0.3.263`.

Sources: [engine and Inspect integration](https://github.com/ScreamingFace/screamingface/tree/3f2b3a6efacf9b9b4604de49f49b69130b36a847/apps/screamingface-engine), [task declarations and digests](https://github.com/ScreamingFace/screamingface/blob/3f2b3a6efacf9b9b4604de49f49b69130b36a847/apps/screamingface-engine/src/screamingface_engine_inspect/prepare.py), [pinned upstream task](https://github.com/UKGovernmentBEIS/inspect_evals/blob/v0.20.0/src/inspect_evals/lab_bench/lab_bench.py).

The inspected standard SDK and REST evaluation path accept `limit`. Imported-board construction passes a prefix slice `(0, selected_case_count)` into the evaluation protocol. That is a prefix of the prepared serving order. It does not select arbitrary original question IDs. `answer_seed` is a model-generation control and does not define a data split.

The SDK also exposes lower-level protocol interfaces. This review does not establish that every possible custom protocol forbids arbitrary IDs. It establishes a gap in the standard path we inspected. A custom path still needs provenance, scorer and aggregate-equivalence checks.

## What remains unverified

The public catalogue request to `https://fusion.screamingface.ai/v1/benchmarks` returned HTTP 403 without credentials. We did not bypass it. This proves neither absence of LAB-Bench nor hosted grant access. The endpoint is a public documentation candidate, not a verified endpoint assigned to this project.

The local task and data checks do not prove hosted installation, local engine deployment, question-selection support in a deployed version, or end-to-end scoring equivalence. Keep those separate from source support.

## Proposed route for review

Prepare a **versioned selected-ID benchmark variant within ScreamingFace**, retaining the upstream task, solver and scorer. Preserve the whole-task choice permutation before filtering. Keep original IDs, canonical source case IDs, variant case IDs and all content hashes in an explicit mapping. Verify selected cases and aggregate denominators with mock outcomes before any model call.

Use separate, identifiable development and held-out variants. Their revisions must include the selection and configuration. A 60-item subset must not reuse the full canonical board identity. Keep the eventual hosted publication path compatible with the shared infrastructure.

An engine-level ID selector is the alternative. It requires changes across the API, protocol construction, cache identity, aggregation and receipts. It is larger than adding a Python filter in the client. No extension or variant has yet been implemented or accepted by maintainers.

## Acceptance checks before a smoke test

1. Local and target hosted catalogues identify the intended board/variant and exact revision.
2. Requested original IDs match returned original IDs one to one. A non-prefix selection works. Unknown, duplicate or conflicting IDs fail explicitly.
3. Full-task and selected-task preparation produce identical prompts, choice order and target mappings for each selected item.
4. Mock correct, wrong, abstained and malformed answers give identical upstream and engine results. Aggregation uses the selected denominator and includes failures.
5. Cache identity includes variant revision, model/configuration and selection. A development response cannot satisfy a held-out request by mistake.
6. Receipts expose effective provider/model identity, attempt status and usage. Preserve nullable values where the backend cannot provide a field.

These checks define the work after review. A local manifest-validation pass is not evidence that they have passed.
