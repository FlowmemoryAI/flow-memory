"""Dependency-free local HMAC signatures."""

from __future__ import annotations

import hmac
from hashlib import sha256
from typing import Any, Mapping

from flow_memory.crypto.asymmetric import DEV_HMAC_ALGORITHM, SignatureEnvelope
from flow_memory.crypto.canonical_json import canonical_json_bytes
from flow_memory.crypto.hashes import content_hash
from flow_memory.crypto.keys import LocalKeyPair




def sign_payload(payload: Any, key: LocalKeyPair) -> SignatureEnvelope:
    payload_hash = content_hash(payload)
    signature = hmac.new(key.secret.encode("utf-8"), canonical_json_bytes(payload), sha256).hexdigest()
    return SignatureEnvelope(payload_hash=payload_hash, signature=signature, key_id=key.key_id, algorithm=DEV_HMAC_ALGORITHM)


def verify_payload(payload: Any, envelope: SignatureEnvelope | Mapping[str, str], key: LocalKeyPair) -> bool:
    record = envelope.as_record() if isinstance(envelope, SignatureEnvelope) else dict(envelope)
    if record.get("algorithm") != DEV_HMAC_ALGORITHM or record.get("key_id") != key.key_id:
        return False
    if record.get("payload_hash") != content_hash(payload):
        return False
    expected = sign_payload(payload, key).signature
    return hmac.compare_digest(str(record.get("signature", "")), expected)
