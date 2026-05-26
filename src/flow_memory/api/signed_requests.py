"""Signed request seam for local API tests."""

from __future__ import annotations

from typing import Any, Mapping

from flow_memory.crypto.keys import LocalKeyPair
from flow_memory.crypto.signatures import sign_payload, verify_payload, SignatureEnvelope


def sign_request(method: str, path: str, payload: Mapping[str, Any], key: LocalKeyPair) -> SignatureEnvelope:
    return sign_payload({"method": method.upper(), "path": path, "payload": dict(payload)}, key)


def verify_request(method: str, path: str, payload: Mapping[str, Any], signature: SignatureEnvelope, key: LocalKeyPair) -> bool:
    return bool(verify_payload({"method": method.upper(), "path": path, "payload": dict(payload)}, signature, key))
