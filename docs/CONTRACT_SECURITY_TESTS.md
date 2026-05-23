# Contract Security Tests

RC1 expands Foundry coverage with `test/AgentEconomySecurity.t.sol`.

Covered locally:

- unauthorized escrow assignment and settlement rejection
- double settlement rejection
- marketplace overpriced bid rejection
- unauthorized marketplace close rejection
- controller/authority-only reputation, dispute, slashing, and treasury checks
- invalid attestation/delegation/capability input rejection

These tests improve confidence but do not constitute an audit. Contracts remain unaudited and not production/mainnet-ready.
