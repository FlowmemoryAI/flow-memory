"""Signed request seam for local API tests."""

from __future__ import annotations

from typing import Any, Mapping

from flow_memory.crypto.keys import LocalKeyPair
from flow_memory.crypto.signatures import sign_payload, verify_payload, SignatureEnvelope


def sign_request(
    method: str,
    path: str,
    payload: Mapping[str, Any],
    key: LocalKeyPair,
    *,
    nonce: str = "",
    timestamp: str = "",
) -> SignatureEnvelope:
    return sign_payload(_signed_request_payload(method, path, payload, nonce=nonce, timestamp=timestamp), key)


def verify_request(
    method: str,
    path: str,
    payload: Mapping[str, Any],
    signature: SignatureEnvelope,
    key: LocalKeyPair,
    *,
    nonce: str = "",
    timestamp: str = "",
) -> bool:
    return bool(verify_payload(_signed_request_payload(method, path, payload, nonce=nonce, timestamp=timestamp), signature, key))


def _signed_request_payload(
    method: str,
    path: str,
    payload: Mapping[str, Any],
    *,
    nonce: str = "",
    timestamp: str = "",
) -> dict[str, Any]:
    signed = {"method": method.upper(), "path": path, "payload": dict(payload)}
    if nonce:
        signed["nonce"] = nonce
    if timestamp:
        signed["timestamp"] = timestamp
    return signed
