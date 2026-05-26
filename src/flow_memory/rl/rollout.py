"""Rollout storage for Flow Arena."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Mapping

@dataclass
class RolloutBuffer:
    observations: list[Mapping[str, Any]] = field(default_factory=list)
    actions: list[int] = field(default_factory=list)
    rewards: list[float] = field(default_factory=list)
    dones: list[bool] = field(default_factory=list)
    infos: list[Mapping[str, Any]] = field(default_factory=list)
    policy_decisions: list[Mapping[str, Any]] = field(default_factory=list)
    economy_receipts: list[Mapping[str, Any]] = field(default_factory=list)
    audit_event_ids: list[str] = field(default_factory=list)
    def add(
        self,
        observation: Mapping[str, Any],
        action: int,
        reward: float,
        done: bool,
        info: Mapping[str, Any],
        *,
        policy_decision: Mapping[str, Any] | None = None,
        economy_receipt: Mapping[str, Any] | None = None,
        audit_event_id: str = "",
    ) -> None:
        self.observations.append(dict(observation)); self.actions.append(action); self.rewards.append(float(reward)); self.dones.append(bool(done)); self.infos.append(dict(info))
        if policy_decision is not None: self.policy_decisions.append(dict(policy_decision))
        if economy_receipt is not None: self.economy_receipts.append(dict(economy_receipt))
        if audit_event_id: self.audit_event_ids.append(audit_event_id)
    @property
    def size(self) -> int:
        return len(self.actions)
    @property
    def total_reward(self)->float: return sum(self.rewards)
    def as_record(self) -> dict[str, Any]: return {"observations":tuple(self.observations),"actions":tuple(self.actions),"rewards":tuple(self.rewards),"dones":tuple(self.dones),"infos":tuple(self.infos),"policy_decisions":tuple(self.policy_decisions),"economy_receipts":tuple(self.economy_receipts),"audit_event_ids":tuple(self.audit_event_ids),"total_reward":self.total_reward}
