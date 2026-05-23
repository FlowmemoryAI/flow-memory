# Smart Contracts

Status: expanded unaudited scaffold with Foundry tests.

## Contracts

- `AgentRegistry.sol`
- `Reputation.sol`
- `TaskEscrow.sol`
- `TaskMarketplace.sol`
- `AgentTreasury.sol`
- `AttestationRegistry.sol`
- `DisputeResolver.sol`
- `SlashingRegistry.sol`
- `CapabilityRegistry.sol`
- `DelegationRegistry.sol`

## Tests

- `test/FlowMemoryContracts.t.sol`
- `test/AgentEconomyV2.t.sol`

The tests cover happy-path registry, escrow, marketplace, reputation, attestation, delegation, dispute, slashing, treasury, and capability registry behavior plus selected unauthorized/double-resolution rejection paths.

## Limitations

These contracts are not audited, not deployed, and not mainnet/testnet ready. They do not include complete governance, upgrade, token, fraud-proof, slashing-dispute appeal, or production treasury controls.

## Next work

- Add revert tests for every permission boundary.
- Add fuzz/invariant tests.
- Add deployment scripts and verification.
- Commission independent audit before value-bearing use.
