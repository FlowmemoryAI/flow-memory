"""Dry-run payment and settlement planning for compute routes."""
from __future__ import annotations

from typing import Any, Mapping

from flow_memory.compute_market.models import ComputeQuote, PaymentIntent, PaymentPlan, SettlementIntent


def build_payment_plan(quote: ComputeQuote | None, *, dry_run_required: bool = True) -> PaymentPlan:
    if quote is None:
        return PaymentPlan(
            payment_plan_id="payment-none",
            selected_rail="none",
            payment_intents=(),
            dry_run_only=True,
            warnings=("no selected route; no payment intent generated",),
            next_safe_actions=("adjust policy or provider availability before retrying",),
        )
    amount = float(quote.estimated_total_cost or 0.0)
    mode = _select_settlement_mode(quote)
    intent = _payment_intent_for_mode(quote, mode, amount)
    warnings = [
        "All payment and settlement flows are dry-run only. Flow Memory does not handle private keys, does not move funds, and does not broadcast transactions in this release.",
        "dry-run only; no funds are moved",
        "no private keys are read or required",
        "transaction broadcast is disabled",
    ]
    if dry_run_required and (intent.broadcast_required or intent.broadcast_allowed or not intent.dry_run_only):
        warnings.append("payment policy violation: route requires live broadcast")
    return PaymentPlan(
        payment_plan_id=f"payment-plan-{quote.quote_id}",
        selected_rail=intent.rail,
        payment_intents=(intent,),
        estimated_total_amount=amount,
        payment_asset=quote.payment_asset,
        network=quote.network,
        dry_run_only=True,
        warnings=tuple(warnings),
        next_safe_actions=(
            "inspect rejected route reasons before execution",
            "obtain separate security review before enabling live settlement",
        ),
    )


def simulate_settlement(quote: ComputeQuote | None, payment_plan: PaymentPlan) -> SettlementIntent:
    if quote is None:
        return SettlementIntent(
            settlement_intent_id="settlement-none",
            route_id="",
            provider_id="",
            payment_plan_id=payment_plan.payment_plan_id,
            settlement_mode="none",
            estimated_amount=0.0,
            payment_asset="",
            network="",
            dry_run_only=True,
            status="not_created_no_route",
            broadcast_allowed=False,
            private_key_required=False,
            funds_moved=False,
            warnings=("no route selected; no dry-run settlement intent generated",),
            policy_result="not_created_no_route",
        )
    return SettlementIntent(
        settlement_intent_id=f"settlement-{quote.quote_id}",
        route_id=quote.route_id,
        provider_id=quote.provider_id,
        payment_plan_id=payment_plan.payment_plan_id,
        settlement_mode=_select_settlement_mode(quote),
        estimated_amount=float(quote.estimated_total_cost or 0.0),
        payment_asset=quote.payment_asset,
        network=quote.network,
        dry_run_only=True,
        broadcast_required=False,
        moves_funds=False,
        broadcast_allowed=False,
        private_key_required=False,
        funds_moved=False,
        recipient=quote.provider_or_route,
        transaction_intent={"simulated": True, "route_id": quote.route_id, "provider_id": quote.provider_id},
        warnings=("dry-run settlement simulation only; broadcast is disabled",),
        policy_result="simulated",
        status="simulated",
    )


def _select_settlement_mode(quote: ComputeQuote) -> str:
    for preferred in (
        "no_payment",
        "http_402_dry_run",
        "solana_usdc_dry_run",
        "base_sepolia_erc4337_dry_run",
        "generic_dry_run",
    ):
        if preferred in quote.settlement_options:
            return preferred
    return quote.settlement_mode


def _payment_intent_for_mode(quote: ComputeQuote, mode: str, amount: float) -> PaymentIntent:
    common: dict[str, Any] = {
        "provider_id": quote.provider_id,
        "route_id": quote.route_id,
        "settlement_mode": mode,
        "dry_run_only": True,
        "broadcast_required": False,
        "requires_private_key": False,
        "moves_funds": False,
        "broadcast_allowed": False,
        "private_key_required": False,
        "funds_moved": False,
    }
    if mode == "http_402_dry_run":
        return PaymentIntent(
            payment_intent_id=f"pay-{quote.quote_id}",
            rail="http_402",
            network=quote.network,
            payment_asset=quote.payment_asset,
            estimated_amount=amount,
            command=("agent-wallet", "request", "--dry-run", "--max-amount", f"{amount:.8f}"),
            payload={"http_402_challenge": "simulated", "provider_or_route": quote.provider_or_route},
            **common,
        )
    if mode == "solana_usdc_dry_run":
        return PaymentIntent(
            payment_intent_id=f"pay-{quote.quote_id}",
            rail="solana_usdc",
            network="solana",
            payment_asset=quote.payment_asset,
            estimated_amount=amount,
            payload={"asset_symbol": quote.payment_asset, "amount": amount, "dry_run": True},
            **common,
        )
    if mode == "base_sepolia_erc4337_dry_run":
        user_operation = {
            "sender": "0x0000000000000000000000000000000000000000",
            "nonce": 0,
            "init_code": "0x",
            "call_data": "0x",
            "call_gas_limit": 0,
            "verification_gas_limit": 0,
            "pre_verification_gas": 0,
            "max_fee_per_gas": 0,
            "max_priority_fee_per_gas": 0,
            "paymaster_and_data": "0x",
            "signature": "0x",
            "dry_run_only": True,
        }
        return PaymentIntent(
            payment_intent_id=f"pay-{quote.quote_id}",
            rail="base_sepolia_erc4337",
            network="base-sepolia",
            payment_asset=quote.payment_asset,
            estimated_amount=amount,
            payload={"user_operation": user_operation, "validation_errors": ()},
            **common,
        )
    if mode == "no_payment":
        return PaymentIntent(
            payment_intent_id=f"pay-{quote.quote_id}",
            rail="no_payment",
            network=quote.network,
            payment_asset=quote.payment_asset,
            estimated_amount=0.0,
            payload={"reason": "local route does not require payment"},
            **common,
        )
    return PaymentIntent(
        payment_intent_id=f"pay-{quote.quote_id}",
        rail="generic",
        network=quote.network,
        payment_asset=quote.payment_asset,
        estimated_amount=amount,
        payload={"generic_payment_intent": True, "dry_run": True},
        **common,
    )


def payment_plan_summary(plan: PaymentPlan) -> Mapping[str, object]:
    return {
        "selected_rail": plan.selected_rail,
        "estimated_total_amount": plan.estimated_total_amount,
        "payment_asset": plan.payment_asset,
        "network": plan.network,
        "dry_run_only": plan.dry_run_only,
        "broadcast_required": any(intent.broadcast_required for intent in plan.payment_intents),
        "moves_funds": any(intent.moves_funds for intent in plan.payment_intents),
        "broadcast_allowed": any(intent.broadcast_allowed for intent in plan.payment_intents),
        "private_key_required": any(intent.private_key_required for intent in plan.payment_intents),
        "funds_moved": any(intent.funds_moved for intent in plan.payment_intents),
    }
