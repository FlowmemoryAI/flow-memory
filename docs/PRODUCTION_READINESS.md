# Production Readiness Checklist

Flow Memory is currently development-stage software. This checklist defines what must be true before any production launch, real-funds flow, or mainnet deployment.

## Non-negotiable current status

- Contracts are unaudited. Do not present the contract suite as production-ready until an external audit is complete and remediations are verified.
- The sandbox is not hardened. Do not run untrusted tools, model-generated code, browser automation, or arbitrary shell access as if it were isolated from the host.
- Real funds and mainnet deployment are not enabled by default. Any production wallet, mainnet RPC, publishing token, or deploy key must require an explicit reviewed release path outside the default dry-run workflow.

## Release classification

| Level | Allowed uses | Not allowed |
| --- | --- | --- |
| Local development | Local demos, unit tests, local chain experiments, dry-run packaging | Real funds, production secrets, untrusted code execution. |
| Testnet / private beta | Testnet contracts, capped experiments, disposable wallets, monitored pilots | Mainnet funds, claims of audited security, public economic incentives. |
| Production candidate | External audit complete, hardened sandbox, runbooks, monitoring, staged rollout | Mainnet launch before sign-off, unaudited contract upgrades, unreviewed deploy keys. |
| Production | Approved mainnet release, monitored operations, incident response, key management | Bypassing release gates or running default workflows with production credentials. |

## Smart contracts and economy

Before production:

- [ ] Independent audit completed for all deployed contracts, libraries, and deployment scripts.
- [ ] Audit findings remediated, re-reviewed, and linked from the release record.
- [ ] Invariants cover escrow accounting, task lifecycle transitions, slashing, delegation, reputation, dispute resolution, and treasury balances.
- [ ] Deployment bytecode is reproducible from the tagged source.
- [ ] Contract addresses, constructor arguments, owner roles, chain ID, and verification status are recorded in a deployment manifest.
- [ ] Owner/admin roles use multisig or equivalent controls; no externally owned account is a single point of failure.
- [ ] Emergency pause, unpause, dispute, and recovery procedures are documented and rehearsed on a non-mainnet environment.
- [ ] Mainnet deployment requires explicit human approval and cannot be triggered by the default dry-run workflow.
- [ ] Real funds are disabled until treasury, escrow, and settlement controls are signed off.

## Runtime sandbox and tools

Before untrusted execution:

- [ ] Tool capabilities are deny-by-default and scoped per task.
- [ ] File-system writes are restricted to an explicit workspace; secrets and repository metadata are not mounted writable into agent sandboxes.
- [ ] Network egress is disabled by default or restricted by policy.
- [ ] Shell/process execution is isolated with resource limits, timeouts, and no inherited production credentials.
- [ ] Browser automation uses disposable profiles and cannot access real accounts, saved credentials, wallet extensions, or production sessions by default.
- [ ] Wallet signing and contract calls require a separate policy decision and human approval for high-impact actions.
- [ ] Logs redact secrets and do not store sensitive prompt, memory, wallet, or credential material unless explicitly classified and protected.
- [ ] Sandbox escape and policy-bypass tests exist for file, network, process, browser, environment-variable, and secret-access paths.

## Memory, identity, and policy

Before production data is used:

- [ ] Tenant/user/agent isolation is enforced in memory storage and retrieval.
- [ ] Memory records carry provenance, trust level, timestamp, and deletion/retention metadata.
- [ ] Untrusted observations are quarantined or down-ranked before they influence high-impact decisions.
- [ ] Policy rules are versioned, reviewed, and logged with a policy hash at decision time.
- [ ] DID/agent identity binding prevents trivial spoofing and replay.
- [ ] Reputation changes are auditable and tied to verifiable task outcomes.
- [ ] Deletion and retention behavior is documented and tested, including backups where applicable.

## CI, release, and supply chain

Before public release:

- [ ] CI uses least-privilege permissions.
- [ ] Default workflows do not deploy contracts, publish packages, transfer funds, or use production secrets.
- [ ] Release dry-runs build or inspect artifacts without publishing them.
- [ ] Dependency versions are pinned or otherwise reviewed for reproducibility.
- [ ] Generated artifacts are traceable to source commit, version, and build command.
- [ ] Maintainers review any workflow that requests write tokens, package publishing permissions, deployment credentials, or mainnet RPC access.
- [ ] Release notes clearly label unaudited, experimental, local-only, or testnet-only features.
- [ ] `python scripts/release_gate.py --root .` passes and its output is attached to the release record.
- [ ] `python scripts/generate_release_manifest.py --root . --out release-manifest.json` is attached to the release record.

## Observability and operations

Before production traffic:

- [ ] Metrics cover task lifecycle counts, settlement outcomes, dispute rates, slashing events, policy denials, sandbox denials, tool failures, and release/deployment status.
- [ ] Alerts exist for unexpected contract balance changes, repeated policy bypass attempts, failed settlements, abnormal validator behavior, and release workflow changes.
- [ ] Incident response runbooks cover contract pause, key compromise, bad deployment, memory leakage, sandbox escape, package compromise, and validator collusion.
- [ ] Backups and restore procedures are tested for critical off-chain state.
- [ ] Maintainers have a rollback or mitigation plan for each production dependency.

## Go / no-go checklist

A release is **no-go** if any of these are true:

- Contracts remain unaudited for a release that handles real funds or mainnet state.
- The sandbox remains unhardened for untrusted code/tool/browser execution.
- Any default workflow can deploy, publish, or transfer value without explicit human approval.
- Production secrets are available to pull requests, forks, local demos, or dry-run jobs.
- Mainnet RPC, deploy keys, package publishing tokens, or treasury wallets are configured as defaults.
- Monitoring, incident response, and key recovery procedures are not in place for the release scope.

## Minimum release evidence

Each release candidate should attach or link:

- Dry-run workflow result and generated artifact list.
- Contract audit status and remediation notes, if contracts are in scope.
- Sandbox hardening status, if tools/browser/shell execution are in scope.
- Deployment manifest for any non-local contract environment.
- Known limitations, including whether funds, mainnet, untrusted execution, or production data are intentionally disabled.
- Release-gate JSON from `scripts/release_gate.py`, including API snapshot, audit replay, Base dry-run, and secret-scan status.
- Release manifest JSON from `scripts/generate_release_manifest.py`, including commit, branch, API snapshot, storage schema, Base dry-run plan, and release-gate status.
