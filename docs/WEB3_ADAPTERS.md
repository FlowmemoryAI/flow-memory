# Web3 Adapters

Status: adapter seam for wallets, contracts, and Base-compatible settlement; not connected to live funds by default.

## Purpose

Specify how Flow Memory's local agent economy can map to Web3 systems without letting chain-specific code own core task, reputation, escrow, or policy state. Adapters translate local intents into wallet signatures, contract calls, attestations, and settlement receipts after policy approval.

## Local-safe behavior

- The default adapter is local-only and must not move funds.
- Wallet operations should produce deterministic test references unless an explicit network adapter is enabled.
- Contract interactions are represented as intents and receipts, not assumed final settlement.
- Core economy state remains authoritative until a verified adapter result is accepted.
- Private keys, RPC URLs, hosted wallet credentials, and bundler credentials must come from explicit runtime configuration and must never be committed.

## Limitations

- No production wallet custody, ERC-4337 bundler/paymaster flow, gas policy, key rotation, nonce management, chain reorg handling, or treasury controls are certified.
- Solidity contracts are unaudited prototypes and must not be treated as mainnet-ready.
- No Base mainnet or testnet deployment is claimed by this document.
- Cross-chain bridges, token issuance, x402 payment rails, and external marketplace integrations remain seams unless separately implemented and verified.

## Next implementation steps

1. Define narrow wallet, registry, escrow, reputation, and attestation adapter interfaces.
2. Add a no-network local adapter with exhaustive tests for signing and settlement state transitions.
3. Add a Base Sepolia dry-run adapter gated by explicit configuration and spending limits.
4. Record every adapter action as an auditable intent, policy decision, submission, receipt, and finality update.
5. Complete contract review, deployment rehearsal, monitoring, and independent audit before any value-bearing use.
