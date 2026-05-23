"""Signer interface and local asymmetric-signature seam.

The local test signer is deterministic and dependency-free so tests can exercise
asymmetric call paths without private keys or network access. It is not a
production cryptosystem; public-alpha/testnet policy accepts it only as a local
prototype seam unless a real adapter such as Ed25519 is configured.
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Mapping, Protocol, runtime_checkable

from flow_memory.crypto.canonical_json import canonical_json_bytes, canonical_json_hash

DEV_HMAC_ALGORITHM = "hmac-sha256-dev"
LOCAL_TEST_ASYMMETRIC_ALGORITHM = "flowmemory-local-test-asymmetric-v1"
ED25519_ALGORITHM = "ed25519"


@dataclass(frozen=True)
class SignatureEnvelope:
    payload_hash: str
    signature: str
    key_id: str
    algorithm: str = DEV_HMAC_ALGORITHM
    public_key: str = ""

    def as_record(self) -> Mapping[str, str]:
        record = {
            "payload_hash": self.payload_hash,
            "signature": self.signature,
            "key_id": self.key_id,
            "algorithm": self.algorithm,
        }
        if self.public_key:
            record["public_key"] = self.public_key
        return record


@dataclass(frozen=True)
class PublicKeyRecord:
    key_id: str
    algorithm: str
    public_key: str
    local_only: bool = False

    def as_record(self) -> Mapping[str, object]:
        return {
            "key_id": self.key_id,
            "algorithm": self.algorithm,
            "public_key": self.public_key,
            "local_only": self.local_only,
        }


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    reason: str = ""
    key_id: str = ""
    algorithm: str = ""

    def as_record(self) -> Mapping[str, object]:
        return {"ok": self.ok, "reason": self.reason, "key_id": self.key_id, "algorithm": self.algorithm}


@runtime_checkable
class Signer(Protocol):
    key_id: str
    algorithm: str

    def public_record(self) -> PublicKeyRecord:
        ...

    def sign(self, payload: Any) -> SignatureEnvelope:
        ...


@runtime_checkable
class Verifier(Protocol):
    key_id: str
    algorithm: str

    def verify(self, payload: Any, envelope: SignatureEnvelope | Mapping[str, str]) -> VerificationResult:
        ...


@dataclass(frozen=True)
class LocalTestSigner:
    """Dependency-free asymmetric seam for local tests only.

    The private seed only derives a stable public key. Signatures are computed
    from the public key and payload, making this useful for deterministic tamper
    tests but unsuitable for production authenticity.
    """

    key_id: str
    private_seed: str
    algorithm: str = LOCAL_TEST_ASYMMETRIC_ALGORITHM

    @property
    def public_key(self) -> str:
        return sha256(self.private_seed.encode("utf-8")).hexdigest()

    def public_record(self) -> PublicKeyRecord:
        return PublicKeyRecord(
            key_id=self.key_id,
            algorithm=self.algorithm,
            public_key=self.public_key,
            local_only=True,
        )

    def verifier(self) -> "LocalTestVerifier":
        return LocalTestVerifier(self.public_record())

    def sign(self, payload: Any) -> SignatureEnvelope:
        return SignatureEnvelope(
            payload_hash=canonical_json_hash(payload),
            signature=_local_test_signature(self.public_key, payload),
            key_id=self.key_id,
            algorithm=self.algorithm,
            public_key=self.public_key,
        )


@dataclass(frozen=True)
class LocalTestVerifier:
    public: PublicKeyRecord

    @property
    def key_id(self) -> str:
        return self.public.key_id

    @property
    def algorithm(self) -> str:
        return self.public.algorithm

    def verify(self, payload: Any, envelope: SignatureEnvelope | Mapping[str, str]) -> VerificationResult:
        record = envelope.as_record() if isinstance(envelope, SignatureEnvelope) else dict(envelope)
        if record.get("algorithm") != self.public.algorithm:
            return VerificationResult(False, "algorithm mismatch", self.public.key_id, self.public.algorithm)
        if record.get("key_id") != self.public.key_id:
            return VerificationResult(False, "key_id mismatch", self.public.key_id, self.public.algorithm)
        public_key = str(record.get("public_key") or self.public.public_key)
        if not hmac.compare_digest(public_key, self.public.public_key):
            return VerificationResult(False, "public key mismatch", self.public.key_id, self.public.algorithm)
        if record.get("payload_hash") != canonical_json_hash(payload):
            return VerificationResult(False, "payload hash mismatch", self.public.key_id, self.public.algorithm)
        expected = _local_test_signature(self.public.public_key, payload)
        if not hmac.compare_digest(str(record.get("signature", "")), expected):
            return VerificationResult(False, "signature mismatch", self.public.key_id, self.public.algorithm)
        return VerificationResult(True, key_id=self.public.key_id, algorithm=self.public.algorithm)


def normalize_signature(envelope: SignatureEnvelope | Mapping[str, str]) -> SignatureEnvelope:
    if isinstance(envelope, SignatureEnvelope):
        return envelope
    return SignatureEnvelope(
        payload_hash=str(envelope.get("payload_hash", "")),
        signature=str(envelope.get("signature", "")),
        key_id=str(envelope.get("key_id", "")),
        algorithm=str(envelope.get("algorithm", "")),
        public_key=str(envelope.get("public_key", "")),
    )


def _local_test_signature(public_key: str, payload: Any) -> str:
    digest = sha256()
    digest.update(b"flowmemory-local-test-asymmetric-v1\x00")
    digest.update(public_key.encode("ascii"))
    digest.update(b"\x00")
    digest.update(canonical_json_bytes(payload))
    return digest.hexdigest()
