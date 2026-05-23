# Signed Manifests

## Purpose

Signed manifests provide a deterministic admission boundary for agent definitions, skills, permissions, plans, and economy declarations. Runtime components should be able to verify what was declared, which schema version it targets, and whether the artifact changed after approval.

## Implemented behavior

Status: implemented development helper; production signing seam.

- `flow_memory.ir.manifest` defines `ManifestEnvelope`, `ManifestSignature`, and `SignedManifestEnvelope`.
- `envelope_manifest(...)` wraps an `AgentSpec` or manifest mapping with `schema_version`, manifest payload, digest, and metadata.
- `manifest_digest(...)` computes a SHA-256 digest over deterministic canonical JSON.
- `sign_manifest(...)` creates a local `hmac-sha256-dev` signature over the envelope.
- `verify_manifest_signature(...)` validates the algorithm, digest consistency, and HMAC signature.

## Limitations

- The implemented signature algorithm is explicitly for local development integrity checks only.
- HMAC shared-secret signing is not a production custody or deployment-signing model.
- There is no key registry, rotation policy, revocation list, transparency log, hardware-backed key custody, or asymmetric verifier path.
- Runtime admission does not yet require signed envelopes everywhere.
- Contract registries accept hashes/URIs in prototypes, but they are unaudited and do not prove manifest safety.

## Next steps

- Replace development HMAC admission with asymmetric signatures at the hardened runtime boundary.
- Define key IDs, issuer identities, rotation, revocation, and audit-log anchoring.
- Require signed envelopes for FlowLang/FlowIR admission, skill registration, economy bids, and work attestations.
- Persist digest, schema version, signer, and verification result in durable storage.
- Add compatibility fixtures so canonical JSON and digest behavior remain stable across languages.
