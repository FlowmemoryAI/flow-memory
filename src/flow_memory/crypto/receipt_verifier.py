"""Receipt signature verification helpers."""

from __future__ import annotations

from typing import Any, Mapping

from flow_memory.crypto.asymmetric import (
    ED25519_ALGORITHM,
    LOCAL_TEST_ASYMMETRIC_ALGORITHM,
    LocalTestVerifier,
    SignatureEnvelope,
    VerificationResult,
)
from flow_memory.crypto.ed25519 import Ed25519Verifier
from flow_memory.crypto.key_registry import KeyRegistry
from flow_memory.crypto.signature_policy import SignaturePolicy


def verify_receipt_signature(
    receipt: Any,
    signature: SignatureEnvelope | Mapping[str, str],
    registry: KeyRegistry,
    policy: SignaturePolicy,
) -> VerificationResult:
    record = signature.as_record() if isinstance(signature, SignatureEnvelope) else dict(signature)
    algorithm = str(record.get("algorithm", ""))
    policy_decision = policy.evaluate_algorithm(algorithm)
    if not policy_decision.ok:
        return VerificationResult(False, policy_decision.reason, str(record.get("key_id", "")), algorithm)
    key_id = str(record.get("key_id", ""))
    public = registry.get(key_id)
    if public is None:
        return VerificationResult(False, "unknown key", key_id, algorithm)
    if public.algorithm != algorithm:
        return VerificationResult(False, "registered algorithm mismatch", key_id, public.algorithm)
    if algorithm == LOCAL_TEST_ASYMMETRIC_ALGORITHM:
        return LocalTestVerifier(public).verify(receipt, record)
    if algorithm == ED25519_ALGORITHM:
        return Ed25519Verifier(public).verify(receipt, record)
    return VerificationResult(False, "unsupported verifier algorithm", key_id, algorithm)
