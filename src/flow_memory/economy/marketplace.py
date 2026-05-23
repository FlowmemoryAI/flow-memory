"""Task marketplace and escrow models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from flow_memory.core.types import new_id


@dataclass(frozen=True)
class Task:
    task_id: str
    title: str
    reward: float
    requester: str
    status: str = "open"
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Bid:
    bid_id: str
    task_id: str
    agent_did: str
    price: float
    status: str = "open"



@dataclass(frozen=True)
class Settlement:
    task_id: str
    title: str
    requester: str
    reward: float
    bid_price: float
    assigned_bid: str
    assignee: str
    status: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_record(self) -> Mapping[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "reward": self.reward,
            "bid_price": self.bid_price,
            "requester": self.requester,
            "status": self.status,
            "assigned_bid": self.assigned_bid,
            "assignee": self.assignee,
            "metadata": dict(self.metadata),
        }

@dataclass
class TaskMarketplace:
    tasks: dict[str, Task] = field(default_factory=dict)
    bids: dict[str, list[Bid]] = field(default_factory=dict)
    assigned: dict[str, str] = field(default_factory=dict)
    settlements: dict[str, Settlement] = field(default_factory=dict)

    def post_task(self, title: str, reward: float, requester: str, metadata: Mapping[str, Any] | None = None) -> str:
        if reward < 0:
            raise ValueError("Reward must be non-negative")
        task_id = new_id("task")
        self.tasks[task_id] = Task(task_id=task_id, title=title, reward=reward, requester=requester, metadata=dict(metadata or {}))
        self.bids[task_id] = []
        return task_id

    def bid(self, task_id: str, agent_did: str, price: float) -> str:
        if task_id not in self.tasks:
            raise KeyError(f"Unknown task: {task_id}")
        if price < 0:
            raise ValueError("Bid price must be non-negative")
        bid_id = new_id("bid")
        self.bids[task_id].append(Bid(bid_id=bid_id, task_id=task_id, agent_did=agent_did, price=price))
        return bid_id

    def _bid_by_id(self, task_id: str, bid_id: str) -> Bid:
        for bid in self.bids.get(task_id, []):
            if bid.bid_id == bid_id:
                return bid
        raise KeyError(f"Unknown bid: {bid_id}")

    def assign_lowest_bid(self, task_id: str) -> Task:
        """Assign the lowest open bid for a task.

        This is deterministic for local/offline tests: ties keep original bid order.
        Settlement still requires an explicit assignment and can only happen once.
        """
        if task_id not in self.tasks:
            raise KeyError(f"Unknown task: {task_id}")
        open_bids = [bid for bid in self.bids.get(task_id, []) if bid.status == "open"]
        if not open_bids:
            raise ValueError(f"Task has no open bids: {task_id}")
        lowest = min(open_bids, key=lambda bid: bid.price)
        return self.accept_bid(task_id, lowest.bid_id)


    def accept_bid(self, task_id: str, bid_id: str) -> Task:
        if task_id not in self.tasks:
            raise KeyError(f"Unknown task: {task_id}")
        self._bid_by_id(task_id, bid_id)
        task = self.tasks[task_id]
        accepted = Task(task_id=task.task_id, title=task.title, reward=task.reward, requester=task.requester, status="assigned", metadata=task.metadata)
        self.tasks[task_id] = accepted
        self.assigned[task_id] = bid_id
        return accepted

    def settle(self, task_id: str, success: bool) -> Mapping[str, Any]:
        if task_id not in self.tasks:
            raise KeyError(f"Unknown task: {task_id}")
        if task_id in self.settlements:
            raise ValueError(f"Task already settled: {task_id}")
        assigned_bid_id = self.assigned.get(task_id)
        if assigned_bid_id is None:
            raise ValueError(f"Task is not assigned: {task_id}")

        task = self.tasks[task_id]
        bid = self._bid_by_id(task_id, assigned_bid_id)
        status = "settled_success" if success else "settled_failure"
        self.tasks[task_id] = Task(task_id=task.task_id, title=task.title, reward=task.reward, requester=task.requester, status=status, metadata=task.metadata)
        settlement = Settlement(
            task_id=task_id,
            title=task.title,
            reward=task.reward,
            bid_price=bid.price,
            requester=task.requester,
            status=status,
            assigned_bid=assigned_bid_id,
            assignee=bid.agent_did,
            metadata=dict(task.metadata),
        )
        self.settlements[task_id] = settlement
        return settlement.as_record()
