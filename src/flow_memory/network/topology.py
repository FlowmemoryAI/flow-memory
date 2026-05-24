"""Local Flow Memory network topology."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from flow_memory.network.participants import LocalNetworkParticipant, participant


@dataclass(frozen=True)
class LocalNetworkTopology:
    participants: tuple[LocalNetworkParticipant, ...]

    def by_role(self, role: str) -> LocalNetworkParticipant:
        for item in self.participants:
            if item.role == role:
                return item
        raise KeyError(f"unknown local network role: {role}")

    def as_record(self) -> Mapping[str, object]:
        return {"participants": tuple(item.as_record() for item in self.participants)}


def default_topology() -> LocalNetworkTopology:
    return LocalNetworkTopology(
        participants=(
            participant("requester", did="did:flow:requester", name="Requester Agent", capabilities=("task_request", "fund_escrow"), reputation=5.0),
            participant("worker", did="did:flow:worker", name="Worker Agent", capabilities=("research", "safe_tool_use", "submit_work"), reputation=7.0),
            participant("verifier", did="did:flow:verifier", name="Verifier Agent", capabilities=("verify_work", "resolve_dispute"), reputation=8.0),
            participant("auditor", did="did:flow:auditor", name="Observer Auditor", capabilities=("audit", "observe"), reputation=6.0),
        )
    )
