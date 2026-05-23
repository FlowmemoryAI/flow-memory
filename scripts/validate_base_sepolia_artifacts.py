from __future__ import annotations

import argparse
import json
from pathlib import Path

from flow_memory.web3.verification import validate_base_sepolia_artifacts


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Base Sepolia dry-run artifact set")
    parser.add_argument("--dir", type=Path, default=Path("deployments/base-sepolia"))
    args = parser.parse_args()
    report = validate_base_sepolia_artifacts(args.dir)
    print(json.dumps(report.as_record(), indent=2, sort_keys=True))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
