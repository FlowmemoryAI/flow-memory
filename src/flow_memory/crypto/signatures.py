"""Dependency-free local HMAC signatures."""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Mapping

from flow_memory.crypto.hashes import canonical_json, content_hash
from flow_memory.crypto.keys import LocalKeyPair


@dataclass(frozen=True)
class SignatureEnvelope:
    payload_hash: str
    signature: str
    key_id: str
    algorithm: str = "hmac-sha256-dev"

    def as_record(self) -> Mapping[str, str]:
        return {"payload_hash": self.payload_hash, "signature": self.signature, "key_id": self.key_id, "algorithm": self.algorithm}


def sign_payload(payload: Any, key: LocalKeyPair) -> SignatureEnvelope:
    payload_hash = content_hash(payload)
    signature = hmac.new(key.secret.encode("utf-8"), canonical_json(payload).encode("utf-8"), sha256).hexdigest()
    return SignatureEnvelope(payload_hash=payload_hash, signature=signature, key_id=key.key_id)


def verify_payload(payload: Any, envelope: SignatureEnvelope | Mapping[str, str], key: LocalKeyPair) -> bool:
    record = envelope.as_record() if isinstance(envelope, SignatureEnvelope) else dict(envelope)
    if record.get("algorithm") != "hmac-sha256-dev" or record.get("key_id") != key.key_id:
        return False
    if record.get("payload_hash") != content_hash(payload):
        return False
    expected = sign_payload(payload, key).signature
    return hmac.compare_digest(record.get("signature", ""), expected)
