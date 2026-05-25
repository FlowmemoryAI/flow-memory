# Flow Memory Compute Market Compliance and Risk Notes

These notes are operational risk notes, not legal advice.

## Scope

Flow Memory Compute Market is compute planning infrastructure. It supports production-grade planning, quote normalization, route selection, policy enforcement, durable economic memory, audit logs, observability, and dry-run payment planning.

Dry-run payment intents are not settlement. They are planning artifacts used to evaluate compute routing and policy outcomes.

## Live settlement risk

Live settlement may trigger legal and compliance obligations. Legal/compliance review is required before enabling live settlement, compute futures, tokenized routes, financialized compute capacity, or any real funds movement.

Custody is not implemented. Flow Memory does not accept private keys, seed phrases, or custody instructions in production-planning mode.

## Asset and token risk

Tokens/assets require legal review before live use. The current asset and network metadata are planning records and do not imply regulatory approval, exchange support, money movement, or custody.

Money transmission risk must be assessed before live funds movement. Paid compute routing may also create tax/accounting implications.

## Compute marketplace risk

Provider contracts and SLAs are required for production marketplace routes. Provider reliability scores, latency estimates, and quote confidence are planning metadata unless backed by signed provider commitments.
External quote providers must pass provider contract conformance tests before onboarding. Contract conformance is an engineering safety gate, not a substitute for commercial/legal provider due diligence.

Financialized compute/futures require separate legal, compliance, risk, and security review.

## Privacy and retention

Durable records may include task metadata, agent IDs, goal IDs, provider IDs, route IDs, policy decisions, and audit events. Deployments must define retention, deletion, tenant isolation, privacy review, and access-control policies.
Audit hash chaining and local export checkpoints are tamper-evidence controls, not a legal records-retention system or WORM guarantee. Production deployments should export audit logs and chain checkpoints to immutable storage according to retention policy and verify exported checkpoints during incident response.

## Required controls before live funds

- Security-reviewed settlement gates.
- Legal/compliance approval.
- Network and asset allowlists.
- Provider contracts and SLAs.
- Accounting and tax review.
- Non-custodial or approved custody model.
- Incident response and rollback procedures.
- Immutable audit export/checkpoint policy.
