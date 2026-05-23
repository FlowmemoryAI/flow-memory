"""In-memory public key registry for signature verification."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping

from flow_memory.crypto.asymmetric import PublicKeyRecord


@dataclass
class KeyRegistry:
    _records: dict[str, PublicKeyRecord] = field(default_factory=dict)

    @classmethod
    def from_records(cls, records: Iterable[PublicKeyRecord | Mapping[str, object]]) -> "KeyRegistry":
        registry = cls()
        for record in records:
            registry.register(record)
        return registry

    def register(self, record: PublicKeyRecord | Mapping[str, object]) -> PublicKeyRecord:
        normalized = normalize_public_key_record(record)
        self._records[normalized.key_id] = normalized
        return normalized

    def get(self, key_id: str) -> PublicKeyRecord | None:
        return self._records.get(key_id)

    def require(self, key_id: str) -> PublicKeyRecord:
        record = self.get(key_id)
        if record is None:
            raise KeyError(key_id)
        return record

    def as_records(self) -> tuple[Mapping[str, object], ...]:
        return tuple(record.as_record() for record in self._records.values())


def normalize_public_key_record(record: PublicKeyRecord | Mapping[str, object]) -> PublicKeyRecord:
    if isinstance(record, PublicKeyRecord):
        return record
    return PublicKeyRecord(
        key_id=str(record.get("key_id", "")),
        algorithm=str(record.get("algorithm", "")),
        public_key=str(record.get("public_key", "")),
        local_only=bool(record.get("local_only", False)),
    )
