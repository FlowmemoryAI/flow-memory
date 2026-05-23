"""Mutable agent runtime state."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


@dataclass
class AgentHealth:
    ok: bool = True
    status: str = "healthy"
    failures: int = 0
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def as_record(self) -> Mapping[str, Any]:
        return {"ok": self.ok, "status": self.status, "failures": self.failures, "warnings": tuple(self.warnings)}


@dataclass
class AgentState:
    lifecycle_status: str = "created"
    current_goal: str = ""
    current_plan: Mapping[str, Any] | None = None
    current_task_graph: Mapping[str, Any] | None = None
    working_memory_snapshot: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    recent_events: list[Mapping[str, Any]] = field(default_factory=list)
    outstanding_approvals: list[Mapping[str, Any]] = field(default_factory=list)
    open_marketplace_tasks: list[str] = field(default_factory=list)
    active_delegations: list[str] = field(default_factory=list)
    health: AgentHealth = field(default_factory=AgentHealth)
    last_evaluation: Mapping[str, Any] | None = None
    error_state: str = ""
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def add_event(self, event: Mapping[str, Any]) -> None:
        self.recent_events.append(dict(event))
        self.recent_events[:] = self.recent_events[-50:]
        self.updated_at = datetime.now(timezone.utc)

    def as_record(self) -> Mapping[str, Any]:
        return {
            "lifecycle_status": self.lifecycle_status,
            "current_goal": self.current_goal,
            "current_plan": dict(self.current_plan or {}),
            "current_task_graph": dict(self.current_task_graph or {}),
            "working_memory_snapshot": tuple(dict(item) for item in self.working_memory_snapshot),
            "recent_events": tuple(dict(event) for event in self.recent_events),
            "outstanding_approvals": tuple(dict(item) for item in self.outstanding_approvals),
            "open_marketplace_tasks": tuple(self.open_marketplace_tasks),
            "active_delegations": tuple(self.active_delegations),
            "health": self.health.as_record(),
            "last_evaluation": dict(self.last_evaluation or {}),
            "error_state": self.error_state,
            "updated_at": self.updated_at.isoformat(),
        }
