"""Local blockchain settlement simulator.

This module mirrors the shape of registry/reputation settlement without requiring a node.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class ChainReceipt:
    status: str
    block_number: int
    tx_hash: str
    event: Mapping[str, Any]


@dataclass
class LocalSettlementChain:
    block_number: int = 0
    agents: dict[str, Mapping[str, Any]] = field(default_factory=dict)
    reputation: dict[str, float] = field(default_factory=dict)

    def _receipt(self, event: Mapping[str, Any]) -> ChainReceipt:
        self.block_number += 1
        return ChainReceipt(
            status="success",
            block_number=self.block_number,
            tx_hash=f"0x{self.block_number:064x}",
            event=dict(event),
        )

    def register_agent(self, did: str, manifest_uri: str, owner: str) -> ChainReceipt:
        self.agents[did] = {"did": did, "manifest_uri": manifest_uri, "owner": owner, "active": True}
        return self._receipt({"kind": "AgentRegistered", "did": did, "owner": owner, "manifest_uri": manifest_uri})

    def apply_reputation_delta(self, agent: str, delta: float, evidence_hash: str) -> ChainReceipt:
        self.reputation[agent] = self.reputation.get(agent, 0.0) + delta
        return self._receipt(
            {"kind": "ReputationChanged", "agent": agent, "delta": delta, "evidence_hash": evidence_hash}
        )
