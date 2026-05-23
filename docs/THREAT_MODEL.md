# Threat Model

This document is a practical security baseline for Flow Memory's agent economy, memory, tool-execution, and smart-contract components. It is not an audit report.

## Explicit safety position

- Contracts are unaudited. Treat every Solidity contract and deployment script as experimental until an independent audit, remediation pass, and release sign-off are complete.
- The tool/runtime sandbox is not hardened. Do not execute untrusted agent code, browser automation, shell commands, model-generated tools, or file-system mutations outside an isolated environment with explicit capability boundaries.
- Real funds and mainnet deployment are not enabled by default. Release and deployment paths must remain dry-run/testnet/local unless maintainers intentionally enable a reviewed mainnet process.

## Assets to protect

| Asset | Security objective |
| --- | --- |
| User memory and agent state | Preserve confidentiality, integrity, provenance, and deletion semantics. |
| Agent identities, DIDs, and reputation | Prevent spoofing, Sybil inflation, unauthorized reputation changes, and replay. |
| Escrowed value, staking records, and treasury balances | Prevent theft, unauthorized release, double settlement, and accounting drift. |
| Task specifications and results | Prevent tampering, hidden prompt injection, unauthorized disclosure, and false completion. |
| Policy/rule files | Prevent bypass, downgrade, and unauthorized edits to safety controls. |
| Tool execution environment | Prevent host escape, credential theft, network abuse, persistence, and lateral movement. |
| Release artifacts and workflows | Prevent compromised packages, unauthorized deployments, and supply-chain substitution. |

## Trust boundaries

1. **Untrusted users/requesters -> API/CLI/runtime**: task text, manifests, tool arguments, and uploaded artifacts are untrusted input.
2. **Model output -> executor/tools**: model-generated commands, code, URLs, file paths, and contract calls are untrusted until policy-checked.
3. **Agent runtime -> host system**: local files, environment variables, wallet keys, network, browser profiles, and process execution must be capability-scoped.
4. **Off-chain services -> on-chain contracts**: attestations, validation outcomes, reputation updates, and settlement instructions can be forged or replayed unless authenticated and domain-separated.
5. **Repository -> release artifacts**: CI dependencies, build scripts, generated artifacts, and workflow permissions are a supply-chain boundary.
6. **Local/testnet -> mainnet**: any switch from local or testnet execution to mainnet is a separate release decision requiring human approval.

## Primary threat scenarios

### Smart contracts and agent economy

| Threat | Impact | Required controls before production |
| --- | --- | --- |
| Reentrancy or unsafe external call in escrow/treasury paths | Stolen or locked funds | Independent audit, invariant tests, reentrancy protections, pull-payment settlement, emergency pause plan. |
| Incorrect task lifecycle transition | Premature payment, inability to resolve disputes | State-machine review, lifecycle invariants, explicit cancellation/timeout rules, event coverage. |
| Oracle/validator collusion | False completion and reputation manipulation | Validator selection policy, quorum rules, challenge period, validator stake/slashing, audit trail. |
| Sybil agents or requesters | Reputation inflation, spam, marketplace capture | Identity binding, stake requirements, rate limits, abuse monitoring, Sybil-resistant reputation policy. |
| Replay or cross-domain attestation reuse | Unauthorized settlement or reputation update | Chain ID/domain separation, nonces, expiry, typed-data signatures, signer rotation procedure. |
| Privileged key compromise | Contract takeover or treasury loss | Multisig, least privilege roles, hardware-backed keys, timelocks, key-rotation runbook. |
| Upgrade or deployment mismatch | Wrong bytecode or parameters on-chain | Reproducible builds, verified source, deployment manifest review, dry-run workflow, post-deploy checks. |

### Runtime, tools, and sandbox

| Threat | Impact | Required controls before production |
| --- | --- | --- |
| Prompt injection causes unsafe tool use | Data exfiltration, unauthorized spend, destructive actions | Capability-scoped tools, policy engine enforcement, human approval for sensitive actions, deny-by-default wallet/network/file access. |
| Sandbox escape or host file mutation | Credential theft, persistence, supply-chain compromise | OS/container isolation, read-only mounts, per-run temp workspace, egress controls, secret redaction, no shared browser profiles. |
| Malicious package or generated code execution | Remote code execution | Dependency pinning, lockfiles, provenance checks, isolated build workers, no arbitrary install/execute without approval. |
| Browser automation against real accounts | Account takeover, unauthorized transactions | Separate disposable profiles, disabled saved credentials, domain allowlists, confirmation gates, audit logging. |
| Tool output poisoning | Model accepts forged success or hides failure | Structured tool outputs, signed/verifiable results where practical, independent verification for high-impact actions. |

### Memory, policy, and data

| Threat | Impact | Required controls before production |
| --- | --- | --- |
| Cross-tenant memory leakage | Disclosure of private user/agent data | Tenant isolation, access-control tests, encryption at rest, scoped retrieval filters. |
| Memory poisoning | Bad plans, unsafe actions, reputation manipulation | Provenance tracking, trust scoring, quarantine for untrusted observations, reviewable deletion/rollback. |
| Policy downgrade or rule tampering | Safety bypass | Signed policy bundles, immutable release artifacts, policy change review, runtime policy hash logging. |
| Retention or deletion failure | Compliance and privacy risk | Retention policy, deletion workflows, audit logs, backups with deletion semantics documented. |

## Baseline mitigations already expected in development

- Keep production wallets, mainnet RPC credentials, signing keys, and real user secrets out of local demos and CI.
- Default-deny high-impact capabilities: wallet transfer, contract deployment, arbitrary shell, browser automation with real accounts, network access, and writes outside an explicit workspace.
- Prefer local chains/testnets and dry-run scripts for contract work.
- Log security-relevant decisions: task creation, assignment, validation, settlement, reputation changes, policy decisions, and deployment manifests.
- Require human approval before enabling any workflow that can publish packages, deploy contracts, transfer value, or mutate production data.

## Public-alpha RC1 added mitigations

- Clean-clone validation reduces "works on my machine" and packaging drift risk.
- Release evidence bundles hash API snapshots, storage schema, Base dry-run artifacts, dependency inventory, gates, and clean-clone evidence.
- Base Sepolia artifacts are dry-run only and validated before public-alpha release decisions.
- Contract security tests now cover additional unauthorized-call and state-transition cases, but do not replace an audit.
- Adversarial economy simulation models collusion, spam bidding, reputation farming, repeated disputes, and Sybil-like duplicates as local prototype signals.
- API scope, structured error, rate-limit, and audit middleware seams make the public-alpha API boundary testable without claiming production auth.

## Production security gates

Flow Memory is not ready for real funds, untrusted users, or mainnet until all of the following are complete:

- Independent smart-contract audit completed; findings remediated and re-reviewed.
- Contract invariants and lifecycle edge cases covered by automated tests and reviewed against the deployed bytecode.
- Hardened sandbox design implemented and tested against file, network, process, browser, and secret-access escape paths.
- Key management, multisig ownership, timelocks, and emergency pause/rollback procedures documented and rehearsed.
- Threat model reviewed after every material change to contracts, settlement logic, runtime tools, policy rules, or release workflows.
- Release workflow produces reproducible dry-run artifacts and cannot deploy or publish without an intentional separate approval path.
