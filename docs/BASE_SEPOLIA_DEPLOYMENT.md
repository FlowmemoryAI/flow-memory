# Base Sepolia Dry-Run Deployment

Status: dry-run deployment plan for testnet rehearsal; no live deployment or production readiness claim.

## Purpose

Describe the safe path for rehearsing Flow Memory contract and Web3 adapter behavior on Base Sepolia before any value-bearing environment. The goal is to validate configuration, deployment order, receipt capture, explorer verification, and rollback notes without changing the local-first economy contract.

## Local-safe behavior

- Local development must default to simulated deployment output and never require funded keys.
- Any Base Sepolia run must be opt-in through explicit environment configuration.
- Testnet private keys must be low-value, isolated, and excluded from the repository.
- Deployment scripts should emit addresses, transaction hashes, constructor args, chain id, compiler settings, and verification status as audit artifacts.
- Dry-run receipts should be consumed by adapters as test references, not as proof of production settlement.

## Limitations

- Base Sepolia is a public testnet; it provides integration signal, not security assurance.
- Testnet success does not validate economic safety, contract upgrade controls, treasury operations, gas griefing resistance, wallet custody, or mainnet finality assumptions.
- Contracts remain unaudited and unsuitable for mainnet or real funds.
- This document does not define a release approval process for production deployment.

## Next implementation steps

1. Add a deployment manifest schema for chain id, contract names, addresses, transaction hashes, and verification metadata.
2. Build a dry-run mode that resolves constructor args and prints planned transactions without broadcasting.
3. Add explicit Base Sepolia broadcast mode with preflight checks for chain id, balance, nonce, RPC endpoint, and key source.
4. Verify contracts on the explorer and store verification results with the deployment manifest.
5. Require security review, audit findings closure, incident runbooks, and treasury controls before any mainnet plan.
