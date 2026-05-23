# Flow Memory Roadmap

## Current V3 baseline

Implemented local production-shaped prototype:

- AI agent layer
- FlowLang-to-runtime integration
- Economy V3 local lifecycles
- SQLite durable storage
- signed manifests/receipts/provenance prototype
- API server/auth/signed request seams
- Base Sepolia/ERC-4337 dry-run adapters
- sandbox profile/receipt interfaces
- MCP/A2A/libp2p protocol seams
- dashboard scaffold
- CI and production docs

## Next milestones

1. Replace local HMAC signing with asymmetric DID/account signing.
2. Add Rust FlowIR validator with full schema checks.
3. Implement Rust Wasm Component Model host for WIT skill ABI.
4. Wire Datalog policy inference into runtime policy decisions.
5. Add durable audit replay CLI and tamper verification commands.
6. Add Base Sepolia contract deployment dry-run artifacts in CI.
7. Add no-funds testnet smoke path with explicit operator confirmation gate.
8. Add FastAPI integration tests behind optional dependency flag.
9. Implement container sandbox execution with strict resource limits.
10. Add dashboard API integration and generated SDK.
11. Add contract threat model review and external audit preparation.
12. Add policy-gated self-repair workflows that produce signed patch proposals.

## Non-goals until proven

- No mainnet deployment claims.
- No audited contract claims.
- No hardened sandbox claims.
- No trained ML performance claims.
- No real funds by default.
