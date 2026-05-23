"""DID signing seam using local development keys."""

from __future__ import annotations

from typing import Any

from flow_memory.crypto.keys import LocalKeyPair
from flow_memory.crypto.signatures import SignatureEnvelope, sign_payload, verify_payload


def sign_did_payload(did: str, payload: Any, key: LocalKeyPair) -> SignatureEnvelope:
    return sign_payload({"did": did, "payload": payload}, key)


def verify_did_payload(did: str, payload: Any, signature: SignatureEnvelope, key: LocalKeyPair) -> bool:
    return verify_payload({"did": did, "payload": payload}, signature, key)
