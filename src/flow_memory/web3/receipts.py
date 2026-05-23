"""Web3 dry-run receipts."""

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class DryRunReceipt:
    status: str
    payload: Mapping[str, object]

    def as_record(self) -> Mapping[str, object]:
        return {"status": self.status, "payload": dict(self.payload)}
