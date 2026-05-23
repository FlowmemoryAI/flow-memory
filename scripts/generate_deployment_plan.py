from __future__ import annotations

import argparse
import json
from pathlib import Path

from flow_memory.web3 import generate_deployment_plan


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Flow Memory Base Sepolia dry-run deployment plan")
    parser.add_argument("--out", type=Path, help="Optional JSON output path")
    args = parser.parse_args()
    plan = generate_deployment_plan()
    text = json.dumps(plan, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8", newline="\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
