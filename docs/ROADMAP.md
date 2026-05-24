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


## Neural roadmap

1. Train tiny dual-stream and world-model prototypes on richer synthetic traces.
2. Wire local V-JEPA 2 checkpoint evaluation without downloads.
3. Wire local VideoMAE checkpoint evaluation without downloads.
4. Add neural scores to release evidence as prototype metrics.
5. Expand benchmarks to real local video fixtures once licensing is clear.


## Flow Arena RL + Neural Evidence RC update

This repo now includes Flow Arena, a dependency-free local RL environment layer for agent-economy decision training, plus GPU evidence import/release-gate seams. RL policies are advisory only; policy, approval, autonomy, and economy risk controls remain authoritative. Neural GPU validation evidence is stored as text/JSON metadata and hashes; raw checkpoint/model artifacts are not committed.

## Launch-readiness roadmap update

Completed in the full-system launch readiness lane:

- public-alpha launch scripts for CLI, FlowLang, neural advisory, and local multi-agent network paths;
- local network scenarios for economy, neural metadata, RL training, and dispute/slashing;
- explicit payment/accounting model answering who pays whom;
- learning loop for trace collection, memory learning, RL Arena learning, and neural training status;
- full-system quick validation script and `public-alpha-launch` release decision target.

Next highest-value work:

1. Import and verify the real RunPod GPU artifact so `neural-gpu-smoke`, `public-alpha-neural`, and `public-alpha-launch` can pass.
2. Add signed public-alpha launch evidence bundles.
3. Add API launch endpoints for agents/network scenarios.
4. Add dashboard panels for full-system and learning-loop reports.
5. Replace prototype local accounting with audited testnet escrow rehearsals only after external review.
