# Experiment 01 review package

Start with [the protocol](PROTOCOL.md), then [the decisions that need review](DECISIONS.md). The [compatibility check](SCREAMINGFACE-COMPATIBILITY.md) answers Leo's source-level questions. [Related work](RELATED-WORK.md) covers overlapping methods and Reddit's practical cautions. [Receipts](RECEIPTS.md) defines the record we need from any backend.

`manifest.draft.json` contains 180 original IDs, including 60 development, 120 held out and 15 smoke questions drawn from development. The selection is a proposal for review. Model IDs, settings, method details and execution prerequisites remain open. The scripts make no provider calls.

## Offline checks

From the repository root:

```sh
python3 -m unittest discover -s tests -v
python3 verify.py
python3 scripts/validate_lab_bench_protocol.py docs/experiment-01/manifest.draft.json
```

The following check must currently return a nonzero status and list unresolved decisions:

```sh
python3 scripts/validate_lab_bench_protocol.py docs/experiment-01/manifest.draft.json --require-frozen
```

It checks recorded prerequisites, not the authenticity of approvals or engine behaviour.

The feature branch's GitHub Actions workflow runs the unit tests, synthetic routing fixture, draft-manifest validator and receipt-schema cases. It uses no provider credentials and makes no model calls. A green check confirms those offline checks only. It does not mean the experiment has passed its freeze requirements.

Install `requirements-checks.txt` to run the same receipt checks locally:

```sh
python3 -m pip install -r requirements-checks.txt
python3 scripts/check_receipt_contract.py
```

## Rebuilding the proposed selection

Download the three parquet files from the exact URLs recorded in `manifest.draft.json`. Keep them outside the repository as `LitQA2_train-00000-of-00001.parquet`, `ProtocolQA_train-00000-of-00001.parquet` and `SeqQA_train-00000-of-00001.parquet`. The builder refuses mismatched SHA-256 values. The dataset licence is CC BY-SA 4.0. Keep its attribution and canaries with any redistributed material.

```sh
uv run --no-project --with pyarrow==26.0.0 python scripts/build_lab_bench_manifest.py \
  --data-dir /absolute/path/to/source-files \
  --output /absolute/path/to/rebuilt-manifest.json
```

Selection sorts IDs by SHA-256 of the declared salt, subset and ID. LitQA2/ProtocolQA take 20 development items first, then 40 held-out items excluding development source groups. SeqQA takes four from each of its 15 subtasks, with one or two development items per subtask. The salt orders which five subtasks receive the extra development item. Each subset's first five development IDs under the same ordering form its smoke set.

This is a stratified, source-separated sample, not a uniform sample from all LAB-Bench tasks. Exact source metadata is incomplete. The selected sample contains no duplicate full-input hashes or recorded source group across the split. Repeated question wording alone is not a duplicate when context/options differ.

## Upstream preparation and mock scoring

```sh
uv run --no-project --with inspect-ai==0.3.263 --with inspect-evals==0.20.0 \
  --with datasets==5.0.1 --with pyarrow==26.0.0 \
  python scripts/check_lab_bench_tasks.py \
  --data-dir /absolute/path/to/source-files \
  --manifest docs/experiment-01/manifest.draft.json \
  --output-dir /absolute/path/to/check-output
```

This uses local parquet input, the pinned upstream sample mappers and a `mockllm/model` fixture. It hashes prepared input and choice order without exporting answer keys. It does not start ScreamingFace or validate hosted access. Preserve the whole-task shuffle before filtering.

The 25 October check prepared all 907 source rows and selected 180. Filtering first changed choice order in 58/60 LitQA2, 60/60 ProtocolQA and 59/60 SeqQA items. Correct, incorrect, abstained and malformed fixture responses scored C, I, N and I respectively. See `validation-summary.json` for the saved check scope.

The optional receipt check uses `jsonschema==4.26.0`:

```sh
uv run --no-project --with jsonschema==4.26.0 python scripts/check_receipt_contract.py
```

No empirical model result, official engine compatibility, cost saving or paper contribution follows from these offline checks.
