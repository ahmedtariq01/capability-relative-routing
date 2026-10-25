# Per-attempt receipt contract

Keep a row for every attempted provider call, including failures and retries. The JSON schema in `receipt.schema.json` defines the record shape. This contract is independent of the eventual backend adapter. It does not claim every field is currently exposed by ScreamingFace.

| Area | Required record |
| --- | --- |
| Identity | Manifest hash, call ID, original item ID, subset/split, model slot, purpose and routing-decision ID |
| Attempts | Attempt index, previous attempt ID, status, terminal error/finish reason |
| Model | Requested ID, effective returned ID/version, provider route and complete settings hash |
| Engine | Instance, version, benchmark/variant revision, engine case ID, run ID, replay/cache status |
| Presentation | Exact request hash, prepared item hash, response hash, artifact paths without credentials |
| Time | UTC start/end, monotonic wall duration, queue/provider/scoring durations when exposed |
| Usage | Input, output, reasoning and cached input tokens with unknowns preserved |
| Money | Billed and estimated USD separately, pricing snapshot hash, source and missing-data reason |
| Outcome | Parsed choice, upstream grade, abstention/refusal, parser status and scorer version |

Join retries to their first attempt and final outcome. A request timeout can have an unknown bill. Reconcile it with provider records where possible. Do not count it as free or erase it on retry. Track attempts for routing and profile generation with the same monetary fields. A terminal outcome table has exactly one row per assigned item/model, even if several attempt records precede it.

All fields are present even when the value is unknown. Null is an explicit absence, never an implicit zero. Known zero dollars needs a billing source. Estimated cost needs a pricing snapshot and token provenance. Do not replace billed amounts with estimated amounts in the same field.

The schema validates types and some dependencies. A schema pass does not prove correct attribution or a complete matrix. Before analysis, additionally check unique call IDs, contiguous retry links, the expected item/model Cartesian product, unchanged configurations, valid split membership, and summed attempt charges. Keep the effective-model mismatch and missing-cost counts in every result bundle.

Engine replay and provider caching are different. Preserve the original execution receipt when replaying a stored outcome. Replay latency cannot represent a fresh call. Counterfactual routing cost references the original call/configuration and records a distinct analysis run ID. It does not add to the collection bill again.

Publish only reviewed artifacts. Keep secrets, authentication headers and billing-account identifiers out of requests and receipts. Preserve public source attribution and applicable data terms when publishing task material.
