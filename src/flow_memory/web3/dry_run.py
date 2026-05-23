"""Base Sepolia dry-run helpers."""

from __future__ import annotations

from typing import Mapping

from flow_memory.web3.deployment_plan import CONTRACTS, generate_deployment_plan
from flow_memory.web3.transaction_builder import build_dry_run_transaction


def dry_run_transactions() -> Mapping[str, object]:
    transactions = tuple(
        {
            "contract": name,
            **build_dry_run_transaction(
                "0x0000000000000000000000000000000000000000",
                data="0x" + (index.to_bytes(2, "big").hex()),
                value=0,
                chain_id=84532,
            ),
        }
        for index, name in enumerate(CONTRACTS, start=1)
    )
    return {"chain": "base-sepolia", "chain_id": 84532, "transactions": transactions}


def base_sepolia_dry_run() -> Mapping[str, object]:
    return {"plan": generate_deployment_plan("base-sepolia"), "transactions": dry_run_transactions()}
