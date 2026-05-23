"""Local delegation contract lifecycle."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from flow_memory.core.types import new_id


@dataclass(frozen=True)
class DelegationReceipt:
    contract_id: str
    status: str
    payload: Mapping[str, Any]

    def as_record(self) -> Mapping[str, Any]:
        return {"contract_id": self.contract_id, "status": self.status, "payload": dict(self.payload)}


@dataclass
class DelegationContract:
    """In-memory assign/complete/verify contract for local swarm work."""

    delegator_did: str
    delegate_did: str
    capability: str
    objective: str
    budget: float = 0.0
    constraints: Mapping[str, Any] = field(default_factory=dict)
    contract_id: str = field(default_factory=lambda: new_id("delegation"))
    status: str = "draft"
    assignment: Mapping[str, Any] = field(default_factory=dict)
    completion: Mapping[str, Any] = field(default_factory=dict)
    verification: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.delegator_did:
            raise ValueError("Delegator DID is required")
        if not self.delegate_did:
            raise ValueError("Delegate DID is required")
        if not self.capability:
            raise ValueError("Capability is required")
        if not self.objective:
            raise ValueError("Objective is required")
        if self.budget < 0:
            raise ValueError("Budget must be non-negative")

    def assign(self, payload: Mapping[str, Any] | None = None) -> DelegationReceipt:
        if self.status != "draft":
            raise ValueError(f"Cannot assign delegation in status: {self.status}")
        self.assignment = dict(payload or {})
        self.status = "assigned"
        return DelegationReceipt(self.contract_id, self.status, self.assignment)

    def complete(self, result: Mapping[str, Any]) -> DelegationReceipt:
        if self.status != "assigned":
            raise ValueError(f"Cannot complete delegation in status: {self.status}")
        self.completion = dict(result)
        self.status = "completed"
        return DelegationReceipt(self.contract_id, self.status, self.completion)

    def verify(self, accepted: bool, evidence: Mapping[str, Any] | None = None) -> DelegationReceipt:
        if self.status != "completed":
            raise ValueError(f"Cannot verify delegation in status: {self.status}")
        self.verification = {"accepted": accepted, "evidence": dict(evidence or {})}
        self.status = "verified" if accepted else "rejected"
        return DelegationReceipt(self.contract_id, self.status, self.verification)

    def as_record(self) -> Mapping[str, Any]:
        return {
            "contract_id": self.contract_id,
            "delegator_did": self.delegator_did,
            "delegate_did": self.delegate_did,
            "capability": self.capability,
            "objective": self.objective,
            "budget": self.budget,
            "constraints": dict(self.constraints),
            "status": self.status,
            "assignment": dict(self.assignment),
            "completion": dict(self.completion),
            "verification": dict(self.verification),
        }
