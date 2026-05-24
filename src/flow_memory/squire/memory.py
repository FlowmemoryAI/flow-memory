"""Economic memory helpers for Squire-routed agent work."""
from __future__ import annotations

from typing import Mapping

from flow_memory.core.types import new_id
from flow_memory.squire.models import AgentTreasury, EconomicMemoryRecord
from flow_memory.squire.routing import parse_usepod_response_headers


def build_economic_memory_record(
    *,
    goal_id: str | None = None,
    treasury: AgentTreasury | None = None,
    route_mode: str = "usepod-auto",
    model_requested: str = "",
    provider_model_id: str = "",
    headers: Mapping[str, str] | None = None,
    tokens_in: int = 0,
    tokens_out: int = 0,
    price_input_per_million: float = 0.0,
    price_output_per_million: float = 0.0,
    latency_ms: int = 0,
    quality_signal: float = 0.0,
    live_or_roadmap: str = "live",
) -> EconomicMemoryRecord:
    treasury = treasury or AgentTreasury()
    header_meta = parse_usepod_response_headers(headers or {})
    balance_after = header_meta.get("balance_remaining")
    total_cost = _estimated_cost(tokens_in, tokens_out, price_input_per_million, price_output_per_million)
    before = treasury.usdc_balance
    after = float(balance_after) if isinstance(balance_after, (int, float)) else max(0.0, before - total_cost)
    return EconomicMemoryRecord(
        goal_id=goal_id or new_id("squire_goal"),
        wallet_pubkey=treasury.wallet_pubkey,
        treasury_source=_treasury_source(treasury),
        route_mode=route_mode,
        provider_class=str(header_meta.get("provider_class", "unknown")),
        model_requested=model_requested,
        provider_model_id=provider_model_id,
        tokens_in=max(0, int(tokens_in)),
        tokens_out=max(0, int(tokens_out)),
        price_input_per_million=max(0.0, float(price_input_per_million)),
        price_output_per_million=max(0.0, float(price_output_per_million)),
        total_cost=total_cost,
        balance_before=before,
        balance_after=after,
        latency_ms=max(0, int(latency_ms)),
        fallback_used=bool(header_meta.get("fallback_used", False)),
        canary_risk="unknown",
        quality_signal=max(0.0, min(1.0, float(quality_signal))),
        live_or_roadmap=live_or_roadmap,
        tool_mode=route_mode,
        usepod_token_id=treasury.usepod_token_id,
    )


def economic_memory_schema() -> tuple[str, ...]:
    return tuple(EconomicMemoryRecord(goal_id="schema").as_record().keys())


def _estimated_cost(tokens_in: int, tokens_out: int, input_price: float, output_price: float) -> float:
    return round((max(0, tokens_in) / 1_000_000.0 * max(0.0, input_price)) + (max(0, tokens_out) / 1_000_000.0 * max(0.0, output_price)), 8)


def _treasury_source(treasury: AgentTreasury) -> str:
    if treasury.level5_token_present:
        return "level5"
    if treasury.usepod_token_present:
        return "usepod"
    if treasury.wallet_pubkey:
        return "solana_wallet"
    return "none"
