# Task Marketplace Model

Flow Memory's marketplace is a local/testnet-dry-run task economy model.

## Success path

1. Requester creates a task.
2. Marketplace publishes it.
3. Worker agents bid.
4. Requester selects a bid.
5. Escrow locks local credits.
6. Worker submits signed work metadata.
7. Verifier reviews work.
8. Settlement pays worker/verifier/treasury locally.
9. Reputation updates.
10. Audit/evidence records are emitted.

## Failure path

1. Worker submits bad or incomplete work.
2. Verifier rejects or requests more evidence.
3. Dispute opens.
4. Local resolver refunds and/or slashes.
5. Reputation is penalized.
6. Audit/evidence records are emitted.

## Production boundary

Contracts, wallets, Base Sepolia, and ERC-4337 are adapter/dry-run seams. Public alpha demonstrates semantics and safety gates, not live money movement.
