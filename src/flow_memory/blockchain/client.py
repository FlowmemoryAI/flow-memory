"""Blockchain client seams for identity and settlement."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from flow_memory.core.types import new_id


@dataclass(frozen=True)
class ContractCall:
    contract: str
    method: str
    args: Mapping[str, Any]
    call_id: str = field(default_factory=lambda: new_id("call"))


@dataclass
class LocalChainLedger:
    """Deterministic local ledger for tests and offline development."""

    events: list[Mapping[str, Any]] = field(default_factory=list)

    def submit(self, call: ContractCall) -> Mapping[str, Any]:
        event = {
            "tx_id": new_id("tx"),
            "contract": call.contract,
            "method": call.method,
            "args": dict(call.args),
            "status": "accepted_local",
        }
        self.events.append(event)
        return event

    def history(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(self.events)
