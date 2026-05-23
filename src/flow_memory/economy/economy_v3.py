"""Agent Economy V3 local/testnet-ready architecture prototype."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from flow_memory.core.types import new_id
from flow_memory.economy.reputation import NonTransferableReputation


@dataclass(frozen=True)
class EconomicRiskControls:
    max_spend_per_agent: float = 10.0
    max_escrow_exposure: float = 10.0
    max_slashing_exposure: float = 5.0
    allowed_task_categories: tuple[str, ...] = ("general",)
    blocked_counterparties: tuple[str, ...] = field(default_factory=tuple)
    min_reputation: float = 0.0
    approval_threshold: float = 5.0
    cooldown_after_failed_tasks: int = 0

    def permits(self, *, agent: str, amount: float, category: str, reputation: float) -> tuple[bool, str]:
        if agent in self.blocked_counterparties:
            return False, "blocked counterparty"
        if category not in self.allowed_task_categories:
            return False, "category not allowed"
        if amount > self.max_spend_per_agent or amount > self.max_escrow_exposure:
            return False, "amount exceeds risk budget"
        if reputation < self.min_reputation:
            return False, "reputation below threshold"
        return True, "permitted"


@dataclass(frozen=True)
class EconomyTaskV3:
    task_id: str
    requester: str
    title: str
    reward: float
    category: str = "general"
    status: str = "created"


@dataclass(frozen=True)
class EconomyBidV3:
    bid_id: str
    task_id: str
    agent: str
    price: float


@dataclass(frozen=True)
class WorkSubmissionV3:
    submission_id: str
    task_id: str
    agent: str
    artifact: Mapping[str, Any]
    signature: str = "local-signature-placeholder"


@dataclass(frozen=True)
class Receipt:
    receipt_id: str
    receipt_type: str
    task_id: str
    actor: str
    payload: Mapping[str, Any]

    def as_record(self) -> Mapping[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "receipt_type": self.receipt_type,
            "task_id": self.task_id,
            "actor": self.actor,
            "payload": dict(self.payload),
        }


TaskCreatedReceipt = Receipt
BidSubmittedReceipt = Receipt
TaskAssignedReceipt = Receipt
EscrowCreatedReceipt = Receipt
WorkSubmittedReceipt = Receipt
VerificationReceipt = Receipt
SettlementReceipt = Receipt
DisputeReceipt = Receipt
SlashingReceipt = Receipt
ReputationUpdateReceipt = Receipt


@dataclass
class EconomyV3:
    risk_controls: EconomicRiskControls = field(default_factory=EconomicRiskControls)
    tasks: dict[str, EconomyTaskV3] = field(default_factory=dict)
    bids: dict[str, list[EconomyBidV3]] = field(default_factory=dict)
    submissions: dict[str, WorkSubmissionV3] = field(default_factory=dict)
    reputations: dict[str, NonTransferableReputation] = field(default_factory=dict)
    receipts: list[Receipt] = field(default_factory=list)
    audit_log: list[Mapping[str, Any]] = field(default_factory=list)
    settled_tasks: set[str] = field(default_factory=set)
    memory_records: list[Mapping[str, Any]] = field(default_factory=list)

    def create_task(self, requester: str, title: str, reward: float, category: str = "general") -> EconomyTaskV3:
        task = EconomyTaskV3(new_id("taskv3"), requester, title, reward, category, "created")
        self.tasks[task.task_id] = task
        self.bids[task.task_id] = []
        self._receipt("task_created", task.task_id, requester, {"title": title, "reward": reward, "category": category})
        return task

    def publish_task(self, task_id: str) -> EconomyTaskV3:
        task = self._task(task_id)
        updated = EconomyTaskV3(task.task_id, task.requester, task.title, task.reward, task.category, "open")
        self.tasks[task_id] = updated
        return updated

    def discover_eligible_agents(self, task_id: str, candidates: tuple[str, ...]) -> tuple[str, ...]:
        task = self._task(task_id)
        eligible: list[str] = []
        for agent in candidates:
            reputation = self.reputation_for(agent).score
            ok, _ = self.risk_controls.permits(agent=agent, amount=task.reward, category=task.category, reputation=reputation)
            if ok:
                eligible.append(agent)
        return tuple(eligible)

    def submit_bid(self, task_id: str, agent: str, price: float) -> EconomyBidV3:
        task = self._task(task_id)
        ok, reason = self.risk_controls.permits(agent=agent, amount=price, category=task.category, reputation=self.reputation_for(agent).score)
        if not ok:
            raise PermissionError(reason)
        bid = EconomyBidV3(new_id("bidv3"), task_id, agent, price)
        self.bids.setdefault(task_id, []).append(bid)
        self._receipt("bid_submitted", task_id, agent, {"price": price})
        return bid

    def assign_task(self, task_id: str, bid_id: str, actor: str) -> EconomyTaskV3:
        task = self._task(task_id)
        if actor != task.requester:
            raise PermissionError("only requester can assign")
        bid = self._bid(task_id, bid_id)
        updated = EconomyTaskV3(task.task_id, task.requester, task.title, task.reward, task.category, "assigned")
        self.tasks[task_id] = updated
        self._receipt("task_assigned", task_id, actor, {"agent": bid.agent, "bid_id": bid_id})
        return updated

    def create_escrow(self, task_id: str, actor: str) -> Receipt:
        task = self._task(task_id)
        if actor != task.requester:
            raise PermissionError("only requester can fund escrow")
        return self._receipt("escrow_created", task_id, actor, {"amount": task.reward})

    def submit_work(self, task_id: str, agent: str, artifact: Mapping[str, Any]) -> WorkSubmissionV3:
        submission = WorkSubmissionV3(new_id("work"), task_id, agent, dict(artifact))
        self.submissions[task_id] = submission
        self._receipt("work_submitted", task_id, agent, {"submission_id": submission.submission_id, "signed": bool(submission.signature)})
        return submission

    def select_verifier(self, task_id: str, candidates: tuple[str, ...]) -> str:
        if not candidates:
            raise ValueError("verifier required")
        return sorted(candidates, key=lambda agent: self.reputation_for(agent).score, reverse=True)[0]

    def verify_work(self, task_id: str, verifier: str, accepted: bool) -> Receipt:
        status = "verified" if accepted else "rejected"
        return self._receipt("verification", task_id, verifier, {"status": status})

    def settle(self, task_id: str, actor: str) -> Receipt:
        task = self._task(task_id)
        if actor != task.requester:
            raise PermissionError("only requester can settle")
        if task_id in self.settled_tasks:
            raise ValueError("task already settled")
        bid = self.bids[task_id][0]
        self.settled_tasks.add(task_id)
        self.reputation_for(bid.agent).record({"task_id": task_id, "event": "settled"}, 5.0)
        self.memory_records.append({"kind": "economic_outcome", "task_id": task_id, "status": "settled"})
        self._receipt("reputation_update", task_id, bid.agent, {"delta": 5.0})
        return self._receipt("settlement", task_id, actor, {"status": "settled", "worker": bid.agent})

    def open_dispute(self, task_id: str, actor: str, reason: str) -> Receipt:
        return self._receipt("dispute", task_id, actor, {"status": "open", "reason": reason})

    def resolve_dispute(self, task_id: str, accused: str, actor: str, slash: bool = True) -> Receipt:
        if slash:
            self.reputation_for(accused).record({"task_id": task_id, "event": "slashed"}, -10.0)
            self.memory_records.append({"kind": "economic_outcome", "task_id": task_id, "status": "slashed"})
            self._receipt("slashing", task_id, accused, {"delta": -10.0})
        return self._receipt("dispute_resolved", task_id, actor, {"status": "resolved", "slashed": slash})

    def run_success_lifecycle(self, requester: str, worker: str, title: str, reward: float) -> Mapping[str, Any]:
        task = self.create_task(requester, title, reward)
        self.publish_task(task.task_id)
        self.submit_bid(task.task_id, worker, reward)
        self.assign_task(task.task_id, self.bids[task.task_id][0].bid_id, requester)
        self.create_escrow(task.task_id, requester)
        self.submit_work(task.task_id, worker, {"result": "completed"})
        verifier = self.select_verifier(task.task_id, (requester,))
        self.verify_work(task.task_id, verifier, True)
        settlement = self.settle(task.task_id, requester)
        return {"task_id": task.task_id, "status": "settled", "settlement": settlement.as_record(), "receipts": tuple(receipt.as_record() for receipt in self.receipts)}

    def run_failure_lifecycle(self, requester: str, worker: str, title: str, reward: float) -> Mapping[str, Any]:
        task = self.create_task(requester, title, reward)
        self.publish_task(task.task_id)
        bid = self.submit_bid(task.task_id, worker, reward)
        self.assign_task(task.task_id, bid.bid_id, requester)
        self.create_escrow(task.task_id, requester)
        self.submit_work(task.task_id, worker, {"result": "bad work"})
        self.verify_work(task.task_id, requester, False)
        self.open_dispute(task.task_id, requester, "bad work")
        resolved = self.resolve_dispute(task.task_id, worker, requester, slash=True)
        return {"task_id": task.task_id, "status": "slashed", "dispute": resolved.as_record(), "receipts": tuple(receipt.as_record() for receipt in self.receipts)}

    def reputation_for(self, agent: str) -> NonTransferableReputation:
        return self.reputations.setdefault(agent, NonTransferableReputation())

    def _task(self, task_id: str) -> EconomyTaskV3:
        if task_id not in self.tasks:
            raise KeyError(f"unknown task: {task_id}")
        return self.tasks[task_id]

    def _bid(self, task_id: str, bid_id: str) -> EconomyBidV3:
        for bid in self.bids.get(task_id, ()):  # tuple/list compatible
            if bid.bid_id == bid_id:
                return bid
        raise KeyError(f"unknown bid: {bid_id}")

    def _receipt(self, receipt_type: str, task_id: str, actor: str, payload: Mapping[str, Any]) -> Receipt:
        receipt = Receipt(new_id("receipt"), receipt_type, task_id, actor, dict(payload))
        self.receipts.append(receipt)
        self.audit_log.append(receipt.as_record())
        return receipt
