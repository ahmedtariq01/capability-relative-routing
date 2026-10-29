"""Check recorded execution prerequisites without running models or sending messages."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from crr.readiness import STAGES, check_readiness


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--stage", choices=STAGES, default="specification")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        report = check_readiness(json.loads(args.config.read_text()), args.root)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Invalid readiness configuration: {exc}\n")
    print(json.dumps(report, indent=2, allow_nan=False))
    raise SystemExit(0 if report["stages"][args.stage]["local_prerequisites_satisfied"] else 1)


if __name__ == "__main__":
    main()
