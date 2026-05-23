# Agent Economy V3

## Purpose

Agent Economy V3 is the production-shaped target for agent work markets: task creation, bidding, escrow, work submission, verification, settlement, disputes, slashing, attestations, reputation, and treasury accounting. It should preserve the deterministic local lifecycle while separating storage, signatures, verification, and chain settlement behind explicit adapters.

## Implemented behavior

Status: prototype/adapter seam.

- The implemented local economy is `AgentEconomyV2`, an in-memory/offline lifecycle for tasks, bids, assignments, escrow funding, work submission, verification, settlement, disputes, slashing, attestations, audit records, and non-transferable reputation.
- Supporting modules provide local marketplace, escrow, dispute, pricing, incentive, slashing, settlement, treasury, wallet, identity, and attestation primitives.
- Solidity contracts exist for registry/marketplace/economy experiments, but they are unaudited and not mainnet-ready.
- V3 is documented here as the cutover shape over the current V2 primitives; there is no separate production `AgentEconomyV3` runtime class in the observed tree.

## Limitations

- Current economy state is mostly in-memory; durability and replay are not production-grade.
- Verification is requester/local-verifier driven, not decentralized or fraud-proof.
- Reputation is non-transferable local accounting, not Sybil-resistant identity.
- Contract code is experimental and unaudited; do not treat it as custody, mainnet, or settlement infrastructure.
- Pricing and incentive modules are simple deterministic seams, not trained market models.

## Next steps

- Introduce a durable economy repository with migrations and idempotent state transitions.
- Require signed manifests and signed work attestations for bidding, submission, and verification.
- Split settlement into local, testnet, and audited-chain adapters with explicit capability flags.
- Add verifier quorum policies and evidence schemas before slashing or high-value settlement.
- Define V3 compatibility tests around every task-state transition and failure branch.
