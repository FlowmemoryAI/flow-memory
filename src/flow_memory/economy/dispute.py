"""Local dispute cases for Agent Economy v2."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

from flow_memory.core.types import new_id, utc_now


@dataclass(frozen=True)
class DisputeCase:
    dispute_id: str
    task_id: str
    opened_by: str
    respondent: str
    reason: str
    evidence: Mapping[str, Any] = field(default_factory=dict)
    status: str = "open"
    resolution: str | None = None
    opened_at: datetime = field(default_factory=utc_now)
    resolved_at: datetime | None = None

    def as_record(self) -> Mapping[str, Any]:
        return {
            "dispute_id": self.dispute_id,
            "task_id": self.task_id,
            "opened_by": self.opened_by,
            "respondent": self.respondent,
            "reason": self.reason,
            "evidence": dict(self.evidence),
            "status": self.status,
            "resolution": self.resolution,
            "opened_at": self.opened_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at is not None else None,
        }


@dataclass
class DisputeBook:
    cases: dict[str, DisputeCase] = field(default_factory=dict)
    task_index: dict[str, str] = field(default_factory=dict)

    def open_case(
        self,
        task_id: str,
        opened_by: str,
        respondent: str,
        reason: str,
        evidence: Mapping[str, Any] | None = None,
    ) -> DisputeCase:
        if task_id in self.task_index:
            raise ValueError(f"Task already has dispute: {task_id}")
        dispute = DisputeCase(
            dispute_id=new_id("dispute"),
            task_id=task_id,
            opened_by=opened_by,
            respondent=respondent,
            reason=reason,
            evidence=dict(evidence or {}),
        )
        self.cases[dispute.dispute_id] = dispute
        self.task_index[task_id] = dispute.dispute_id
        return dispute

    def for_task(self, task_id: str) -> DisputeCase:
        dispute_id = self.task_index.get(task_id)
        if dispute_id is None:
            raise KeyError(f"Task has no dispute: {task_id}")
        return self.cases[dispute_id]

    def resolve(self, dispute_id: str, resolution: str) -> DisputeCase:
        case = self.cases.get(dispute_id)
        if case is None:
            raise KeyError(f"Unknown dispute: {dispute_id}")
        if case.status != "open":
            raise ValueError(f"Dispute already resolved: {dispute_id}")
        resolved = DisputeCase(
            dispute_id=case.dispute_id,
            task_id=case.task_id,
            opened_by=case.opened_by,
            respondent=case.respondent,
            reason=case.reason,
            evidence=case.evidence,
            status="resolved",
            resolution=resolution,
            opened_at=case.opened_at,
            resolved_at=utc_now(),
        )
        self.cases[dispute_id] = resolved
        return resolved
