"""Manifest signing helpers."""

from __future__ import annotations

from typing import Any

from flow_memory.crypto.keys import LocalKeyPair
from flow_memory.crypto.signatures import SignatureEnvelope, sign_payload, verify_payload


def sign_manifest(manifest: Any, key: LocalKeyPair) -> SignatureEnvelope:
    return sign_payload(manifest, key)


def verify_manifest(manifest: Any, signature: SignatureEnvelope, key: LocalKeyPair) -> bool:
    return verify_payload(manifest, signature, key)
