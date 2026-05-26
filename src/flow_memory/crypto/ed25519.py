"""Optional Ed25519 signer adapter.

No Ed25519 dependency is required by the base package. Callers can inspect
``ed25519_available`` or catch ``Ed25519UnavailableError`` when neither
``cryptography`` nor ``PyNaCl`` is installed.
"""

from __future__ import annotations

import base64
import hmac
from dataclasses import dataclass
from typing import Any, Mapping, cast

from flow_memory.crypto.asymmetric import ED25519_ALGORITHM, PublicKeyRecord, SignatureEnvelope, VerificationResult
from flow_memory.crypto.canonical_json import canonical_json_bytes, canonical_json_hash


class Ed25519UnavailableError(RuntimeError):
    """Raised when no supported Ed25519 backend is installed."""


def ed25519_available() -> bool:
    return _backend_name() != ""


def ed25519_unavailable_reason() -> str:
    if ed25519_available():
        return ""
    return "Ed25519 support requires optional dependency cryptography or PyNaCl"


def require_ed25519_backend() -> str:
    backend = _backend_name()
    if not backend:
        raise Ed25519UnavailableError(ed25519_unavailable_reason())
    return backend


@dataclass(frozen=True)
class Ed25519Signer:
    key_id: str
    private_key_bytes: bytes
    algorithm: str = ED25519_ALGORITHM

    @classmethod
    def from_private_key_bytes(cls, key_id: str, private_key_bytes: bytes) -> "Ed25519Signer":
        require_ed25519_backend()
        return cls(key_id=key_id, private_key_bytes=bytes(private_key_bytes))

    def public_key_bytes(self) -> bytes:
        backend = require_ed25519_backend()
        if backend == "cryptography":
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

            private_key = Ed25519PrivateKey.from_private_bytes(self.private_key_bytes)
            return cast(
                bytes,
                private_key.public_key().public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw,
                ),
            )
        from nacl.signing import SigningKey

        return bytes(SigningKey(self.private_key_bytes).verify_key)

    def public_key(self) -> str:
        return _b64url(self.public_key_bytes())

    def public_record(self) -> PublicKeyRecord:
        return PublicKeyRecord(key_id=self.key_id, algorithm=self.algorithm, public_key=self.public_key())

    def sign(self, payload: Any) -> SignatureEnvelope:
        message = canonical_json_bytes(payload)
        backend = require_ed25519_backend()
        if backend == "cryptography":
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

            signature = Ed25519PrivateKey.from_private_bytes(self.private_key_bytes).sign(message)
        else:
            from nacl.signing import SigningKey

            signature = bytes(SigningKey(self.private_key_bytes).sign(message).signature)
        return SignatureEnvelope(
            payload_hash=canonical_json_hash(payload),
            signature=_b64url(signature),
            key_id=self.key_id,
            algorithm=self.algorithm,
            public_key=self.public_key(),
        )


@dataclass(frozen=True)
class Ed25519Verifier:
    public: PublicKeyRecord

    @property
    def key_id(self) -> str:
        return str(self.public.key_id)

    @property
    def algorithm(self) -> str:
        return str(self.public.algorithm)

    def verify(self, payload: Any, envelope: SignatureEnvelope | Mapping[str, str]) -> VerificationResult:
        record = envelope.as_record() if isinstance(envelope, SignatureEnvelope) else dict(envelope)
        if record.get("algorithm") != ED25519_ALGORITHM or self.public.algorithm != ED25519_ALGORITHM:
            return VerificationResult(False, "algorithm mismatch", self.public.key_id, self.public.algorithm)
        if record.get("key_id") != self.public.key_id:
            return VerificationResult(False, "key_id mismatch", self.public.key_id, self.public.algorithm)
        if not hmac.compare_digest(str(record.get("public_key") or self.public.public_key), self.public.public_key):
            return VerificationResult(False, "public key mismatch", self.public.key_id, self.public.algorithm)
        if record.get("payload_hash") != canonical_json_hash(payload):
            return VerificationResult(False, "payload hash mismatch", self.public.key_id, self.public.algorithm)
        try:
            signature = _unb64url(str(record.get("signature", "")))
            public_key = _unb64url(self.public.public_key)
            backend = require_ed25519_backend()
            if backend == "cryptography":
                from cryptography.exceptions import InvalidSignature
                from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

                try:
                    Ed25519PublicKey.from_public_bytes(public_key).verify(signature, canonical_json_bytes(payload))
                except InvalidSignature:
                    return VerificationResult(False, "signature mismatch", self.public.key_id, self.public.algorithm)
            else:
                from nacl.exceptions import BadSignatureError
                from nacl.signing import VerifyKey

                try:
                    VerifyKey(public_key).verify(canonical_json_bytes(payload), signature)
                except BadSignatureError:
                    return VerificationResult(False, "signature mismatch", self.public.key_id, self.public.algorithm)
        except (Ed25519UnavailableError, ValueError):
            return VerificationResult(False, ed25519_unavailable_reason() or "invalid signature encoding", self.public.key_id, self.public.algorithm)
        return VerificationResult(True, key_id=self.public.key_id, algorithm=self.public.algorithm)


def _backend_name() -> str:
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: F401

        return "cryptography"
    except ImportError:
        pass
    try:
        from nacl.signing import SigningKey  # noqa: F401

        return "pynacl"
    except ImportError:
        return ""


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _unb64url(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))
