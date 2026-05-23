# Changelog

## Unreleased

### Added

- Portable `scripts/verify.sh` Python launcher selection for Windows/Git-Bash/PowerShell-oriented checkouts.
- Safety circuit-breaker integration for repeated denied/unsafe policy outcomes and failed action results.
- Explicit human approval statuses: `allow`, `deny`, and `defer`.
- Appearance-invariant dorsal motion signatures for frame-like and structured-object motion.
- Predictive-world-model propagation of dorsal motion signatures.
- Stricter local marketplace settlement requiring explicit assignment and rejecting double settlement.
- Deterministic `assign_lowest_bid()` local marketplace helper for examples.
- Local marketplace settlement records with assignee, bid, reward, requester, status, and metadata.
- Minimal Foundry smoke tests for AgentRegistry, TaskMarketplace, TaskEscrow, and Reputation.
- `FLOW_MEMORY_STATUS.md` maturity/risk status document.
- Public-repo hygiene files: `CODE_OF_CONDUCT.md`, issue templates, and pull request template.

### Changed

- README setup and verification instructions now include Windows and Bash notes.
- Architecture and roadmap docs now distinguish local implementation, functional prototype, adapter seam, scaffold, and missing production work.
- Economy examples now run against explicit assignment semantics.

### Validation

Observed on 2026-05-23 in `E:/FlowMemory/flow-memory`:

- Python tests: `50 passed in 0.32s`.
- Verify script: `50 passed in 0.31s` plus CLI smoke and perception benchmark output.
- Forge build: compiler run successful.
- Forge test: `4 tests passed, 0 failed, 0 skipped`.
- Docker Compose config: passed.
