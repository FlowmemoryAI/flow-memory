"""Dry-run testnet settlement simulation harness for Compute Market.

The harness intentionally never imports wallet, RPC, or signing libraries. It
produces deterministic simulation envelopes that can be audited by the planner
and API while preserving the production invariant that Flow Memory does not move
funds, read private keys, or broadcast transactions.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Mapping

from flow_memory.compute_market.models import ComputeQuote

_BASE_SEPOLIA_CHAIN_ID = 84532
_BASE_SEPOLIA_ENTRY_POINT = "0x0000000000000000000000000000000000004337"
_SOLANA_TESTNET_CLUSTER = "devnet"
_SOLANA_USDC_TEST_MINT = "So11111111111111111111111111111111111111112"


@dataclass(frozen=True)
class TestnetSettlementSimulation:
    settlement_mode: str
    network: str
    chain_id: int | str
    payload: Mapping[str, Any]
    dry_run_only: bool = True
    broadcast_allowed: bool = False
    private_key_required: bool = False
    funds_moved: bool = False
    status: str = "simulated"

    def as_record(self) -> dict[str, Any]:
        return {
            "settlement_mode": self.settlement_mode,
            "network": self.network,
            "chain_id": self.chain_id,
            "payload": dict(self.payload),
            "dry_run_only": self.dry_run_only,
            "broadcast_allowed": self.broadcast_allowed,
            "private_key_required": self.private_key_required,
            "funds_moved": self.funds_moved,
            "status": self.status,
        }


class LocalTestnetSettlementSimulator:
    """Deterministic Solana/Base testnet simulator with fail-closed safety flags."""

    def simulate(self, quote: ComputeQuote, *, mode: str, amount: float) -> TestnetSettlementSimulation:
        if mode == "solana_usdc_dry_run":
            return self._simulate_solana_usdc(quote, amount=amount)
        if mode == "base_sepolia_erc4337_dry_run":
            return self._simulate_base_sepolia_erc4337(quote, amount=amount)
        return self._simulate_generic(quote, mode=mode, amount=amount)

    def _simulate_solana_usdc(self, quote: ComputeQuote, *, amount: float) -> TestnetSettlementSimulation:
        digest = _simulation_digest("solana", quote, amount)
        payload = {
            "harness": "local_solana_testnet",
            "cluster": _SOLANA_TESTNET_CLUSTER,
            "asset_symbol": quote.payment_asset,
            "asset_mint": _SOLANA_USDC_TEST_MINT,
            "amount": amount,
            "dry_run": True,
            "dry_run_only": True,
            "funds_moved": False,
            "broadcast_allowed": False,
            "private_key_required": False,
            "simulated_blockhash": digest[:32],
            "simulated_signature": f"sim_{digest}",
            "fee_lamports": 5000,
            "preflight_status": "ok",
            "instructions": (
                {
                    "program": "spl-token",
                    "action": "transfer_checked",
                    "mint": _SOLANA_USDC_TEST_MINT,
                    "source": "dry-run-source-token-account",
                    "destination": quote.provider_or_route,
                    "authority": "dry-run-authority",
                    "amount": amount,
                    "decimals": 6,
                },
            ),
            "balance_snapshot": {
                "source_before": amount,
                "source_after": amount,
                "destination_before": 0.0,
                "destination_after": 0.0,
                "delta": 0.0,
            },
        }
        return TestnetSettlementSimulation(
            settlement_mode="solana_usdc_dry_run",
            network="solana",
            chain_id=_SOLANA_TESTNET_CLUSTER,
            payload=payload,
        )

    def _simulate_base_sepolia_erc4337(self, quote: ComputeQuote, *, amount: float) -> TestnetSettlementSimulation:
        digest = _simulation_digest("base-sepolia", quote, amount)
        nonce = int(digest[:8], 16)
        user_operation = {
            "sender": "0x0000000000000000000000000000000000000000",
            "nonce": nonce,
            "init_code": "0x",
            "call_data": f"0x{digest[:64]}",
            "call_gas_limit": 21_000,
            "verification_gas_limit": 100_000,
            "pre_verification_gas": 50_000,
            "max_fee_per_gas": 1_000_000_000,
            "max_priority_fee_per_gas": 100_000_000,
            "paymaster_and_data": "0x",
            "signature": "0x",
            "dry_run_only": True,
        }
        payload = {
            "harness": "local_base_sepolia_erc4337",
            "chain_id": _BASE_SEPOLIA_CHAIN_ID,
            "entry_point": _BASE_SEPOLIA_ENTRY_POINT,
            "asset_symbol": quote.payment_asset,
            "amount": amount,
            "dry_run": True,
            "dry_run_only": True,
            "funds_moved": False,
            "broadcast_allowed": False,
            "private_key_required": False,
            "user_operation": user_operation,
            "user_operation_hash": f"0x{digest}",
            "simulated_gas_estimate": user_operation["call_gas_limit"]
            + user_operation["verification_gas_limit"]
            + user_operation["pre_verification_gas"],
            "validation_errors": (),
        }
        return TestnetSettlementSimulation(
            settlement_mode="base_sepolia_erc4337_dry_run",
            network="base-sepolia",
            chain_id=_BASE_SEPOLIA_CHAIN_ID,
            payload=payload,
        )

    def _simulate_generic(self, quote: ComputeQuote, *, mode: str, amount: float) -> TestnetSettlementSimulation:
        payload = {
            "harness": "local_generic_dry_run",
            "provider_id": quote.provider_id,
            "route_id": quote.route_id,
            "amount": amount,
            "dry_run": True,
            "dry_run_only": True,
            "funds_moved": False,
            "broadcast_allowed": False,
            "private_key_required": False,
        }
        return TestnetSettlementSimulation(
            settlement_mode=mode,
            network=quote.network,
            chain_id=quote.network or "local",
            payload=payload,
        )


def simulate_testnet_settlement(quote: ComputeQuote, *, mode: str, amount: float) -> dict[str, Any]:
    return LocalTestnetSettlementSimulator().simulate(quote, mode=mode, amount=amount).as_record()


def _simulation_digest(prefix: str, quote: ComputeQuote, amount: float) -> str:
    material = "|".join(
        (
            prefix,
            quote.quote_id,
            quote.provider_id,
            quote.route_id,
            quote.provider_or_route,
            quote.payment_asset,
            f"{amount:.8f}",
        )
    )
    return sha256(material.encode("utf-8")).hexdigest()
