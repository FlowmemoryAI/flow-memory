"""Economy V3 verification helpers."""

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class VerificationResult:
    task_id: str
    verifier: str
    accepted: bool
    evidence_hash: str = ""

    def as_record(self) -> Mapping[str, object]:
        return {"task_id": self.task_id, "verifier": self.verifier, "accepted": self.accepted, "evidence_hash": self.evidence_hash}
