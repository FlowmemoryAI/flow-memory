"""Flow Memory Compute Market domain records.

The compute market treats compute capacity as the economic resource. These
records are deliberately protocol-neutral and serialize to plain Python values
so they can be returned from APIs, written to durable economic memory, or
embedded in release evidence without importing wallet/provider SDKs.
"""
from __future__ import annotations

from dataclasses import dataclass, field, is_dataclass
from enum import Enum
from typing import Any, Mapping

UTC_EPOCH = "2026-05-24T00:00:00Z"
SCHEMA_VERSION = 6
PLANNER_VERSION = "compute-market-planner-v2"
SUPPORTED_UNIT_TYPES: tuple[str, ...] = (
    "token",
    "request",
    "gpu_second",
    "gpu_minute",
    "gpu_hour",
    "cpu_second",
    "memory_gb_hour",
    "storage_gb_month",
    "bandwidth_gb",
    "agent_step",
    "tool_call",
    "inference_job",
    "batch_job",
    "reserved_capacity_slot",
)


class SelectionStrategy(str, Enum):
    LOWEST_COST = "lowest_cost"
    BEST_LATENCY = "best_latency"
    BEST_ROI = "best_roi"
    MARKETPLACE_PREFERRED = "marketplace_preferred"
    CAPACITY_GUARANTEED = "capacity_guaranteed"
    RELIABILITY_WEIGHTED = "reliability_weighted"
    BALANCED = "balanced"
class IntelligenceTier(str, Enum):
    INSTANT = "instant"
    STANDARD = "standard"
    DEEP_REASONING = "deep_reasoning"
    BACKGROUND_AGENT = "background_agent"
    BATCH = "batch"
    PREMIUM = "premium"
    RESERVED_CAPACITY = "reserved_capacity"


class ReasoningLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


class RunDecision(str, Enum):
    RUN_NOW = "run_now"
    DEFER_UNTIL_CHEAPER = "defer_until_cheaper"
    DOWNGRADE_TIER = "downgrade_tier"
    RESERVE_CAPACITY = "reserve_capacity"
    REQUIRE_HUMAN_APPROVAL = "require_human_approval"
    REJECT_NEGATIVE_ROI = "reject_negative_roi"



class QuoteStatus(str, Enum):
    VALID = "valid"
    EXPIRED = "expired"
    STALE = "stale"
    UNKNOWN_PRICE = "unknown_price"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_ERROR = "provider_error"
    INVALID_RESPONSE = "invalid_response"
    CAPACITY_UNAVAILABLE = "capacity_unavailable"
    POLICY_REJECTED = "policy_rejected"
    UNSUPPORTED_TASK = "unsupported_task"
    DISABLED_PROVIDER = "disabled_provider"


class ErrorCategory(str, Enum):
    VALIDATION_ERROR = "validation_error"
    AUTH_ERROR = "auth_error"
    SCOPE_ERROR = "scope_error"
    POLICY_DENIED = "policy_denied"
    NO_VALID_ROUTE = "no_valid_route"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_ERROR = "provider_error"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    QUOTE_EXPIRED = "quote_expired"
    QUOTE_STALE = "quote_stale"
    UNKNOWN_PRICE = "unknown_price"
    CAPACITY_UNAVAILABLE = "capacity_unavailable"
    BUDGET_EXCEEDED = "budget_exceeded"
    ROI_NEGATIVE = "roi_negative"
    MARKETPLACE_REQUIRED = "marketplace_required"
    FALLBACK_DISALLOWED = "fallback_disallowed"
    SETTLEMENT_DISALLOWED = "settlement_disallowed"
    UNSAFE_PAYLOAD = "unsafe_payload"
    AUDIT_REQUIRED_FAILED = "audit_required_failed"
    STORAGE_ERROR = "storage_error"
    CONFIGURATION_ERROR = "configuration_error"
    RATE_LIMITED = "rate_limited"
    CIRCUIT_OPEN = "circuit_open"
    INTERNAL_ERROR = "internal_error"


@dataclass(frozen=True)
class ProviderCapability:
    capability_id: str
    unit_types: tuple[str, ...] = ("token",)
    models: tuple[str, ...] = ()
    max_capacity: float = 0.0
    networks: tuple[str, ...] = ()
    payment_assets: tuple[str, ...] = ()
    reliability_score: float = 1.0
    created_at: str = UTC_EPOCH
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class UnitPriceSnapshot:
    unit_type: str
    unit_price: float | None
    payment_asset: str
    network: str
    provider_id: str = ""
    route_id: str = ""
    created_at: str = UTC_EPOCH
    quote_ttl_seconds: int = 300
    confidence: float = 1.0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class PriceCurve:
    pricing_model: str
    unit_prices: tuple[UnitPriceSnapshot, ...] = ()
    fixed_cost: float = 0.0
    minimum_charge: float = 0.0
    blended: bool = False
    notes: tuple[str, ...] = ()

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class ComputeCapacityWindow:
    window_id: str
    starts_at: str = UTC_EPOCH
    ends_at: str = UTC_EPOCH
    capacity_available: bool = True
    capacity_units: float = 0.0
    reserved_capacity_slots: int = 0
    provider_id: str = ""
    route_id: str = ""

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class ComputeReservation:
    reservation_id: str
    provider_id: str
    route_id: str
    capacity_window: ComputeCapacityWindow
    unit_type: str = "reserved_capacity_slot"
    units_reserved: float = 0.0
    estimated_total_cost: float | None = None
    payment_asset: str = ""
    dry_run_only: bool = True
    created_at: str = UTC_EPOCH
    updated_at: str = UTC_EPOCH
    tenant_id: str = ""
    workspace_id: str = ""
    archived_at: str = ""

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class ComputeProvider:
    provider_id: str
    provider_name: str
    provider_type: str
    market_type: str
    network: str
    payment_asset: str
    capabilities: tuple[ProviderCapability, ...] = ()
    reliability_score: float = 1.0
    dry_run_only: bool = True
    capacity_available: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)
    created_at: str = UTC_EPOCH
    updated_at: str = UTC_EPOCH
    tenant_id: str = ""
    workspace_id: str = ""
    status: str = "active"
    supported_unit_types: tuple[str, ...] = ()
    supported_networks: tuple[str, ...] = ()
    supported_assets: tuple[str, ...] = ()
    supported_settlement_modes: tuple[str, ...] = ("generic_dry_run",)
    average_latency_ms: int = 0
    quote_ttl_seconds: int = 300
    rate_limit_profile: Mapping[str, Any] = field(default_factory=dict)
    health_check_url: str = ""
    configured_by: str = "system"
    verified: bool = False
    config_version: int = 1
    disabled_at: str = ""
    archived_at: str = ""

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class ComputeRoute:
    route_id: str
    provider_id: str
    provider_or_route: str
    provider_type: str
    market_type: str
    network: str
    payment_asset: str
    unit_type: str
    unit_price: float | None = None
    estimated_units: float = 0.0
    estimated_total_cost: float | None = None
    estimated_latency_ms: int = 0
    capacity_available: bool = True
    reservation_required: bool = False
    settlement_mode: str = "generic_dry_run"
    settlement_modes: tuple[str, ...] = ("generic_dry_run",)
    dry_run_only: bool = True
    fallback_route: bool = False
    quote_ttl_seconds: int = 300
    confidence: float = 1.0
    reliability_score: float = 1.0
    price_curve: PriceCurve | None = None
    capacity_window: ComputeCapacityWindow | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    created_at: str = UTC_EPOCH
    updated_at: str = UTC_EPOCH
    tenant_id: str = ""
    workspace_id: str = ""
    route_type: str = "compute"
    pricing_model: str = "unit"
    supported_assets: tuple[str, ...] = ()
    supported_networks: tuple[str, ...] = ()
    fallback_priority: int = 100
    enabled: bool = True
    verified_provider_required: bool = False
    config_version: int = 1
    disabled_at: str = ""
    archived_at: str = ""

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class ComputeQuote:
    quote_id: str
    provider_id: str
    provider_or_route: str
    provider_type: str
    route_id: str
    market_type: str
    network: str
    payment_asset: str
    unit_type: str
    unit_price: float | None
    estimated_units: float
    estimated_total_cost: float | None
    estimated_latency_ms: int = 0
    capacity_available: bool = True
    reservation_required: bool = False
    settlement_mode: str = "generic_dry_run"
    settlement_options: tuple[str, ...] = ("generic_dry_run",)
    dry_run_only: bool = True
    fallback_allowed: bool = True
    marketplace_only: bool = False
    task_roi: float = 0.0
    selected_reason: str = ""
    rejected_reasons: tuple[str, ...] = ()
    policy_result: str = "unevaluated"
    confidence: float = 1.0
    created_at: str = UTC_EPOCH
    quote_ttl_seconds: int = 300
    expired: bool = False
    stale: bool = False
    assumptions: tuple[str, ...] = ()
    capacity_window: ComputeCapacityWindow | None = None
    original_quote: Mapping[str, Any] = field(default_factory=dict)
    comparability_warnings: tuple[str, ...] = ()
    updated_at: str = UTC_EPOCH
    tenant_id: str = ""
    workspace_id: str = ""
    status: str = QuoteStatus.VALID.value
    source: str = "simulation"
    expires_at: str = ""
    task_hash: str = ""
    policy_hash: str = ""
    raw_quote_hash: str = ""
    signed_quote: str = ""
    signed_quote_valid: bool = False
    provider_error_code: str = ""
    retryable: bool = False
    idempotency_key: str = ""

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class ComputeIntent:
    intent_id: str
    task_id: str
    agent_id: str
    goal_id: str
    route_id: str
    provider_id: str
    unit_type: str
    estimated_units: float
    estimated_total_cost: float | None
    dry_run_only: bool = True
    created_at: str = UTC_EPOCH
    updated_at: str = UTC_EPOCH
    tenant_id: str = ""
    workspace_id: str = ""
    request_id: str = ""
    idempotency_key: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class PaymentIntent:
    payment_intent_id: str
    rail: str
    network: str
    payment_asset: str
    estimated_amount: float
    provider_id: str = ""
    route_id: str = ""
    settlement_mode: str = "generic_dry_run"
    dry_run_only: bool = True
    broadcast_required: bool = False
    requires_private_key: bool = False
    moves_funds: bool = False
    broadcast_allowed: bool = False
    private_key_required: bool = False
    funds_moved: bool = False
    command: tuple[str, ...] = ()
    payload: Mapping[str, Any] = field(default_factory=dict)
    created_at: str = UTC_EPOCH
    updated_at: str = UTC_EPOCH
    tenant_id: str = ""
    workspace_id: str = ""
    idempotency_key: str = ""

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class PaymentPlan:
    payment_plan_id: str
    selected_rail: str
    payment_intents: tuple[PaymentIntent, ...] = ()
    estimated_total_amount: float = 0.0
    payment_asset: str = ""
    network: str = ""
    dry_run_only: bool = True
    warnings: tuple[str, ...] = ()
    next_safe_actions: tuple[str, ...] = ()
    created_at: str = UTC_EPOCH
    updated_at: str = UTC_EPOCH
    tenant_id: str = ""
    workspace_id: str = ""
    request_id: str = ""
    idempotency_key: str = ""

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class SettlementIntent:
    settlement_intent_id: str
    route_id: str
    provider_id: str
    payment_plan_id: str
    settlement_mode: str
    estimated_amount: float
    payment_asset: str
    network: str
    dry_run_only: bool = True
    broadcast_required: bool = False
    moves_funds: bool = False
    broadcast_allowed: bool = False
    private_key_required: bool = False
    funds_moved: bool = False
    recipient: str = ""
    transaction_intent: Mapping[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    policy_result: str = "simulated"
    status: str = "simulated"
    created_at: str = UTC_EPOCH
    updated_at: str = UTC_EPOCH
    tenant_id: str = ""
    workspace_id: str = ""
    request_id: str = ""
    idempotency_key: str = ""
    live_settlement_gate_result: Mapping[str, Any] = field(default_factory=dict)

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class TaskEconomicProfile:
    task_id: str
    task_description: str
    agent_id: str = ""
    goal_id: str = ""
    expected_output_type: str = "artifact"
    latency_requirement_ms: int = 0
    budget: float = 0.0
    quality_requirement: str = "standard"
    estimated_value: float | None = None
    estimated_units: Mapping[str, float] = field(default_factory=dict)
    created_at: str = UTC_EPOCH
    updated_at: str = UTC_EPOCH
    tenant_id: str = ""
    workspace_id: str = ""
    task_type: str = "generic"
    task_hash: str = ""

    intelligence_tier: str = IntelligenceTier.STANDARD.value
    reasoning_level: str = ReasoningLevel.MEDIUM.value
    reasoning_budget: Mapping[str, Any] = field(default_factory=dict)
    background_run_policy: Mapping[str, Any] = field(default_factory=dict)
    urgency: Mapping[str, Any] = field(default_factory=dict)
    quality_target: Mapping[str, Any] = field(default_factory=dict)

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class ReasoningBudget:
    reasoning_level: str = ReasoningLevel.MEDIUM.value
    max_reasoning_steps: int = 8
    max_parallel_branches: int = 1
    max_reflection_passes: int = 1
    max_tool_calls: int = 4
    max_wall_time_seconds: int = 60
    max_background_runtime_seconds: int = 0
    checkpoint_interval_seconds: int = 0

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class BackgroundRunPolicy:
    allow_background: bool = False
    background_deadline: str = ""
    checkpoint_interval_seconds: int = 0
    max_background_runtime_seconds: int = 0
    defer_policy: str = "run_now"

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class TaskUrgency:
    run_now: bool = True
    defer_allowed: bool = False
    deadline: str = ""
    max_latency_ms: int = 0
    off_peak_allowed: bool = False

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class QualityTarget:
    target: str = "standard"
    min_confidence: float = 0.0
    require_audit_trail: bool = True
    require_verified_provider: bool = False

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class IntelligencePlan:
    intelligence_plan_id: str
    task_id: str
    agent_id: str
    goal_id: str
    recommended_intelligence_tier: str
    recommended_reasoning_budget: Mapping[str, Any]
    recommended_route_types: tuple[str, ...]
    max_recommended_spend: float
    run_decision: str
    defer_until: str = ""
    downgrade_options: tuple[Mapping[str, Any], ...] = ()
    reserve_capacity_recommended: bool = False
    rationale: tuple[str, ...] = ()
    next_safe_actions: tuple[str, ...] = ()
    compute_plan: Mapping[str, Any] = field(default_factory=dict)
    price_context: Mapping[str, Any] = field(default_factory=dict)
    dry_run_only: bool = True
    funds_moved: bool = False
    broadcast_allowed: bool = False
    private_key_required: bool = False
    created_at: str = UTC_EPOCH
    tenant_id: str = ""
    workspace_id: str = ""
    request_id: str = ""
    idempotency_key: str = ""

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class ComputePriceSnapshot:
    price_snapshot_id: str
    provider_id: str
    route_id: str
    unit_type: str
    unit_price: float | None
    payment_asset: str
    network: str
    latency_ms: int = 0
    reliability_score: float = 0.0
    capacity_available: bool = True
    market_type: str = ""
    quote_source: str = ""
    confidence: float = 1.0
    created_at: str = UTC_EPOCH
    tenant_id: str = ""
    workspace_id: str = ""
    quote_id: str = ""
    task_hash: str = ""

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class RoutePriceIndex:
    route_id: str
    unit_type: str
    latest_unit_price: float | None
    median_unit_price: float | None
    sample_count: int
    payment_asset: str = ""
    network: str = ""
    provider_id: str = ""
    created_at: str = UTC_EPOCH

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class ProviderPriceIndex:
    provider_id: str
    latest_unit_price: float | None
    median_unit_price: float | None
    sample_count: int
    unit_type: str = ""
    payment_asset: str = ""
    network: str = ""
    created_at: str = UTC_EPOCH

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class PriceAnomaly:
    anomaly_id: str
    provider_id: str
    route_id: str
    unit_type: str
    unit_price: float
    median_unit_price: float
    ratio_to_median: float
    direction: str
    severity: str
    created_at: str = UTC_EPOCH

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class PriceForecast:
    forecast_id: str
    provider_id: str
    route_id: str
    unit_type: str
    forecast_unit_price: float | None
    confidence: float
    sample_count: int
    horizon_seconds: int = 3600
    created_at: str = UTC_EPOCH

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class IntelligenceUsageRecord:
    usage_record_id: str
    workspace_id: str
    agent_id: str
    goal_id: str
    task_id: str
    intelligence_tier: str
    reasoning_level: str
    metered_units: Mapping[str, float]
    estimated_cost: float
    actual_cost: float | None
    estimated_value: float | None
    task_roi: float
    selected_route: str
    provider_id: str
    route_id: str
    background_runtime_seconds: int = 0
    created_at: str = UTC_EPOCH
    tenant_id: str = ""
    request_id: str = ""
    decision_id: str = ""

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class ComputeStatement:
    statement_id: str
    workspace_id: str
    period: str
    total_estimated_cost: float
    total_actual_cost: float
    record_count: int
    highest_roi_agent: str = ""
    waste_detected: float = 0.0
    recommended_budget_changes: tuple[Mapping[str, Any], ...] = ()
    created_at: str = UTC_EPOCH

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class AgentBudgetPolicy:
    max_total_cost: float = 0.0
    max_unit_price: float = 0.0
    allowed_assets: tuple[str, ...] = ()
    allowed_networks: tuple[str, ...] = ()
    allowed_providers: tuple[str, ...] = ()
    denied_providers: tuple[str, ...] = ()
    require_roi_positive: bool = False
    require_human_approval_above: float = 0.0
    human_approval_granted: bool = False
    max_latency_ms: int = 0
    max_slippage_bps: int = 0
    quote_ttl_seconds: int = 0
    allow_unknown_price: bool = False
    allow_stale_quote: bool = False
    settlement_modes_allowed: tuple[str, ...] = ()
    dry_run_required: bool = True
    fallback_allowed: bool = True
    require_capacity_confirmation: bool = False
    max_retries: int = 2
    max_provider_timeout_ms: int = 2_000
    max_global_planning_timeout_ms: int = 10_000
    require_audit_log: bool = True
    require_idempotency_key: bool = False
    require_verified_provider: bool = False
    require_signed_quote: bool = False
    max_budget_period: str = "daily"
    per_agent_daily_budget: float = 0.0
    per_goal_budget: float = 0.0
    per_workspace_budget: float = 0.0
    provider_rate_limit_policy: Mapping[str, Any] = field(default_factory=dict)

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class ComputeMarketPolicy:
    marketplace_only: bool = False
    dry_run_required: bool = True
    fallback_allowed: bool = True
    require_capacity_confirmation: bool = False
    allow_unknown_price: bool = False
    allow_stale_quote: bool = False
    selection_strategy: str = SelectionStrategy.BALANCED.value
    settlement_modes_allowed: tuple[str, ...] = (
        "http_402_dry_run",
        "solana_usdc_dry_run",
        "base_sepolia_erc4337_dry_run",
        "generic_dry_run",
        "no_payment",
    )
    quote_ttl_seconds: int = 300
    policy_id: str = "default-compute-market-policy"
    policy_version: str = "v2"
    max_retries: int = 2
    max_provider_timeout_ms: int = 2_000
    max_global_planning_timeout_ms: int = 10_000
    require_audit_log: bool = True
    require_idempotency_key: bool = False
    require_verified_provider: bool = False
    require_signed_quote: bool = False
    require_human_approval_above: float = 0.0
    max_latency_ms: int = 0
    max_slippage_bps: int = 0
    max_budget_period: str = "daily"
    per_agent_daily_budget: float = 0.0
    per_goal_budget: float = 0.0
    per_workspace_budget: float = 0.0
    provider_rate_limit_policy: Mapping[str, Any] = field(default_factory=dict)
    live_settlement_enabled: bool = False
    broadcast_enabled: bool = False
    private_key_inputs_allowed: bool = False
    created_at: str = UTC_EPOCH
    updated_at: str = UTC_EPOCH
    tenant_id: str = ""
    workspace_id: str = ""
    archived_at: str = ""

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class PolicyTrace:
    policy_id: str
    policy_version: str
    checks_run: tuple[str, ...]
    passed_checks: tuple[str, ...]
    failed_checks: tuple[str, ...]
    rejected_reasons: tuple[Mapping[str, str], ...]
    warnings: tuple[str, ...]
    final_result: str
    created_at: str = UTC_EPOCH

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class RouteDecision:
    selected_route: Mapping[str, Any] | None
    normalized_quote: Mapping[str, Any] | None
    accepted_routes: tuple[Mapping[str, Any], ...]
    rejected_routes: tuple[Mapping[str, Any], ...]
    rejected_reasons: Mapping[str, tuple[str, ...]]
    policy_result: str
    fail_closed_errors: tuple[str, ...] = ()
    rejected_explanations: Mapping[str, tuple[Mapping[str, str], ...]] = field(default_factory=dict)
    selection_strategy: str = ""
    selected_reason: str = ""
    confidence: float = 0.0
    warnings: tuple[str, ...] = ()
    created_at: str = UTC_EPOCH
    decision_id: str = ""
    request_id: str = ""
    idempotency_key: str = ""
    agent_id: str = ""
    goal_id: str = ""
    tenant_id: str = ""
    workspace_id: str = ""
    task_profile_hash: str = ""
    policy_hash: str = ""
    strategy: str = ""
    provider_candidates: tuple[str, ...] = ()
    quote_snapshots: tuple[Mapping[str, Any], ...] = ()
    normalized_quotes: tuple[Mapping[str, Any], ...] = ()
    tie_breakers: tuple[str, ...] = ()
    policy_trace: Mapping[str, Any] = field(default_factory=dict)
    planner_version: str = PLANNER_VERSION
    replay_payload: Mapping[str, Any] = field(default_factory=dict)
    updated_at: str = UTC_EPOCH

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class EconomicMemoryRecord:
    task_id: str
    agent_id: str
    goal_id: str
    provider_or_route: str
    provider_type: str
    marketplace_route: bool
    unit_prices: Mapping[str, float]
    unit_type: str
    estimated_units: float
    actual_units: float | None
    estimated_total_cost: float | None
    actual_total_cost: float | None
    estimated_latency_ms: int
    actual_latency_ms: int | None
    task_roi: float
    roi_basis: str
    fallback_used: bool
    fallback_reason: str
    rejected_routes: tuple[Mapping[str, Any], ...]
    policy_snapshot: Mapping[str, Any]
    quote_snapshot: Mapping[str, Any]
    settlement_intent_id: str
    dry_run_only: bool
    selected_reason: str
    created_at: str = UTC_EPOCH
    record_id: str = ""
    tenant_id: str = ""
    workspace_id: str = ""
    request_id: str = ""
    decision_id: str = ""
    provider_id: str = ""
    route_id: str = ""
    task_type: str = "generic"
    task_hash: str = ""
    policy_result: str = ""
    selected_route_id: str = ""
    route_rejected_count: int = 0
    stale_quote: bool = False
    policy_failure_codes: tuple[str, ...] = ()
    updated_at: str = UTC_EPOCH
    schema_version: int = SCHEMA_VERSION
    idempotency_key: str = ""
    archived_at: str = ""

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class AuditEvent:
    audit_event_id: str
    request_id: str
    actor_id: str
    actor_type: str
    action: str
    resource_type: str
    resource_id: str
    result: str
    reason_codes: tuple[str, ...] = ()
    tenant_id: str = ""
    workspace_id: str = ""
    agent_id: str = ""
    goal_id: str = ""
    decision_id: str = ""
    policy_id: str = ""
    route_id: str = ""
    provider_id: str = ""
    dry_run_only: bool = True
    funds_moved: bool = False
    broadcast_allowed: bool = False
    private_key_required: bool = False
    ip_hash: str = ""
    user_agent: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    created_at: str = UTC_EPOCH
    previous_hash: str = ""
    event_hash: str = ""
    hash_algorithm: str = "sha256"
    chain_id: str = ""
    sequence_number: int = 0
    canonical_payload_hash: str = ""
    signed_at: str = ""
    verification_status: str = ""

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class ProviderHealthSnapshot:
    health_snapshot_id: str
    provider_id: str
    status: str
    reliability_score: float
    latency_ms: int
    checked_at: str = UTC_EPOCH
    route_count: int = 0
    error_code: str = ""
    message: str = ""
    rate_limits: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class QuoteCacheEntry:
    cache_key: str
    provider_id: str
    route_id: str
    task_hash: str
    policy_hash: str
    quote: Mapping[str, Any]
    source: str
    created_at: str = UTC_EPOCH
    updated_at: str = UTC_EPOCH
    expires_at: str = ""
    ttl_seconds: int = 300
    status: str = QuoteStatus.VALID.value
    provider_config_version: int = 1

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class EconomicMemoryQueryRequest:
    query: str = "summary"
    start_time: str = ""
    end_time: str = ""
    agent_id: str = ""
    goal_id: str = ""
    provider_id: str = ""
    route_id: str = ""
    task_type: str = ""
    marketplace_only: bool | None = None
    unit_type: str = ""
    policy_result: str = ""
    selected_only: bool = False
    rejected_only: bool = False
    fallback_used: bool | None = None
    limit: int = 100
    cursor: str = ""

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class EconomicMemoryQueryResponse:
    ok: bool
    query: str
    data: Mapping[str, Any]
    confidence: float
    sample_size: int
    time_range: Mapping[str, str]
    filters_applied: Mapping[str, Any]
    warnings: tuple[str, ...]
    next_recommended_action: str
    cursor: str = ""
    record_count: int = 0

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class ComputeMarketError:
    error_code: str
    error_category: str
    message: str
    details: Mapping[str, Any] = field(default_factory=dict)
    request_id: str = ""
    retryable: bool = False
    rejected_reasons: tuple[str, ...] = ()
    next_safe_actions: tuple[str, ...] = ()

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class ComputeMarketHealth:
    ok: bool
    compute_market_enabled: bool
    database_reachable: bool
    provider_registry_reachable: bool
    audit_log_writable: bool
    quote_cache_reachable: bool
    provider_health_summary: tuple[Mapping[str, Any], ...]
    mode: str = "production_planning"
    warnings: tuple[str, ...] = ()

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class LiveSettlementGateResult:
    ok: bool
    final_result: str
    failed_gates: tuple[str, ...]
    passed_gates: tuple[str, ...]
    live_settlement_enabled: bool = False
    broadcast_enabled: bool = False
    private_key_inputs_allowed: bool = False
    next_safe_actions: tuple[str, ...] = ()
    created_at: str = UTC_EPOCH

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class ComputePlan:
    ok: bool
    profile: Mapping[str, Any]
    selected_route: Mapping[str, Any] | None
    normalized_quote: Mapping[str, Any] | None
    rejected_routes: tuple[Mapping[str, Any], ...]
    rejected_reasons: Mapping[str, tuple[str, ...]]
    policy_result: str
    payment_plan: Mapping[str, Any]
    settlement_intent: Mapping[str, Any]
    economic_memory_preview: Mapping[str, Any]
    warnings: tuple[str, ...]
    next_safe_actions: tuple[str, ...]
    fail_closed_errors: tuple[str, ...] = ()
    rejected_explanations: Mapping[str, tuple[Mapping[str, str], ...]] = field(default_factory=dict)
    provider_count: int = 0
    route_count: int = 0
    quote_count: int = 0
    created_at: str = UTC_EPOCH
    request_id: str = ""
    idempotency_key: str = ""
    decision_id: str = ""
    policy_trace: Mapping[str, Any] = field(default_factory=dict)
    route_decision: Mapping[str, Any] = field(default_factory=dict)
    audit_event_ids: tuple[str, ...] = ()
    planner_version: str = PLANNER_VERSION
    dry_run_only: bool = True
    funds_moved: bool = False
    broadcast_allowed: bool = False
    private_key_required: bool = False

    def as_record(self) -> dict[str, Any]:
        return _record(self)


def _record(item: object) -> dict[str, Any]:
    data = dict(getattr(item, "__dict__"))
    for key, value in list(data.items()):
        data[key] = _nested(value)
    return data


def _nested(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and hasattr(value, "as_record"):
        return value.as_record()
    if isinstance(value, tuple):
        return tuple(_nested(item) for item in value)
    if isinstance(value, list):
        return tuple(_nested(item) for item in value)
    if isinstance(value, Mapping):
        return {str(key): _nested(child) for key, child in value.items()}
    return value
