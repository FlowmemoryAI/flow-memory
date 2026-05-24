"""Mission Control visual state dataclasses."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from flow_memory.visualization.events import VISUAL_SCHEMA_VERSION


@dataclass(frozen=True)
class VisualAgentNode:
    agent_id: str
    label: str
    role: str
    status: str = "idle"
    reputation: float = 0.0
    capabilities: tuple[str, ...] = ()
    provenance: str = "live"
    source_event_id: str = ""

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class VisualTaskNode:
    task_id: str
    label: str
    status: str
    requester_id: str = ""
    worker_id: str = ""
    verifier_id: str = ""
    reward: float = 0.0
    provenance: str = "live"
    source_event_id: str = ""
    ignored_regressions: tuple[str, ...] = ()

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class VisualMemoryNode:
    memory_id: str
    agent_id: str
    kind: str
    summary: str
    importance: float = 0.0
    provenance: str = "live"
    source_event_id: str = ""

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class VisualEconomyEdge:
    edge_id: str
    from_id: str
    to_id: str
    kind: str
    amount: float = 0.0
    currency: str = "LOCAL_CREDITS"
    status: str = "observed"
    provenance: str = "live"
    source_event_id: str = ""
    task_id: str = ""
    reputation_delta: float = 0.0

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class VisualNeuralSignal:
    signal_id: str
    agent_id: str
    backend: str
    status: str
    plan_score: float = 0.0
    risk_score: float = 0.0
    surprise_score: float = 0.0
    session_id: str = ""
    phase: str = ""
    prediction_confidence: float = 0.0
    uncertainty: float = 0.0
    learning_tick_count: int = 0
    memory_activation_count: int = 0
    action_state: str = ""
    policy_gate_state: str = ""
    provenance: str = "live"
    source_event_id: str = ""

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class VisualComputeMarketSignal:
    signal_id: str
    agent_id: str
    task_id: str
    event: str
    status: str
    provider_id: str = ""
    route_id: str = ""
    quote_total: float = 0.0
    payment_rail: str = "local_credits"
    dry_run_only: bool = True
    no_funds_moved: bool = True
    provenance: str = "live"
    source_event_id: str = ""

    def as_record(self) -> dict[str, Any]:
        return _record(self)

@dataclass(frozen=True)
class VisualRLEpisode:
    episode_id: str
    agent_id: str
    env_id: str
    mean_reward: float = 0.0
    success_rate: float = 0.0
    safety_violation_rate: float = 0.0
    policy: str = "local_tabular"
    provenance: str = "live"
    source_event_id: str = ""

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class VisualSafetyGate:
    gate_id: str
    agent_id: str
    decision: str
    risk_level: str = "low"
    requires_approval: bool = False
    reason: str = ""
    provenance: str = "live"
    source_event_id: str = ""

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class VisualAuditTrailItem:
    audit_id: str
    event_type: str
    actor_id: str
    summary: str
    ok: bool = True
    provenance: str = "live"
    source_event_id: str = ""

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class VisualRuntimeHealth:
    status: str = "ok"
    agents: int = 0
    tasks: int = 0
    events: int = 0
    warnings: tuple[str, ...] = ()
    ignored_regressions: tuple[str, ...] = ()

    def as_record(self) -> dict[str, Any]:
        return _record(self)


@dataclass(frozen=True)
class VisualNetworkState:
    agents: tuple[VisualAgentNode, ...] = ()
    tasks: tuple[VisualTaskNode, ...] = ()
    memory: tuple[VisualMemoryNode, ...] = ()
    economy: tuple[VisualEconomyEdge, ...] = ()
    neural: tuple[VisualNeuralSignal, ...] = ()
    compute: tuple[VisualComputeMarketSignal, ...] = ()
    rl: tuple[VisualRLEpisode, ...] = ()
    safety: tuple[VisualSafetyGate, ...] = ()
    audit: tuple[VisualAuditTrailItem, ...] = ()
    runtime: VisualRuntimeHealth = field(default_factory=VisualRuntimeHealth)
    schema_version: str = VISUAL_SCHEMA_VERSION
    provenance: str = "live"

    def as_record(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "provenance": self.provenance,
            "runtime": self.runtime.as_record(),
            "agents": tuple(item.as_record() for item in self.agents),
            "tasks": tuple(item.as_record() for item in self.tasks),
            "memory": tuple(item.as_record() for item in self.memory),
            "economy": tuple(item.as_record() for item in self.economy),
            "neural": tuple(item.as_record() for item in self.neural),
            "rl": tuple(item.as_record() for item in self.rl),
            "compute": tuple(item.as_record() for item in self.compute),
            "safety": tuple(item.as_record() for item in self.safety),
            "audit": tuple(item.as_record() for item in self.audit),
        }


def _record(item: object) -> dict[str, Any]:
    return dict(getattr(item, "__dict__"))
