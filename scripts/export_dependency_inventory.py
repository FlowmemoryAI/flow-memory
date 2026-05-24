"""Export Flow Memory dependency inventory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import sys
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.release import (
    build_dependency_inventory,
    validate_dependency_policy,
    write_dependency_inventory,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Flow Memory dependency inventory JSON")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root")
    parser.add_argument("--out", type=Path, help="Write inventory JSON to this path")
    parser.add_argument(
        "--policy",
        action="store_true",
        help="Validate dependency policy instead of exporting manifests",
    )
    args = parser.parse_args()

    if args.policy:
        report = validate_dependency_policy(args.root)
        print(json.dumps(report.as_record(), indent=2, sort_keys=True))
        return 0 if report.ok else 1

    if args.out:
        output = write_dependency_inventory(args.root, args.out)
        print(json.dumps({"ok": True, "inventory": str(output)}, indent=2, sort_keys=True))
    else:
        print(json.dumps(build_dependency_inventory(args.root).as_record(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
