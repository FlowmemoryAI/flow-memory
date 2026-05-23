"""Versioned FlowIR manifest envelopes and local signature helpers.

The helpers in this module are deliberately dependency-free. They provide a
stable canonical JSON form, content digest, and local HMAC signature prototype
for development and CI. Production signing should use an asymmetric key system
implemented at the hardened runtime boundary.
"""

from __future__ import annotations

import hmac
import json
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Mapping

from flow_memory.ir.agent import AgentSpec

FLOWIR_SCHEMA_VERSION = "flowir/v0.1"
FLOWIR_SIGNATURE_ALGORITHM = "hmac-sha256-dev"


@dataclass(frozen=True)
class ManifestEnvelope:
    """Versioned, digest-addressed FlowIR manifest envelope."""

    schema_version: str
    manifest: Mapping[str, Any]
    digest: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def as_record(self) -> Mapping[str, Any]:
        return {
            "schema_version": self.schema_version,
            "manifest": _json_safe(self.manifest),
            "digest": self.digest,
            "metadata": dict(self.metadata),
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        return canonical_json(self.as_record(), indent=indent)


@dataclass(frozen=True)
class ManifestSignature:
    """Local development signature over a FlowIR manifest envelope."""

    algorithm: str
    digest: str
    signature: str
    key_id: str = "local-dev"

    def as_record(self) -> Mapping[str, Any]:
        return {
            "algorithm": self.algorithm,
            "digest": self.digest,
            "signature": self.signature,
            "key_id": self.key_id,
        }


@dataclass(frozen=True)
class SignedManifestEnvelope:
    """FlowIR manifest envelope plus a local development signature."""

    envelope: ManifestEnvelope
    signature: ManifestSignature

    def as_record(self) -> Mapping[str, Any]:
        return {
            "envelope": self.envelope.as_record(),
            "signature": self.signature.as_record(),
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        return canonical_json(self.as_record(), indent=indent)


def canonical_json(record: Mapping[str, Any], *, indent: int | None = None) -> str:
    """Return deterministic JSON for signing, hashing, and test snapshots."""

    return json.dumps(_json_safe(record), sort_keys=True, separators=(",", ":") if indent is None else None, indent=indent)


def manifest_digest(manifest: Mapping[str, Any]) -> str:
    """Return a stable SHA-256 digest for a JSON-serializable manifest."""

    return sha256(canonical_json(manifest).encode("utf-8")).hexdigest()


def envelope_manifest(agent_or_manifest: AgentSpec | Mapping[str, Any], *, metadata: Mapping[str, Any] | None = None) -> ManifestEnvelope:
    """Wrap an AgentSpec or manifest mapping in a versioned FlowIR envelope."""

    manifest = agent_or_manifest.as_manifest() if isinstance(agent_or_manifest, AgentSpec) else dict(agent_or_manifest)
    return ManifestEnvelope(
        schema_version=FLOWIR_SCHEMA_VERSION,
        manifest=manifest,
        digest=manifest_digest(manifest),
        metadata=dict(metadata or {}),
    )


def sign_manifest(
    agent_or_manifest: AgentSpec | Mapping[str, Any],
    secret: bytes | str,
    *,
    key_id: str = "local-dev",
    metadata: Mapping[str, Any] | None = None,
) -> SignedManifestEnvelope:
    """Create a local development HMAC signature over a FlowIR envelope.

    This is for deterministic local integrity checks only. It is not a
    production custody or deployment-signing scheme.
    """

    envelope = envelope_manifest(agent_or_manifest, metadata=metadata)
    key = secret.encode("utf-8") if isinstance(secret, str) else secret
    signature = hmac.new(key, canonical_json(envelope.as_record()).encode("utf-8"), sha256).hexdigest()
    return SignedManifestEnvelope(
        envelope=envelope,
        signature=ManifestSignature(
            algorithm=FLOWIR_SIGNATURE_ALGORITHM,
            digest=envelope.digest,
            signature=signature,
            key_id=key_id,
        ),
    )


def verify_manifest_signature(signed: SignedManifestEnvelope | Mapping[str, Any], secret: bytes | str) -> bool:
    """Verify a local development HMAC signature over a FlowIR envelope."""

    signed_record = signed.as_record() if isinstance(signed, SignedManifestEnvelope) else signed
    envelope_record = signed_record.get("envelope")
    signature_record = signed_record.get("signature")
    if not isinstance(envelope_record, Mapping) or not isinstance(signature_record, Mapping):
        return False
    if signature_record.get("algorithm") != FLOWIR_SIGNATURE_ALGORITHM:
        return False
    manifest = envelope_record.get("manifest")
    if not isinstance(manifest, Mapping):
        return False
    expected_digest = manifest_digest(manifest)
    if envelope_record.get("digest") != expected_digest or signature_record.get("digest") != expected_digest:
        return False
    key = secret.encode("utf-8") if isinstance(secret, str) else secret
    expected_signature = hmac.new(key, canonical_json(dict(envelope_record)).encode("utf-8"), sha256).hexdigest()
    return hmac.compare_digest(str(signature_record.get("signature", "")), expected_signature)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value
