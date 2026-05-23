"""Signature policy for local demo and public-alpha/testnet contexts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from flow_memory.crypto.asymmetric import DEV_HMAC_ALGORITHM, ED25519_ALGORITHM, LOCAL_TEST_ASYMMETRIC_ALGORITHM

LOCAL_DEMO_CONTEXTS = frozenset({"local", "demo", "dev", "development", "test"})
PUBLIC_ALPHA_CONTEXTS = frozenset({"public-alpha", "public_alpha", "testnet", "base-sepolia", "base_sepolia"})
ASYMMETRIC_ALGORITHMS = frozenset({ED25519_ALGORITHM, LOCAL_TEST_ASYMMETRIC_ALGORITHM})


@dataclass(frozen=True)
class SignaturePolicyDecision:
    ok: bool
    reason: str
    context: str
    algorithm: str

    def as_record(self) -> Mapping[str, object]:
        return {"ok": self.ok, "reason": self.reason, "context": self.context, "algorithm": self.algorithm}


@dataclass(frozen=True)
class SignaturePolicy:
    context: str
    allow_local_test_asymmetric: bool = True

    def evaluate_algorithm(self, algorithm: str) -> SignaturePolicyDecision:
        context = self.context.lower()
        normalized_algorithm = algorithm.lower()
        if normalized_algorithm == DEV_HMAC_ALGORITHM:
            if context in LOCAL_DEMO_CONTEXTS:
                return SignaturePolicyDecision(True, "dev_hmac allowed for local/demo only", context, normalized_algorithm)
            return SignaturePolicyDecision(False, "dev_hmac is local/demo only", context, normalized_algorithm)
        if normalized_algorithm == LOCAL_TEST_ASYMMETRIC_ALGORITHM and not self.allow_local_test_asymmetric:
            return SignaturePolicyDecision(False, "local test asymmetric signer disabled", context, normalized_algorithm)
        if normalized_algorithm in ASYMMETRIC_ALGORITHMS:
            return SignaturePolicyDecision(True, "asymmetric signature accepted", context, normalized_algorithm)
        if context in PUBLIC_ALPHA_CONTEXTS:
            return SignaturePolicyDecision(False, "public-alpha/testnet requires asymmetric signatures", context, normalized_algorithm)
        return SignaturePolicyDecision(False, "unknown signature algorithm", context, normalized_algorithm)


def evaluate_signature_policy(context: str, algorithm: str) -> SignaturePolicyDecision:
    return SignaturePolicy(context=context).evaluate_algorithm(algorithm)


def public_alpha_policy() -> SignaturePolicy:
    return SignaturePolicy(context="public-alpha")
