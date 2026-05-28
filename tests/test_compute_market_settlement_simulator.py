from __future__ import annotations

from flow_memory.compute_market.models import ComputeQuote
from flow_memory.compute_market.payment import build_payment_plan, simulate_settlement
from flow_memory.compute_market.settlement_simulator import LocalTestnetSettlementSimulator, simulate_testnet_settlement


def _quote(
    mode: str,
    *,
    network: str,
    asset: str,
    settlement_options: tuple[str, ...] | None = None,
) -> ComputeQuote:
    return ComputeQuote(
        quote_id=f"quote-{mode}",
        provider_id="provider-testnet",
        provider_or_route="provider-testnet-recipient",
        provider_type="gpu",
        route_id=f"route-{mode}",
        market_type="marketplace",
        network=network,
        payment_asset=asset,
        unit_type="gpu_minute",
        unit_price=0.09,
        estimated_units=2,
        estimated_total_cost=0.18,
        settlement_mode=mode,
        settlement_options=(mode,) if settlement_options is None else settlement_options,
    )


def test_solana_testnet_harness_never_moves_funds_or_broadcasts() -> None:
    quote = _quote("solana_usdc_dry_run", network="solana", asset="USDC")

    simulation = LocalTestnetSettlementSimulator().simulate(quote, mode="solana_usdc_dry_run", amount=0.18).as_record()
    payload = simulation["payload"]

    assert simulation["dry_run_only"] is True
    assert simulation["funds_moved"] is False
    assert simulation["broadcast_allowed"] is False
    assert simulation["private_key_required"] is False
    assert payload["harness"] == "local_solana_testnet"
    assert payload["simulated_signature"]
    assert payload["preflight_status"] == "ok"
    assert payload["balance_snapshot"]["delta"] == 0.0


def test_base_sepolia_testnet_harness_builds_non_broadcast_user_operation() -> None:
    quote = _quote("base_sepolia_erc4337_dry_run", network="base-sepolia", asset="ETH")

    simulation = simulate_testnet_settlement(quote, mode="base_sepolia_erc4337_dry_run", amount=0.18)
    payload = simulation["payload"]

    assert simulation["dry_run_only"] is True
    assert simulation["funds_moved"] is False
    assert simulation["broadcast_allowed"] is False
    assert payload["harness"] == "local_base_sepolia_erc4337"
    assert payload["chain_id"] == 84532
    assert payload["entry_point"].startswith("0x")
    assert payload["simulated_gas_estimate"] > 0
    assert payload["user_operation"]["signature"] == "0x"
    assert payload["user_operation"]["dry_run_only"] is True


def test_payment_plan_and_settlement_intent_include_testnet_simulation_artifact() -> None:
    quote = _quote("solana_usdc_dry_run", network="solana", asset="USDC")

    plan = build_payment_plan(quote)
    settlement = simulate_settlement(quote, plan)
    payment_payload = plan.payment_intents[0].payload
    simulation = settlement.transaction_intent["testnet_simulation"]

    assert plan.dry_run_only is True
    assert plan.payment_intents[0].funds_moved is False
    assert payment_payload["harness"] == "local_solana_testnet"
    assert settlement.dry_run_only is True
    assert settlement.funds_moved is False
    assert settlement.broadcast_allowed is False
    assert simulation["payload"]["simulated_blockhash"] == payment_payload["simulated_blockhash"]


def test_generic_settlement_fallback_preserves_no_custody_invariants() -> None:
    quote = _quote("provider_custom_dry_run", network="offchain", asset="CREDITS", settlement_options=())

    plan = build_payment_plan(quote)
    settlement = simulate_settlement(quote, plan)
    simulation = settlement.transaction_intent["testnet_simulation"]
    payload = simulation["payload"]

    assert plan.selected_rail == "generic"
    assert settlement.settlement_mode == "provider_custom_dry_run"
    assert settlement.dry_run_only is True
    assert settlement.funds_moved is False
    assert settlement.broadcast_allowed is False
    assert settlement.private_key_required is False
    assert simulation["dry_run_only"] is True
    assert simulation["funds_moved"] is False
    assert simulation["broadcast_allowed"] is False
    assert simulation["private_key_required"] is False
    assert payload["harness"] == "local_generic_dry_run"
    assert payload["provider_id"] == "provider-testnet"
    assert payload["route_id"] == "route-provider_custom_dry_run"
    assert plan.payment_intents[0].payload["generic_payment_intent"] is True
