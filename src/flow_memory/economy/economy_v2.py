"""Local/offline Agent Economy v2 marketplace primitives."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

from flow_memory.core.types import new_id, utc_now
from flow_memory.economy.attestations import Attestation
from flow_memory.economy.dispute import DisputeBook, DisputeCase
from flow_memory.economy.escrow import EscrowAccount, LocalEscrow
from flow_memory.economy.reputation import NonTransferableReputation


@dataclass(frozen=True)
class EconomyTask:
    task_id: str
    requester: str
    title: str
    reward: float
    status: str = "open"
    metadata: Mapping[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)

    def as_record(self) -> Mapping[str, Any]:
        return {
            "task_id": self.task_id,
            "requester": self.requester,
            "title": self.title,
            "reward": self.reward,
            "status": self.status,
            "metadata": dict(self.metadata),
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True)
class EconomyBid:
    bid_id: str
    task_id: str
    agent_did: str
    price: float
    status: str = "open"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_record(self) -> Mapping[str, Any]:
        return {
            "bid_id": self.bid_id,
            "task_id": self.task_id,
            "agent_did": self.agent_did,
            "price": self.price,
            "status": self.status,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class WorkSubmission:
    submission_id: str
    task_id: str
    agent_did: str
    artifact: Mapping[str, Any]
    status: str = "submitted"
    submitted_at: datetime = field(default_factory=utc_now)
    verified_by: str | None = None
    verified_at: datetime | None = None

    def as_record(self) -> Mapping[str, Any]:
        return {
            "submission_id": self.submission_id,
            "task_id": self.task_id,
            "agent_did": self.agent_did,
            "artifact": dict(self.artifact),
            "status": self.status,
            "submitted_at": self.submitted_at.isoformat(),
            "verified_by": self.verified_by,
            "verified_at": self.verified_at.isoformat() if self.verified_at is not None else None,
        }


@dataclass
class AgentEconomyV2:
    """Deterministic in-memory marketplace for local/offline agent economy tests."""

    tasks: dict[str, EconomyTask] = field(default_factory=dict)
    bids: dict[str, list[EconomyBid]] = field(default_factory=dict)
    assignments: dict[str, str] = field(default_factory=dict)
    submissions: dict[str, WorkSubmission] = field(default_factory=dict)
    submission_index: dict[str, str] = field(default_factory=dict)
    attestations: list[Attestation] = field(default_factory=list)
    disputes: DisputeBook = field(default_factory=DisputeBook)
    escrow: LocalEscrow = field(default_factory=LocalEscrow)
    reputations: dict[str, NonTransferableReputation] = field(default_factory=dict)
    settlements: dict[str, Mapping[str, Any]] = field(default_factory=dict)
    audit_log: list[Mapping[str, Any]] = field(default_factory=list)

    def _audit(self, action: str, **fields: Any) -> None:
        self.audit_log.append({"action": action, "at": utc_now().isoformat(), **fields})

    def reputation_for(self, agent_did: str) -> NonTransferableReputation:
        reputation = self.reputations.get(agent_did)
        if reputation is None:
            reputation = NonTransferableReputation()
            self.reputations[agent_did] = reputation
        return reputation

    def create_task(
        self,
        requester: str,
        title: str,
        reward: float,
        metadata: Mapping[str, Any] | None = None,
    ) -> EconomyTask:
        if reward < 0:
            raise ValueError("Reward must be non-negative")
        task = EconomyTask(
            task_id=new_id("task"),
            requester=requester,
            title=title,
            reward=reward,
            metadata=dict(metadata or {}),
        )
        self.tasks[task.task_id] = task
        self.bids[task.task_id] = []
        self._audit("task_created", task_id=task.task_id, requester=requester, reward=reward)
        return task

    def place_bid(
        self,
        task_id: str,
        agent_did: str,
        price: float,
        metadata: Mapping[str, Any] | None = None,
    ) -> EconomyBid:
        task = self._task(task_id)
        if task.status != "open":
            raise ValueError(f"Task is not open: {task_id}")
        if price < 0:
            raise ValueError("Bid price must be non-negative")
        bid = EconomyBid(
            bid_id=new_id("bid"),
            task_id=task_id,
            agent_did=agent_did,
            price=price,
            metadata=dict(metadata or {}),
        )
        self.bids[task_id].append(bid)
        self._audit("bid_placed", task_id=task_id, bid_id=bid.bid_id, agent_did=agent_did, price=price)
        return bid

    def assign(self, task_id: str, bid_id: str, actor: str) -> EconomyTask:
        task = self._task(task_id)
        if actor != task.requester:
            raise PermissionError("Only the requester can assign the task")
        if task.status != "open":
            raise ValueError(f"Task is not open: {task_id}")
        self._bid(task_id, bid_id)
        assigned = self._replace_task(task, status="assigned")
        self.assignments[task_id] = bid_id
        self._audit("task_assigned", task_id=task_id, bid_id=bid_id, actor=actor)
        return assigned

    def fund_escrow(self, task_id: str, actor: str) -> EscrowAccount:
        task = self._task(task_id)
        if actor != task.requester:
            raise PermissionError("Only the requester can fund escrow")
        if task.status != "assigned":
            raise ValueError(f"Task is not assigned: {task_id}")
        bid = self._assigned_bid(task_id)
        escrow = self.escrow.fund(task_id, payer=task.requester, payee=bid.agent_did, amount=task.reward)
        self._replace_task(task, status="escrowed")
        self._audit("escrow_funded", task_id=task_id, escrow_id=escrow.escrow_id, amount=escrow.amount)
        return escrow

    def submit_work(self, task_id: str, agent_did: str, artifact: Mapping[str, Any]) -> WorkSubmission:
        task = self._task(task_id)
        if task.status != "escrowed":
            raise ValueError(f"Task is not escrowed: {task_id}")
        bid = self._assigned_bid(task_id)
        if agent_did != bid.agent_did:
            raise PermissionError("Only the assigned agent can submit work")
        if task_id in self.submission_index:
            raise ValueError(f"Task already has a submission: {task_id}")
        submission = WorkSubmission(
            submission_id=new_id("submission"),
            task_id=task_id,
            agent_did=agent_did,
            artifact=dict(artifact),
        )
        self.submissions[submission.submission_id] = submission
        self.submission_index[task_id] = submission.submission_id
        self._replace_task(task, status="submitted")
        attestation = Attestation(
            issuer=agent_did,
            subject=task_id,
            claim="work_submitted",
            evidence={"submission_id": submission.submission_id},
        )
        self.attestations.append(attestation)
        self._audit("work_submitted", task_id=task_id, submission_id=submission.submission_id, agent_did=agent_did)
        return submission

    def verify_work(self, task_id: str, actor: str, accepted: bool, notes: str = "") -> WorkSubmission:
        task = self._task(task_id)
        if actor != task.requester:
            raise PermissionError("Only the requester can verify work")
        if task.status != "submitted":
            raise ValueError(f"Task is not submitted: {task_id}")
        submission = self._submission_for_task(task_id)
        status = "verified" if accepted else "rejected"
        verified = WorkSubmission(
            submission_id=submission.submission_id,
            task_id=submission.task_id,
            agent_did=submission.agent_did,
            artifact=submission.artifact,
            status=status,
            submitted_at=submission.submitted_at,
            verified_by=actor,
            verified_at=utc_now(),
        )
        self.submissions[verified.submission_id] = verified
        self._replace_task(task, status=status)
        attestation = Attestation(
            issuer=actor,
            subject=task_id,
            claim="work_accepted" if accepted else "work_rejected",
            evidence={"submission_id": verified.submission_id, "notes": notes},
        )
        self.attestations.append(attestation)
        self._audit("work_verified", task_id=task_id, accepted=accepted, actor=actor, notes=notes)
        return verified

    def settle_task(self, task_id: str, actor: str) -> Mapping[str, Any]:
        task = self._task(task_id)
        if actor != task.requester:
            raise PermissionError("Only the requester can settle the task")
        if task_id in self.settlements:
            raise ValueError(f"Task already settled: {task_id}")
        if task.status != "verified":
            raise ValueError(f"Task is not verified: {task_id}")
        bid = self._assigned_bid(task_id)
        escrow = self.escrow.release(task_id, actor=actor)
        self.reputation_for(bid.agent_did).record({"task_id": task_id, "event": "settled_success"}, 5.0)
        self._replace_task(task, status="settled")
        settlement = {
            "task_id": task_id,
            "status": "settled",
            "requester": task.requester,
            "assignee": bid.agent_did,
            "reward": task.reward,
            "escrow_id": escrow.escrow_id,
            "escrow_status": escrow.status,
            "reputation_delta": 5.0,
        }
        self.settlements[task_id] = settlement
        self._audit("task_settled", **settlement)
        return dict(settlement)

    def open_dispute(
        self,
        task_id: str,
        actor: str,
        reason: str,
        evidence: Mapping[str, Any] | None = None,
    ) -> DisputeCase:
        task = self._task(task_id)
        if actor != task.requester:
            raise PermissionError("Only the requester can dispute submitted work")
        if task.status != "rejected":
            raise ValueError(f"Task is not rejected: {task_id}")
        bid = self._assigned_bid(task_id)
        dispute = self.disputes.open_case(
            task_id=task_id,
            opened_by=actor,
            respondent=bid.agent_did,
            reason=reason,
            evidence=dict(evidence or {}),
        )
        self._replace_task(task, status="disputed")
        self._audit("dispute_opened", task_id=task_id, dispute_id=dispute.dispute_id, reason=reason)
        return dispute

    def resolve_dispute(self, dispute_id: str, actor: str, slash: bool) -> Mapping[str, Any]:
        case = self.disputes.cases.get(dispute_id)
        if case is None:
            raise KeyError(f"Unknown dispute: {dispute_id}")
        task = self._task(case.task_id)
        if actor != task.requester:
            raise PermissionError("Only the requester can resolve the dispute")
        if case.task_id in self.settlements:
            raise ValueError(f"Task already settled: {case.task_id}")
        if task.status != "disputed":
            raise ValueError(f"Task is not disputed: {case.task_id}")
        bid = self._assigned_bid(case.task_id)
        resolution = "requester_upheld" if slash else "agent_upheld"
        resolved = self.disputes.resolve(dispute_id, resolution=resolution)
        if slash:
            escrow = self.escrow.refund(case.task_id, actor=actor)
            reputation_delta = -10.0
            final_status = "slashed"
        else:
            escrow = self.escrow.release(case.task_id, actor=actor)
            reputation_delta = 1.0
            final_status = "settled"
        self.reputation_for(bid.agent_did).record(
            {"task_id": case.task_id, "event": final_status, "dispute_id": dispute_id},
            reputation_delta,
        )
        self._replace_task(task, status=final_status)
        settlement = {
            "task_id": case.task_id,
            "status": final_status,
            "requester": task.requester,
            "assignee": bid.agent_did,
            "reward": task.reward,
            "escrow_id": escrow.escrow_id,
            "escrow_status": escrow.status,
            "dispute_id": resolved.dispute_id,
            "dispute_resolution": resolved.resolution,
            "reputation_delta": reputation_delta,
        }
        self.settlements[case.task_id] = settlement
        self._audit("dispute_resolved", **settlement)
        return dict(settlement)

    def _task(self, task_id: str) -> EconomyTask:
        task = self.tasks.get(task_id)
        if task is None:
            raise KeyError(f"Unknown task: {task_id}")
        return task

    def _bid(self, task_id: str, bid_id: str) -> EconomyBid:
        for bid in self.bids.get(task_id, []):
            if bid.bid_id == bid_id:
                return bid
        raise KeyError(f"Unknown bid: {bid_id}")

    def _assigned_bid(self, task_id: str) -> EconomyBid:
        bid_id = self.assignments.get(task_id)
        if bid_id is None:
            raise ValueError(f"Task is not assigned: {task_id}")
        return self._bid(task_id, bid_id)

    def _submission_for_task(self, task_id: str) -> WorkSubmission:
        submission_id = self.submission_index.get(task_id)
        if submission_id is None:
            raise KeyError(f"Task has no submission: {task_id}")
        return self.submissions[submission_id]

    def _replace_task(self, task: EconomyTask, status: str) -> EconomyTask:
        updated = EconomyTask(
            task_id=task.task_id,
            requester=task.requester,
            title=task.title,
            reward=task.reward,
            status=status,
            metadata=task.metadata,
            created_at=task.created_at,
        )
        self.tasks[task.task_id] = updated
        return updated
