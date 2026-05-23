"""DID-to-public-key mapping helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from flow_memory.crypto.asymmetric import PublicKeyRecord
from flow_memory.crypto.key_registry import KeyRegistry, normalize_public_key_record


@dataclass(frozen=True)
class DidKeyBinding:
    did: str
    key_id: str

    def as_record(self) -> Mapping[str, str]:
        return {"did": self.did, "key_id": self.key_id}


@dataclass
class DidKeyMap:
    registry: KeyRegistry
    _bindings: dict[str, str]

    @classmethod
    def empty(cls) -> "DidKeyMap":
        return cls(registry=KeyRegistry(), _bindings={})

    @classmethod
    def from_records(cls, records: Mapping[str, PublicKeyRecord | Mapping[str, object]]) -> "DidKeyMap":
        did_map = cls.empty()
        for did, record in records.items():
            did_map.bind(did, record)
        return did_map

    def bind(self, did: str, record: PublicKeyRecord | Mapping[str, object]) -> DidKeyBinding:
        normalized = self.registry.register(normalize_public_key_record(record))
        self._bindings[did] = normalized.key_id
        return DidKeyBinding(did=did, key_id=normalized.key_id)

    def key_id_for_did(self, did: str) -> str | None:
        return self._bindings.get(did)

    def public_key_for_did(self, did: str) -> PublicKeyRecord | None:
        key_id = self.key_id_for_did(did)
        if key_id is None:
            return None
        return self.registry.get(key_id)

    def as_record(self) -> Mapping[str, object]:
        return {
            "bindings": {did: key_id for did, key_id in sorted(self._bindings.items())},
            "keys": self.registry.as_records(),
        }
