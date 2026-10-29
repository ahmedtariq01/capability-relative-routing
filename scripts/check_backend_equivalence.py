"""Compare official and candidate development mock exports; never run models."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from crr.backend_equivalence import compare_exports


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--official", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sources = {name: getattr(args, name).resolve() for name in ("manifest", "official", "candidate")}
    if args.output.resolve() in sources.values():
        parser.error("output must not overwrite an input artifact")
    if args.output.exists():
        parser.error("output already exists; choose a new audit path")
    try:
        raw = {name: path.read_bytes() for name, path in sources.items()}
        result = compare_exports(*(json.loads(raw[name]) for name in ("manifest", "official", "candidate")))
    except (OSError, ValueError) as exc:
        parser.error(f"cannot read valid input artifacts: {exc}")
    result["source_files"] = {name: {"path": str(path), "sha256": hashlib.sha256(raw[name]).hexdigest()}
                              for name, path in sources.items()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as handle:
        handle.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "selected_ids"}, indent=2))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
