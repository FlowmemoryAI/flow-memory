"""Sandbox execution receipts."""

from dataclasses import dataclass
from typing import Mapping

from flow_memory.core.types import new_id


@dataclass(frozen=True)
class SandboxReceipt:
    status: str
    profile_hash: str
    output_size: int = 0
    receipt_id: str = ""

    def as_record(self) -> Mapping[str, object]:
        return {"receipt_id": self.receipt_id or new_id("sandbox_receipt"), "status": self.status, "profile_hash": self.profile_hash, "output_size": self.output_size}
