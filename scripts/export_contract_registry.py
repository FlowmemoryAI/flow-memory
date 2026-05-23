from __future__ import annotations

import argparse
import json
from pathlib import Path

from flow_memory.web3.contract_registry import CONTRACTS, ContractRegistry, ZERO_ADDRESS, write_registry


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a dry-run Flow Memory contract registry")
    parser.add_argument("--out", type=Path, default=Path("deployments/base-sepolia/contract-registry.json"))
    parser.add_argument("--placeholder", default=ZERO_ADDRESS, help="Placeholder address to write for every contract")
    args = parser.parse_args()

    registry = ContractRegistry()
    for name in CONTRACTS:
        registry.register(name, args.placeholder)
    output = write_registry(registry, args.out)
    print(json.dumps({"ok": True, "registry": str(output)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
