# Public GitHub Launch Checklist

## Ready to show as alpha

- Local cognitive loop runs.
- Runtime managers exist and are tested.
- Skill system exists and is tested.
- Economy v2 local lifecycle and failure lifecycle are tested.
- Swarm/delegation local primitives are tested.
- Internal API manifest/router is tested.
- Constitutional graph and memory policy are tested.
- Self-improvement repair planning is tested.
- Solidity scaffolds compile and have smoke tests.
- Docs distinguish implemented/prototype/adapter seam/scaffold/missing.

## Must not claim

- Trained ML perception.
- Hardened sandbox.
- Mainnet/testnet deployment.
- Audited contracts.
- Real funds.
- Production marketplace.

## Before publishing

- Review `.gitignore` and ensure `.venv/`, `out/`, `cache/`, and secrets are not committed.
- Run `python -m pytest -q`.
- Run `bash scripts/verify.sh`.
- Run `forge build && forge test`.
- Run created examples.
- Confirm docs match observed validation.
