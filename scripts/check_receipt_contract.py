"""Exercise the receipt schema on synthetic valid and invalid records."""
from pathlib import Path
import copy
import json


def main() -> None:
    from jsonschema import Draft202012Validator, FormatChecker
    root = Path(__file__).resolve().parents[1] / "docs/experiment-01"
    schema = json.loads((root / "receipt.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    example = json.loads((root / "receipt.synthetic.example.json").read_text())
    validator.validate(example)
    checks = {"unknown_billing_preserved": True}
    mutations = [
        ("unknown_bill_needs_reason", lambda r: r["cost"].update(missing_reason=None)),
        ("zero_bill_needs_source", lambda r: r["cost"].update(billed_usd=0, source=None)),
        ("negative_bill_rejected", lambda r: r["cost"].update(billed_usd=-1, source="synthetic")),
        ("estimate_needs_price_snapshot", lambda r: r["cost"].update(estimated_usd=1, source="synthetic")),
        ("retry_needs_previous_attempt", lambda r: r.update(attempt_index=2)),
        ("negative_token_count_rejected", lambda r: r["usage"].update(input_tokens=-1)),
        ("undeclared_credential_field_rejected", lambda r: r.update(api_key="synthetic-placeholder")),
    ]
    for name, mutate in mutations:
        row = copy.deepcopy(example)
        mutate(row)
        if not list(validator.iter_errors(row)):
            raise AssertionError(f"Invalid receipt accepted: {name}")
        checks[name] = True
    zero = copy.deepcopy(example)
    zero["cost"].update(billed_usd=0, source="synthetic verified zero", missing_reason=None)
    validator.validate(zero)
    checks["known_zero_with_source_accepted"] = True
    print(json.dumps({"scope": "synthetic schema checks only", "passed": len(checks), "checks": checks}, indent=2))


if __name__ == "__main__":
    main()
