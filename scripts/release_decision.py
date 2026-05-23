"""Print a Flow Memory release go/no-go decision."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from flow_memory.release import decide_release_readiness


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Flow Memory release readiness")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root")
    parser.add_argument("--target", choices=("local", "testnet", "production"), default="local")
    args = parser.parse_args()

    decision = decide_release_readiness(args.root, target=args.target)
    print(json.dumps(decision.as_record(), indent=2, sort_keys=True))
    return 0 if decision.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
