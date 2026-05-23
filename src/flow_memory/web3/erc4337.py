"""ERC-4337 account abstraction seam."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class UserOperationDraft:
    sender: str
    call_data: str
    call_gas_limit: int = 0

    def as_record(self) -> Mapping[str, object]:
        return {"sender": self.sender, "callData": self.call_data, "callGasLimit": self.call_gas_limit, "dryRun": True}
