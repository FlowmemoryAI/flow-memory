"""/goal squire orchestration logic."""
from __future__ import annotations

import os
import shutil
from typing import Mapping

from flow_memory.core.types import new_id
from flow_memory.squire.docs_sync import docs_sync_plan
from flow_memory.squire.memory import build_economic_memory_record, economic_memory_schema
from flow_memory.squire.models import (
    DEFAULT_LIVE_STACK,
    DEFAULT_ROADMAP_ITEMS,
    AgentTreasury,
    SquireEnvironment,
    SquireMode,
    SquirePlan,
    SquireRoutingPolicy,
)
from flow_memory.squire.provider import build_provider_setup_plan
from flow_memory.squire.routing import default_route_candidates, choose_route
from flow_memory.squire.tool_commerce import build_agent_wallet_payment_plan, mpp_memory_fields


def classify_squire_goal(goal: str) -> tuple[SquireMode, ...]:
    text = goal.lower()
    modes: list[SquireMode] = []
    if any(word in text for word in ("host", "provider", "monetize", "sell", "serve", "gpu", "usepod-agent")):
        modes.append(SquireMode.PROVIDER)
    if any(word in text for word in ("wallet", "fund", "treasury", "budget", "balance", "level5", "self-funded")):
        modes.append(SquireMode.TREASURY)
    if any(word in text for word in ("402", "mpp", "paid api", "agent-wallet", "dns", "tool")):
        modes.append(SquireMode.PAID_TOOL)
    if any(word in text for word in ("tee", "attestation", "futures", "reserved", "staking", "squire redemption", "token redemption", "whitepaper")):
        modes.append(SquireMode.ROADMAP_RESEARCH)
    if any(word in text for word in ("infer", "model", "route", "cheap", "usepod", "openai", "anthropic", "proxy", "llm")):
        modes.append(SquireMode.BUYER)
    if not modes:
        modes.append(SquireMode.BUYER)
    unique = tuple(dict.fromkeys(modes))
    if len(unique) > 1 and SquireMode.HYBRID not in unique:
        return (SquireMode.HYBRID, *unique)
    return unique


def inspect_squire_environment(env: Mapping[str, str] | None = None) -> SquireEnvironment:
    source = dict(os.environ if env is None else env)
    balance = _float(source.get("FLOW_MEMORY_SQUIRE_USDC_BALANCE", "0"))
    wallet = bool(source.get("SOLANA_WALLET_PUBKEY") or source.get("AGENT_WALLET_PUBKEY"))
    return SquireEnvironment(
        has_solana_wallet=wallet,
        has_level5_token=bool(source.get("LEVEL5_API_TOKEN")),
        has_usepod_token=bool(source.get("USEPOD_API_TOKEN")),
        funded_balance=balance > 0.0,
        gpu_available=bool(source.get("CUDA_VISIBLE_DEVICES")) or shutil.which("nvidia-smi") is not None,
        user_budget_usdc=balance,
        preferred_models=tuple(part.strip() for part in source.get("SQUIRE_APPROVED_MODELS", "").split(",") if part.strip()),
        latency_budget_ms=int(_float(source.get("SQUIRE_LATENCY_BUDGET_MS", "0"))),
        secrets_present=tuple(name for name in ("LEVEL5_API_TOKEN", "USEPOD_API_TOKEN", "SOLANA_WALLET_PUBKEY", "AGENT_WALLET_PUBKEY") if source.get(name)),
        constraints={"network_calls_enabled": False, "real_funds_enabled": False},
    )


def build_squire_goal_plan(
    goal: str,
    *,
    environment: SquireEnvironment | None = None,
    treasury: AgentTreasury | None = None,
    routing_policy: SquireRoutingPolicy | None = None,
) -> SquirePlan:
    environment = environment or inspect_squire_environment()
    treasury = treasury or _treasury_from_environment(environment)
    routing_policy = routing_policy or _routing_policy_for(goal, treasury)
    modes = classify_squire_goal(goal)
    selected_route = _selected_route(routing_policy)
    memory_record = build_economic_memory_record(
        goal_id=new_id("squire_goal"),
        treasury=treasury,
        route_mode=routing_policy.route_mode,
        model_requested=(treasury.approved_models[0] if treasury.approved_models else "unspecified"),
        provider_model_id=selected_route.model,
        price_input_per_million=selected_route.input_price_per_million,
        price_output_per_million=selected_route.output_price_per_million,
        latency_ms=selected_route.latency_ms,
        quality_signal=selected_route.quality_score,
    )
    architecture = {
        "treasury_layer": "Level5 for self-funded billing, UsePod token/deposit tracking, Solana wallet/agent-wallet seam",
        "routing_layer": "UsePod register/fund/proxy first; fallback is explicit and logged; direct providers remain separate",
        "tool_commerce_layer": "agent-wallet HTTP 402 / MPP subprocess boundary for paid external APIs",
        "memory_telemetry_layer": "EconomicMemoryRecord captures route, cost, balance, latency, fallback, and quality signal",
        "fallback_behavior": "use centralized fallback only when policy allows it; marketplace-only fails closed",
        "trust_safety_posture": "live: bonds, reputation, canaries; roadmap: TEE, on-chain slashing, futures",
        "provider_path": build_provider_setup_plan(gpu_available=environment.gpu_available, wants_monetization=SquireMode.PROVIDER in modes).as_record(),
        "docs_sync": docs_sync_plan(enabled=False),
    }
    return SquirePlan(
        goal_summary=goal.strip() or "Plan Squire compute routing for an agent goal",
        recommended_operating_mode=tuple(mode.value for mode in modes),
        live_stack_to_use_now=_live_stack_for(modes),
        optional_roadmap_extensions=DEFAULT_ROADMAP_ITEMS,
        system_architecture=architecture,
        required_env_vars_and_secrets=_required_env_vars(modes),
        memory_writes=(memory_record.as_record(), {"schema_fields": economic_memory_schema(), "mpp_fields": mpp_memory_fields()}),
        budget_and_routing_policy={**routing_policy.as_record(), "selected_route": selected_route.as_record()},
        execution_steps=_execution_steps(modes, environment, treasury, routing_policy),
        risks_and_unknowns=_risks(modes, environment),
        success_criteria=_success_criteria(modes),
        environment=environment.as_record(),
    )


def _treasury_from_environment(environment: SquireEnvironment) -> AgentTreasury:
    return AgentTreasury(
        wallet_pubkey="configured" if environment.has_solana_wallet else "",
        custodial_status="self-custody" if environment.has_solana_wallet else "none",
        level5_token_present=environment.has_level5_token,
        usepod_token_present=environment.has_usepod_token,
        usdc_balance=environment.user_budget_usdc,
        max_spend_usdc=environment.user_budget_usdc,
        approved_models=environment.preferred_models,
    )


def _routing_policy_for(goal: str, treasury: AgentTreasury) -> SquireRoutingPolicy:
    text = goal.lower()
    marketplace_only = "marketplace-only" in text or "no fallback" in text
    quality_sensitive = any(word in text for word in ("quality", "frontier", "critical", "high-value"))
    return SquireRoutingPolicy(
        route_mode=treasury.preferred_route_mode or "usepod-auto",
        marketplace_only=marketplace_only,
        allow_centralized_fallback=not marketplace_only,
        quality_sensitive=quality_sensitive,
        max_input_price_per_million=treasury.max_price_input_per_million,
        max_output_price_per_million=treasury.max_price_output_per_million,
    )


def _selected_route(policy: SquireRoutingPolicy):
    try:
        return choose_route(policy, default_route_candidates())
    except ValueError:
        return default_route_candidates()[0]


def _live_stack_for(modes: tuple[SquireMode, ...]) -> tuple[str, ...]:
    stack = ["UsePod proxy/routing", "Flow Memory economic memory"]
    if SquireMode.TREASURY in modes or SquireMode.HYBRID in modes:
        stack.append("Level5 self-funded billing")
    if SquireMode.PAID_TOOL in modes:
        stack.append("agent-wallet HTTP 402 / MPP")
    if SquireMode.PROVIDER in modes:
        stack.append("usepod-agent provider runtime")
    stack.append("UsePod machine-readable docs sync")
    return tuple(dict.fromkeys(stack)) or DEFAULT_LIVE_STACK


def _required_env_vars(modes: tuple[SquireMode, ...]) -> tuple[str, ...]:
    required = ["USEPOD_API_TOKEN or onboarding to create one", "FLOW_MEMORY_SQUIRE_USDC_BALANCE for local budget accounting"]
    if SquireMode.TREASURY in modes or SquireMode.PAID_TOOL in modes:
        required.append("SOLANA_WALLET_PUBKEY or AGENT_WALLET_PUBKEY")
    if SquireMode.TREASURY in modes:
        required.append("LEVEL5_API_TOKEN if Level5 treasury mode is selected")
    if SquireMode.PROVIDER in modes:
        required.extend(("usepod-agent operator identity", "explicit approval before any bond/funding action"))
    return tuple(required)


def _execution_steps(modes: tuple[SquireMode, ...], environment: SquireEnvironment, treasury: AgentTreasury, policy: SquireRoutingPolicy) -> tuple[str, ...]:
    steps = [
        "Create or load AgentTreasury; do not fabricate wallet, token, balance, or deposit state.",
        "If no UsePod token is configured, run the onboarding/register flow outside tests and store only token presence/ID metadata.",
        "Set OpenAI/Anthropic-compatible base URL to UsePod or Level5 proxy rather than rewriting model SDK code.",
        "Apply max spend and per-million input/output price ceilings before each inference call.",
        "Capture X-Balance-Remaining, X-Pod-Route, token usage, latency, fallback flag, and quality signal into EconomicMemoryRecord.",
    ]
    if policy.marketplace_only:
        steps.append("Fail closed if no eligible marketplace/key-relay route exists; do not silently use centralized fallback.")
    if SquireMode.PAID_TOOL in modes:
        plan = build_agent_wallet_payment_plan(service="example-paid-tool", url="https://example.invalid/paid-tool", wallet_pubkey=treasury.wallet_pubkey, max_payment_usdc=treasury.max_spend_usdc)
        steps.append(f"For HTTP 402 / MPP tools, prepare agent-wallet command at subprocess boundary: {' '.join(plan.command)}")
    if SquireMode.PROVIDER in modes:
        steps.append("If GPU hardware is available and approved, follow usepod-agent provider setup; otherwise keep provider path as setup/roadmap.")
    if not environment.funded_balance:
        steps.append("Funding is missing locally; output onboarding/funding instructions instead of attempting paid calls.")
    return tuple(steps)


def _risks(modes: tuple[SquireMode, ...], environment: SquireEnvironment) -> tuple[str, ...]:
    risks = [
        "SQUIRE token redemption mechanics are not modeled as a public implementation-level API.",
        "UsePod coordinator internals are private; integrate only through public register/proxy/provider contracts.",
        "TEE attestation, on-chain slashing, reserved throughput, and compute futures are roadmap unless verified in environment.",
        "agent-wallet and provider tools must remain subprocess/plugin boundaries; do not vendor copyleft or privileged code into core.",
    ]
    if not environment.has_usepod_token:
        risks.append("UsePod token not configured; paid inference route is onboarding-only until funded.")
    if SquireMode.PROVIDER in modes and not environment.gpu_available:
        risks.append("Provider mode requested but no GPU was detected locally.")
    return tuple(risks)


def _success_criteria(modes: tuple[SquireMode, ...]) -> tuple[str, ...]:
    criteria = [
        "A plan distinguishes live, adjacent, and roadmap components.",
        "Routing policy respects budget ceilings and fallback controls.",
        "Every inference/tool call can produce an EconomicMemoryRecord.",
        "No balances, wallets, deposits, keys, or token redemptions are invented.",
    ]
    if SquireMode.PROVIDER in modes:
        criteria.append("Provider path remains optional and requires explicit operator approval before bond/funding actions.")
    return tuple(criteria)


def _float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
