from __future__ import annotations

import argparse
import json
from pathlib import Path

from flow_memory.web3 import base_sepolia_dry_run


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Flow Memory Base Sepolia dry-run transactions")
    parser.add_argument("--out", type=Path, help="Optional JSON output path")
    args = parser.parse_args()
    report = base_sepolia_dry_run()
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(report["transactions"], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
