"""Local blockchain/testnet adapter.

This module provides deterministic receipt objects for tests and offline demos. Web3
adapters can implement the same methods and return compatible receipts.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

from flow_memory.core.types import new_id


@dataclass(frozen=True)
class OnChainReceipt:
    tx_hash: str
    status: str
    block_number: int
    events: tuple[Mapping[str, Any], ...]

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "tx_hash": self.tx_hash,
            "status": self.status,
            "block_number": self.block_number,
            "events": [dict(event) for event in self.events],
        }


@dataclass
class LocalSettlementChain:
    """In-memory chain emulator for identity, escrow, and reputation tests."""

    block_number: int = 0
    receipts: list[OnChainReceipt] = field(default_factory=list)
    registry: dict[str, Mapping[str, Any]] = field(default_factory=dict)
    reputation: dict[str, float] = field(default_factory=dict)

    def _mine(self, kind: str, payload: Mapping[str, Any]) -> OnChainReceipt:
        self.block_number += 1
        event = {"kind": kind, **dict(payload), "timestamp": datetime.now(timezone.utc).isoformat()}
        tx_hash = "0x" + hashlib.sha256(json.dumps(event, sort_keys=True).encode("utf-8")).hexdigest()
        receipt = OnChainReceipt(tx_hash=tx_hash, status="success", block_number=self.block_number, events=(event,))
        self.receipts.append(receipt)
        return receipt

    def register_agent(self, did: str, manifest_uri: str, owner: str) -> OnChainReceipt:
        agent_id = new_id("agent")
        self.registry[agent_id] = {"agent_id": agent_id, "did": did, "manifest_uri": manifest_uri, "owner": owner, "active": True}
        return self._mine("AgentRegistered", self.registry[agent_id])

    def apply_reputation_delta(self, agent: str, delta: float, evidence_hash: str) -> OnChainReceipt:
        self.reputation[agent] = self.reputation.get(agent, 0.0) + delta
        return self._mine(
            "ReputationChanged",
            {"agent": agent, "delta": delta, "new_score": self.reputation[agent], "evidence_hash": evidence_hash},
        )
