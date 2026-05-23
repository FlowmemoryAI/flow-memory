# Flow Memory Roadmap

## Current public-alpha RC1 baseline

Implemented local/testnet-preflight prototype:

- AI agent layer
- FlowLang-to-runtime integration
- Economy V3 local lifecycles
- SQLite durable storage and audit replay JSONL
- local HMAC signing plus deterministic asymmetric/DID signing seams
- API server/auth/signed request/scope/error/rate-limit seams
- Base Sepolia/ERC-4337 dry-run artifact set
- sandbox profile/receipt interfaces plus optional Docker backend seam
- MCP/A2A/libp2p protocol seams
- typed dashboard mock API scaffold
- clean-clone validation and release evidence bundle
- adversarial economy simulation
- expanded contract security tests

## Next milestones

1. Replace local deterministic asymmetric signing with audited DID/account signing and key custody.
2. Add Rust FlowIR validator with full schema checks.
3. Implement Rust Wasm Component Model host for WIT skill ABI.
4. Wire Datalog policy inference into runtime policy decisions.
5. Promote Docker sandbox from optional seam to hardened isolated backend with platform-specific controls.
6. Run no-funds Base Sepolia deployment rehearsal with disposable reviewed keys after manual approval.
7. Add FastAPI integration tests behind optional dependency flag.
8. Add dashboard live read-only API integration and generated SDK.
9. Add contract threat model review and external audit preparation.
10. Build Neural Agent Layer v1 for optional PyTorch-backed perception/world-model/advisory scoring.

## Non-goals until proven

- No mainnet deployment claims.
- No audited contract claims.
- No hardened sandbox claims.
- No trained ML performance claims.
- No real funds by default.
