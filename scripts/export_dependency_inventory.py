"""Export Flow Memory dependency inventory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from flow_memory.release import build_dependency_inventory, write_dependency_inventory


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Flow Memory dependency inventory JSON")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root")
    parser.add_argument("--out", type=Path, help="Write inventory JSON to this path")
    args = parser.parse_args()

    if args.out:
        output = write_dependency_inventory(args.root, args.out)
        print(json.dumps({"ok": True, "inventory": str(output)}, indent=2, sort_keys=True))
    else:
        print(json.dumps(build_dependency_inventory(args.root).as_record(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
