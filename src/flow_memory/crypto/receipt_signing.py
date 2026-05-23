"""Receipt signing helpers."""

from __future__ import annotations

from typing import Any

from flow_memory.crypto.keys import LocalKeyPair
from flow_memory.crypto.signatures import SignatureEnvelope, sign_payload, verify_payload


def sign_receipt(receipt: Any, key: LocalKeyPair) -> SignatureEnvelope:
    return sign_payload(receipt, key)


def verify_receipt(receipt: Any, signature: SignatureEnvelope, key: LocalKeyPair) -> bool:
    return verify_payload(receipt, signature, key)
