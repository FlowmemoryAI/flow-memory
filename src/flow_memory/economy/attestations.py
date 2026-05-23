"""Local/offline attestations for Agent Economy v2."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

from flow_memory.core.types import new_id, utc_now


@dataclass(frozen=True)
class Attestation:
    """A local, unsigned claim about task work or settlement.

    This deliberately does not model cryptographic signatures or deployed credentials.
    The issuer is a local DID/string and the payload is an immutable snapshot for tests,
    audit logs, and offline simulations.
    """

    issuer: str
    subject: str
    claim: str
    evidence: Mapping[str, Any] = field(default_factory=dict)
    attestation_id: str = field(default_factory=lambda: new_id("attestation"))
    issued_at: datetime = field(default_factory=utc_now)

    def as_record(self) -> Mapping[str, Any]:
        return {
            "attestation_id": self.attestation_id,
            "issuer": self.issuer,
            "subject": self.subject,
            "claim": self.claim,
            "evidence": dict(self.evidence),
            "issued_at": self.issued_at.isoformat(),
        }
