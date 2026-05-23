"""Verify Flow Memory chain and contract registry configuration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from flow_memory.web3 import ContractRegistry, chain_by_name, load_registry


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Flow Memory contract configuration")
    parser.add_argument("--registry", type=Path, help="Optional contract registry JSON")
    parser.add_argument("--allow-zero", action="store_true", help="Allow zero addresses for local dry-run manifests")
    parser.add_argument("--partial", action="store_true", help="Allow registries that do not list every required contract")
    args = parser.parse_args()

    chain = chain_by_name("base-sepolia")
    registry = load_registry(args.registry) if args.registry else ContractRegistry()
    validation = registry.validate(allow_zero=args.allow_zero, require_all=not args.partial and args.registry is not None)
    payload = {
        "ok": chain["chain_id"] == 84532 and validation.ok,
        "chain": chain["name"],
        "chain_id": chain["chain_id"],
        "registry": registry.as_record(),
        "validation": validation.as_record(),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
