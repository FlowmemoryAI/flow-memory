"""Local multi-agent verification."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from flow_memory.core.types import new_id


@dataclass(frozen=True)
class VerificationVote:
    verifier_did: str
    accepted: bool
    evidence: Mapping[str, object] = field(default_factory=dict)
    vote_id: str = field(default_factory=lambda: new_id("vote"))


@dataclass
class MultiAgentVerifier:
    threshold: int = 1
    votes: dict[str, list[VerificationVote]] = field(default_factory=dict)

    def submit(self, task_id: str, vote: VerificationVote) -> Mapping[str, object]:
        self.votes.setdefault(task_id, []).append(vote)
        accepted = sum(1 for item in self.votes[task_id] if item.accepted)
        rejected = sum(1 for item in self.votes[task_id] if not item.accepted)
        return {"task_id": task_id, "accepted_votes": accepted, "rejected_votes": rejected, "accepted": accepted >= self.threshold}
