"""Blockchain adapter seams.

The default adapter is dry-run only. It creates typed transaction intents that can
be handed to web3.py, Foundry scripts, account-abstraction bundlers, or zk/TEE
verification services in production deployments.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from flow_memory.core.types import new_id


@dataclass(frozen=True)
class ContractIntent:
    """A typed, auditable blockchain operation intent."""

    contract: str
    function: str
    args: Mapping[str, Any]
    value: float = 0.0
    intent_id: str = field(default_factory=lambda: new_id("intent"))


@dataclass
class DryRunBlockchainAdapter:
    """Local adapter that records blockchain intents without broadcasting."""

    chain_id: int = 31337
    intents: list[ContractIntent] = field(default_factory=list)

    def register_agent(self, did: str, manifest_uri: str) -> ContractIntent:
        return self._record(
            ContractIntent(
                contract="AgentRegistry",
                function="register",
                args={"did": did, "manifestURI": manifest_uri},
            )
        )

    def open_task_escrow(self, spec_hash: str, reward: float) -> ContractIntent:
        return self._record(
            ContractIntent(
                contract="TaskEscrow",
                function="createTask",
                args={"specHash": spec_hash},
                value=reward,
            )
        )

    def settle_task(self, task_id: int, result_hash: str) -> ContractIntent:
        return self._record(
            ContractIntent(
                contract="TaskEscrow",
                function="settle",
                args={"taskId": task_id, "resultHash": result_hash},
            )
        )

    def apply_reputation_delta(self, agent: str, delta: int, evidence_hash: str) -> ContractIntent:
        return self._record(
            ContractIntent(
                contract="ReputationSBT",
                function="applyDelta",
                args={"agent": agent, "delta": delta, "evidenceHash": evidence_hash},
            )
        )

    def _record(self, intent: ContractIntent) -> ContractIntent:
        self.intents.append(intent)
        return intent
