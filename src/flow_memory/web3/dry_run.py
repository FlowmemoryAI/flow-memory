"""Base Sepolia dry-run helpers."""

from flow_memory.web3.deployment_plan import generate_deployment_plan
from flow_memory.web3.transaction_builder import build_dry_run_transaction


def base_sepolia_dry_run():
    plan = generate_deployment_plan("base-sepolia")
    tx = build_dry_run_transaction("0x0000000000000000000000000000000000000000")
    return {"plan": plan, "transaction": tx}
