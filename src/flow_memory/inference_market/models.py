"""Flow Memory Inference Market domain records.

These records model inference credit resale and agent economic decisions. They
serialize to plain Python values so API, CLI, docs, and audit evidence can share
one representation without provider SDKs or payment dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass, field, is_dataclass
from enum import Enum
from typing import Any, Mapping

UTC_EPOCH = "2026-05-26T00:00:00Z"
SCHEMA_VERSION = 1
MARKET_VERSION = "inference-market-v1"


class SourceType(str, Enum):
    VENICE_LIKE = "venice_like"
    MORPHEUS_LIKE = "morpheus_like"
    DM_LIKE = "dm_like"
    LEVEL_FIVE_LIKE = "level_five_like"
    OPENAI_COMPATIBLE = "openai_compatible"
    ANTHROPIC_COMPATIBLE = "anthropic_compatible"
    LOCAL = "local"
    INTERNAL = "internal"
    CUSTOM = "custom"


class CreditUnit(str, Enum):
    TOKEN = "token"
    REQUEST = "request"
    INFERENCE_SECOND = "inference_second"
    INFERENCE_MINUTE = "inference_minute"
    MODEL_CALL = "model_call"
    AGENT_STEP = "agent_step"
    TOOL_CALL = "tool_call"
    CREDIT = "credit"


class ListingStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    FILLED = "filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class OrderStatus(str, Enum):
    CREATED = "created"
    MATCHED = "matched"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REJECTED = "rejected"


class AgentInferenceDecision(str, Enum):
    RUN_TASK_NOW = "run_task_now"
    RUN_TASK_DISCOUNT_ROUTE = "run_task_discount_route"
    BUY_DISCOUNT_INFERENCE = "buy_discount_inference"
    SELL_UNUSED_INFERENCE = "sell_unused_inference"
    DEFER_TASK = "defer_task"
    DOWNGRADE_INTELLIGENCE_TIER = "downgrade_intelligence_tier"
    RESERVE_CAPACITY = "reserve_capacity"
    BUY_FORWARD_CAPACITY = "buy_forward_capacity"
    SIMULATE_FUTURES_HEDGE = "simulate_futures_hedge"
    REQUIRE_HUMAN_APPROVAL = "require_human_approval"
    REJECT_NEGATIVE_ROI = "reject_negative_roi"
    USE_LOCAL_NO_PAYMENT_ROUTE = "use_local_no_payment_route"
    USE_FALLBACK_ROUTE = "use_fallback_route"


@dataclass(frozen=True)
class InferenceCreditSource:
    source_id: str
    source_name: str
    source_type: str = SourceType.OPENAI_COMPATIBLE.value
    status: str = "active"
    verified: bool = False
    models: tuple[str, ...] = ()
    supported_units: tuple[str, ...] = (CreditUnit.TOKEN.value, CreditUnit.REQUEST.value)
    base_url: str = ""
    credential_ref: str = ""
    transferable: bool = False
    seller_id: str = ""
    quality_score: float = 1.0
    reliability_score: float = 1.0
    created_at: str = UTC_EPOCH
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class InferenceCreditAccount:
    account_id: str
    owner_id: str
    source_id: str
    workspace_id: str = "default"
    status: str = "active"
    credential_ref: str = ""
    sell_enabled: bool = False
    buy_enabled: bool = True
    created_at: str = UTC_EPOCH
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class InferenceCreditBalance:
    balance_id: str
    account_id: str
    source_id: str
    owner_id: str
    model: str
    unit_type: str = CreditUnit.TOKEN.value
    available_units: float = 0.0
    reserved_units: float = 0.0
    used_units: float = 0.0
    expires_at: str = ""
    transferable: bool = False
    updated_at: str = UTC_EPOCH
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class InferenceCreditInventory:
    inventory_id: str
    owner_id: str
    balances: tuple[InferenceCreditBalance, ...] = ()
    total_available_units: float = 0.0
    sellable_units: float = 0.0
    expires_soon_units: float = 0.0
    created_at: str = UTC_EPOCH

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class InferenceEntitlement:
    entitlement_id: str
    account_id: str
    source_id: str
    model: str
    unit_type: str
    max_units: float
    transferable: bool = False
    expires_at: str = ""
    restrictions: tuple[str, ...] = ()

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class InferenceCreditLedgerEntry:
    ledger_entry_id: str
    account_id: str
    source_id: str
    owner_id: str
    event_type: str
    unit_type: str
    units: float
    balance_after: float
    related_id: str = ""
    dry_run_only: bool = True
    funds_moved: bool = False
    created_at: str = UTC_EPOCH

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class InferenceCreditReservation:
    reservation_id: str
    listing_id: str
    buyer_id: str
    seller_id: str
    unit_type: str
    reserved_units: float
    unit_price: float
    hold_expires_at: str
    status: str = "held"
    dry_run_only: bool = True
    funds_moved: bool = False
    created_at: str = UTC_EPOCH

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class InferenceCreditListing:
    listing_id: str
    seller_id: str
    account_id: str
    source_id: str
    model: str
    unit_type: str
    available_units: float
    unit_price: float
    currency: str = "CREDITS"
    min_order_units: float = 1.0
    status: str = ListingStatus.ACTIVE.value
    expires_at: str = ""
    transferable: bool = True
    dry_run_only: bool = True
    funds_moved: bool = False
    created_at: str = UTC_EPOCH
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class InferenceCreditOrder:
    order_id: str
    buyer_id: str
    model: str
    unit_type: str
    requested_units: float
    max_unit_price: float
    status: str = OrderStatus.CREATED.value
    selected_listing_id: str = ""
    filled_units: float = 0.0
    average_unit_price: float = 0.0
    rejected_reason: str = ""
    dry_run_only: bool = True
    funds_moved: bool = False
    created_at: str = UTC_EPOCH

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class InferenceCreditFill:
    fill_id: str
    order_id: str
    listing_id: str
    buyer_id: str
    seller_id: str
    unit_type: str
    units: float
    unit_price: float
    total_price: float
    dry_run_only: bool = True
    funds_moved: bool = False
    created_at: str = UTC_EPOCH

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class InferenceCreditTransfer:
    transfer_id: str
    from_account_id: str
    to_account_id: str
    source_id: str
    unit_type: str
    units: float
    status: str = "simulated"
    dry_run_only: bool = True
    funds_moved: bool = False
    created_at: str = UTC_EPOCH

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class InferenceCreditQuote:
    quote_id: str
    listing_id: str
    seller_id: str
    source_id: str
    model: str
    unit_type: str
    unit_price: float
    estimated_units: float
    estimated_total_cost: float
    currency: str = "CREDITS"
    expires_at: str = ""
    capacity_available: bool = True
    assumptions: tuple[str, ...] = ()
    dry_run_only: bool = True
    funds_moved: bool = False

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class InferenceMarketPolicy:
    policy_id: str = "default-inference-market-policy"
    allowed_models: tuple[str, ...] = ()
    min_discount_bps: int = 0
    max_unit_price: float = 0.0
    allow_fallback: bool = True
    allow_sell_unused: bool = False
    allow_external_providers: bool = False
    raw_credentials_allowed: bool = False
    dry_run_required: bool = True
    live_settlement_enabled: bool = False
    broadcast_enabled: bool = False
    private_key_inputs_allowed: bool = False

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class InferenceRoute:
    route_id: str
    source_id: str
    listing_id: str
    model: str
    unit_type: str
    unit_price: float
    quality_score: float = 1.0
    latency_ms: int = 0
    compatible_api: str = "openai"
    dry_run_only: bool = True
    funds_moved: bool = False

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class InferenceQuote:
    quote_id: str
    route: InferenceRoute
    estimated_units: float
    estimated_total_cost: float
    discount_bps: int = 0
    expires_at: str = ""
    assumptions: tuple[str, ...] = ()
    dry_run_only: bool = True
    funds_moved: bool = False
    broadcast_allowed: bool = False
    private_key_required: bool = False

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class InferenceMarketDecision:
    decision_id: str
    decision: str
    selected_route: InferenceRoute | None = None
    selected_listing: InferenceCreditListing | None = None
    rejected_routes: tuple[Mapping[str, Any], ...] = ()
    rationale: tuple[str, ...] = ()
    next_safe_actions: tuple[str, ...] = ()
    dry_run_only: bool = True
    funds_moved: bool = False

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class InferenceUsageRecord:
    usage_id: str
    workspace_id: str
    agent_id: str
    goal_id: str
    task_id: str
    model: str
    source_id: str
    route_id: str
    unit_type: str
    estimated_units: float
    actual_units: float
    estimated_cost: float
    actual_cost: float
    credits_bought: float = 0.0
    credits_sold: float = 0.0
    credits_consumed: float = 0.0
    discount_bps: int = 0
    task_value: float = 0.0
    task_roi: float = 0.0
    selected_decision: str = ""
    opportunity_cost: float = 0.0
    latency_ms: int = 0
    quality_score: float = 1.0
    dry_run_only: bool = True
    funds_moved: bool = False
    created_at: str = UTC_EPOCH

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class InferenceUsageLedger:
    ledger_id: str
    usage_records: tuple[InferenceUsageRecord, ...] = ()
    total_actual_cost: float = 0.0
    total_task_value: float = 0.0
    total_roi: float = 0.0
    dry_run_only: bool = True
    funds_moved: bool = False

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class InferenceStatement:
    statement_id: str
    workspace_id: str
    agent_id: str
    period: str
    usage_records: tuple[InferenceUsageRecord, ...] = ()
    total_units: float = 0.0
    total_cost: float = 0.0
    total_task_value: float = 0.0
    net_roi: float = 0.0
    dry_run_only: bool = True
    funds_moved: bool = False

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class InferencePriceSnapshot:
    snapshot_id: str
    source_id: str
    route_id: str
    model: str
    unit_type: str
    unit_price: float
    reference_price: float
    discount_bps: int
    available_units: float
    latency_ms: int = 0
    quality_score: float = 1.0
    reliability_score: float = 1.0
    created_at: str = UTC_EPOCH

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class InferenceDemandSnapshot:
    snapshot_id: str
    requested_model: str
    provider_class: str
    unit_type: str
    units_requested: float
    max_price: float
    urgency: str
    workspace_id: str
    agent_id: str
    accepted_route: str = ""
    rejected_reason: str = ""
    created_at: str = UTC_EPOCH

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class InferenceRoutePriceIndex:
    index_id: str
    route_id: str
    model: str
    unit_type: str
    median_unit_price: float
    best_unit_price: float
    spread_bps: int
    sample_size: int
    created_at: str = UTC_EPOCH

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class InferenceSourcePriceIndex:
    index_id: str
    source_id: str
    model: str
    unit_type: str
    median_unit_price: float
    available_units: float
    reliability_score: float
    created_at: str = UTC_EPOCH

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class AgentBudgetAccount:
    budget_account_id: str
    agent_id: str
    workspace_id: str = "default"
    available_budget: float = 0.0
    reserved_budget: float = 0.0
    currency: str = "CREDITS"
    dry_run_only: bool = True
    funds_moved: bool = False

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class AgentSpendPolicy:
    policy_id: str = "default-agent-spend-policy"
    max_task_spend: float = 0.0
    max_unit_price: float = 0.0
    min_expected_roi: float = 0.0
    allow_defer: bool = True
    allow_downgrade: bool = True
    allow_discount_route: bool = True
    allow_capacity_reservation: bool = True
    require_human_approval_above: float = 1000.0

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class AgentEarnPolicy:
    policy_id: str = "default-agent-earn-policy"
    allow_sell_unused: bool = False
    min_sell_unit_price: float = 0.0
    reserve_minimum_units: float = 0.0
    sell_expiring_first: bool = True
    require_human_approval_above_units: float = 1_000_000.0

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class AgentTreasury:
    treasury_id: str
    agent_id: str
    budget_account: AgentBudgetAccount
    balances: tuple[InferenceCreditBalance, ...] = ()
    spend_policy: AgentSpendPolicy = field(default_factory=AgentSpendPolicy)
    earn_policy: AgentEarnPolicy = field(default_factory=AgentEarnPolicy)
    dry_run_only: bool = True
    funds_moved: bool = False

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class AgentTreasuryLedgerEntry:
    entry_id: str
    treasury_id: str
    event_type: str
    amount: float
    units: float = 0.0
    related_id: str = ""
    dry_run_only: bool = True
    funds_moved: bool = False
    created_at: str = UTC_EPOCH

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class AgentEconomicState:
    state_id: str
    agent_id: str
    treasury: AgentTreasury
    market_bid_price: float = 0.0
    market_ask_price: float = 0.0
    estimated_task_value: float = 0.0
    urgency: str = "normal"
    quality_requirement: str = "standard"
    created_at: str = UTC_EPOCH

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class TaskValueEstimate:
    estimate_id: str
    task: str
    agent_id: str
    goal_id: str = ""
    estimated_task_value: float = 0.0
    confidence: float = 0.0
    unknown_value: bool = False
    rationale: tuple[str, ...] = ()

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class RunVsSellAnalysis:
    analysis_id: str
    estimated_task_value: float
    estimated_run_cost: float
    estimated_sell_value: float
    opportunity_cost: float
    expected_roi_if_run: float
    expected_roi_if_sell: float
    urgent: bool = False
    value_unknown: bool = False
    rationale: tuple[str, ...] = ()
    dry_run_only: bool = True
    funds_moved: bool = False

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


@dataclass(frozen=True)
class OpportunityCostDecision:
    decision_id: str
    decision: str
    recommended_action: str
    analysis: RunVsSellAnalysis
    selected_route: InferenceRoute | None = None
    selected_listing: InferenceCreditListing | None = None
    rejected_routes: tuple[Mapping[str, Any], ...] = ()
    rejected_reasons: tuple[str, ...] = ()
    rationale: tuple[str, ...] = ()
    next_safe_actions: tuple[str, ...] = ()
    dry_run_only: bool = True
    funds_moved: bool = False
    broadcast_allowed: bool = False
    private_key_required: bool = False

    def as_record(self) -> dict[str, Any]:
        return _record_dict(self)


def _record_dict(value: Any) -> dict[str, Any]:
    record = _record(value)
    if not isinstance(record, dict):
        raise TypeError("expected dataclass record")
    return record
def _record(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _record(val) for key, val in value.__dict__.items()}
    if isinstance(value, tuple):
        return tuple(_record(item) for item in value)
    if isinstance(value, list):
        return [_record(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _record(val) for key, val in value.items()}
    return value
