"""Economic autonomy layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from flow_memory.core.types import ActionResult, Plan
from flow_memory.economy.identity import DID
from flow_memory.economy.marketplace import TaskMarketplace
from flow_memory.economy.reputation import NonTransferableReputation
from flow_memory.economy.treasury import AgentTreasury
from flow_memory.economy.wallet import SmartWallet


@dataclass
class EconomicLayer:
    """Composes identity, wallet, reputation, marketplace, and treasury."""

    identity: DID = field(default_factory=DID)
    wallet: SmartWallet = field(default_factory=SmartWallet)
    reputation: NonTransferableReputation = field(default_factory=NonTransferableReputation)
    marketplace: TaskMarketplace = field(default_factory=TaskMarketplace)
    treasury: AgentTreasury = field(default_factory=AgentTreasury)

    def settle(self, plan: Plan, result: ActionResult) -> Mapping[str, Any]:
        total_value = sum(step.economic_value for step in plan.steps)
        if total_value <= 0:
            return {"settled": False, "reason": "no_economic_value"}
        if result.success:
            self.wallet.deposit(total_value)
            self.reputation.record({"plan_id": plan.plan_id, "result": "success"}, delta=1.0)
            return {"settled": True, "amount": total_value, "status": "credited", "wallet": self.wallet.address}
        self.reputation.record({"plan_id": plan.plan_id, "result": "failure"}, delta=-1.0)
        return {"settled": True, "amount": 0.0, "status": "no_credit", "wallet": self.wallet.address}

    def settle_marketplace_task(self, task_id: str, success: bool) -> Mapping[str, Any]:
        settlement = self.marketplace.settle(task_id, success=success)
        event = {
            "task_id": settlement["task_id"],
            "assigned_bid": settlement["assigned_bid"],
            "assignee": settlement["assignee"],
            "reward": settlement["reward"],
            "result": "success" if success else "failure",
        }
        if success:
            self.wallet.deposit(float(settlement["reward"]), reason=f"marketplace:{task_id}")
            self.reputation.record(event, delta=1.0)
            return dict(settlement, settled=True, amount=settlement["reward"], economic_status="credited", wallet=self.wallet.address)

        self.reputation.record(event, delta=-1.0)
        return dict(settlement, settled=True, amount=0.0, economic_status="slashed_reputation", wallet=self.wallet.address)


__all__ = [
    "AgentTreasury",
    "DID",
    "EconomicLayer",
    "NonTransferableReputation",
    "SmartWallet",
    "TaskMarketplace",
]
