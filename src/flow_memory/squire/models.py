"""Typed Squire control-plane records.

The records intentionally separate live integrations from adjacent and roadmap items.
They are JSON-serializable so they can be stored in memory, release evidence, and
API responses without importing external wallet or inference SDKs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class SquireMode(str, Enum):
    BUYER = "buyer mode"
    PROVIDER = "provider mode"
    HYBRID = "hybrid mode"
    TREASURY = "treasury mode"
    PAID_TOOL = "paid-tool mode"
    ROADMAP_RESEARCH = "roadmap research mode"


_LIVE_STACK = ("level5", "usepod", "agent-wallet", "usepod-agent", "sortis-skills")
_ROADMAP_ITEMS = (
    "TEE attestation",
    "content-addressed model registry",
    "on-chain slashing",
    "reserved throughput staking",
    "compute futures",
    "native SQUIRE redemption API",
)


@dataclass(frozen=True)
class AgentTreasury:
    agent_id: str = ""
    wallet_pubkey: str = ""
    custodial_status: str = "none"
    level5_token_present: bool = False
    usepod_token_present: bool = False
    usepod_token_id: str = ""
    usdc_balance: float = 0.0
    max_spend_usdc: float = 0.0
    max_price_input_per_million: float = 0.0
    max_price_output_per_million: float = 0.0
    approved_models: tuple[str, ...] = ()
    preferred_route_mode: str = "usepod-auto"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class SquireEnvironment:
    has_solana_wallet: bool = False
    has_level5_token: bool = False
    has_usepod_token: bool = False
    funded_balance: bool = False
    gpu_available: bool = False
    user_budget_usdc: float = 0.0
    preferred_models: tuple[str, ...] = ()
    latency_budget_ms: int = 0
    secrets_present: tuple[str, ...] = ()
    constraints: Mapping[str, Any] = field(default_factory=dict)

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class SquireRoutingPolicy:
    route_mode: str = "usepod-auto"
    marketplace_only: bool = False
    allow_centralized_fallback: bool = True
    quality_sensitive: bool = False
    max_input_price_per_million: float = 0.0
    max_output_price_per_million: float = 0.0
    commodity_model_candidates: tuple[str, ...] = ("open-weight-router", "cheap-eligible-route")
    frontier_model_candidates: tuple[str, ...] = ("frontier-for-high-value-step",)

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class EconomicMemoryRecord:
    goal_id: str
    wallet_pubkey: str = ""
    treasury_source: str = "none"
    route_mode: str = "direct"
    provider_class: str = "unknown"
    model_requested: str = ""
    provider_model_id: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    price_input_per_million: float = 0.0
    price_output_per_million: float = 0.0
    total_cost: float = 0.0
    balance_before: float = 0.0
    balance_after: float = 0.0
    latency_ms: int = 0
    fallback_used: bool = False
    canary_risk: str = "unknown"
    quality_signal: float = 0.0
    live_or_roadmap: str = "live"
    tool_mode: str = "direct"
    usepod_token_id: str = ""

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class SquirePlan:
    goal_summary: str
    recommended_operating_mode: tuple[str, ...]
    live_stack_to_use_now: tuple[str, ...]
    optional_roadmap_extensions: tuple[str, ...]
    system_architecture: Mapping[str, Any]
    required_env_vars_and_secrets: tuple[str, ...]
    memory_writes: tuple[Mapping[str, Any], ...]
    budget_and_routing_policy: Mapping[str, Any]
    execution_steps: tuple[str, ...]
    risks_and_unknowns: tuple[str, ...]
    success_criteria: tuple[str, ...]
    environment: Mapping[str, Any]
    live_or_roadmap: str = "live-first"

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class RouteCandidate:
    provider_class: str
    provider_or_route: str
    model: str
    input_price_per_million: float
    output_price_per_million: float
    latency_ms: int = 0
    quality_score: float = 0.0
    centralized_fallback: bool = False
    live_or_roadmap: str = "live"

    def eligible_for(self, policy: SquireRoutingPolicy) -> bool:
        if policy.marketplace_only and self.provider_class == "centralized":
            return False
        if policy.max_input_price_per_million and self.input_price_per_million > policy.max_input_price_per_million:
            return False
        if policy.max_output_price_per_million and self.output_price_per_million > policy.max_output_price_per_million:
            return False
        return self.live_or_roadmap == "live"

    @property
    def score_price(self) -> float:
        return self.input_price_per_million + self.output_price_per_million

    def as_record(self) -> dict[str, Any]:
        return _record(self)


DEFAULT_LIVE_STACK = _LIVE_STACK
DEFAULT_ROADMAP_ITEMS = _ROADMAP_ITEMS


def _record(item: object) -> dict[str, Any]:
    data = dict(getattr(item, "__dict__"))
    for key, value in list(data.items()):
        if isinstance(value, Enum):
            data[key] = value.value
        elif isinstance(value, tuple):
            data[key] = tuple(_nested(child) for child in value)
        elif isinstance(value, Mapping):
            data[key] = {str(k): _nested(v) for k, v in value.items()}
    return data


def _nested(value: Any) -> Any:
    if hasattr(value, "as_record"):
        return value.as_record()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return tuple(_nested(item) for item in value)
    if isinstance(value, Mapping):
        return {str(k): _nested(v) for k, v in value.items()}
    return value
