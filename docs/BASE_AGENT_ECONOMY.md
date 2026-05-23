# Flow Memory Base-readiness requirements

This document defines Base-readiness for Flow Memory without claiming deployment, production funds, audited contracts, or mainnet operation. The default implementation must remain local, deterministic, dependency-free, and offline safe.

## Readiness definition

Flow Memory is Base-ready when its local economy model can be mapped cleanly to Base-compatible adapters without changing core agent behavior.

Readiness requires:

- stable local identities that can later bind to wallets or DIDs
- wallet abstraction boundary
- ERC-4337 account-abstraction path
- escrow state machine
- marketplace state machine
- reputation ledger
- attestations
- slashing rules
- verification workflow
- agent payment records
- dispute workflow
- governance controls
- deterministic audit export

Readiness does not mean:

- deployed contracts
- real funds
- audited security
- production x402 support
- guaranteed Base compatibility
- trained models or autonomous financial authority

## Core invariants

- Agent logic must not depend on chain availability.
- Economic state must be reproducible locally from events.
- Payments, reputation, verification, and memory provenance must be separate ledgers linked by IDs.
- No unsigned public observation may release escrow, increase verified reputation, slash an agent, or satisfy a paid verification requirement.
- Every economic transition must have actor, timestamp, task ID, policy result, and evidence reference.
- Disputes must freeze settlement until resolved.
- Slashing must require an explicit rule, evidence, and dispute window.

## Identity

### Local identity

Each agent requires a local identity record:

- `agent_id`
- display name
- public key or local authority identifier
- created timestamp
- status: active, suspended, retired
- capabilities declared by manifest
- optional wallet binding ID
- optional DID binding ID

### Wallet/DID binding

Wallets and DIDs are attestations attached to a local identity, not replacements for it.

Requirements:

- Binding must record signer, signature/evidence hash, chain/network label, address or DID, timestamp, and revocation status.
- One agent may have multiple bindings.
- Revoked bindings remain in audit history.
- Core local tasks continue to work without any wallet binding.

## Wallet abstraction

Define a wallet adapter interface that can be implemented by local test wallets, hosted wallets, or ERC-4337 smart accounts later.

Required operations:

- derive or load account reference
- sign challenge
- sign typed economic intent
- verify signature
- expose chain/network metadata
- report whether the account supports account abstraction

The default adapter must be local-only and must not move funds.

## ERC-4337 path

Flow Memory should model account abstraction as an optional payment/execution path.

Required local concepts:

- user operation intent ID
- sponsor/paymaster policy result
- spending limit
- task/payment link
- signature reference
- execution status: proposed, signed, submitted, confirmed, failed, cancelled

Local tests should validate the state machine only. They must not require bundlers, paymasters, RPC endpoints, or network calls.

## Escrow

Escrow is the core settlement primitive.

Required states:

- proposed
- funded or locally locked
- accepted
- submitted
- verified
- released
- disputed
- resolved
- refunded
- slashed
- cancelled

Required fields:

- escrow ID
- task ID
- payer agent
- worker agent
- verifier agent or policy
- amount
- denomination
- funding reference
- acceptance criteria hash
- deadline
- dispute window
- evidence references
- state transition log

Rules:

- Funds cannot be released before verification.
- Dispute freezes release/refund until resolved.
- Slash requires a specific violated rule and evidence.
- Reputation updates occur from escrow outcome events, not from payment existence alone.

## Marketplace

Marketplace records match tasks to agents. It must be useful without chain deployment.

Required objects:

- task listing
- bid/offer
- assignment
- escrow link
- required capabilities
- risk class
- verification method
- price/denomination
- deadlines
- cancellation rules

Requirements:

- Marketplace matching must not bypass safety policy.
- Bids must include agent identity and capability evidence.
- Listings with economic settlement must specify verifier and dispute policy before acceptance.

## Reputation

Reputation is an evidence ledger, not a mutable score alone.

Required event types:

- task accepted
- task completed
- verification passed
- verification failed
- dispute opened
- dispute resolved
- escrow released
- refund issued
- slash applied
- policy violation
- attestation added
- attestation revoked

Each event must include evidence and provenance.

Derived scores may exist, but must be recomputable from events and must expose components.

## Attestations

Attestations bind claims to evidence.

Required fields:

- attestation ID
- subject agent/task/memory/skill
- issuer
- claim type
- claim value or hash
- evidence hash
- issued timestamp
- expiration timestamp when applicable
- signature or local authority proof
- revocation status

Attestation classes:

- identity binding
- capability
- task completion
- verification
- safety review
- payment/settlement
- governance authorization

## Slashing

Slashing is a penalty mechanism and must be conservative.

Requirements:

- Slashable conditions must be enumerated before task acceptance.
- Slash action requires evidence, rule ID, actor, timestamp, and dispute window.
- Slashing must affect stake/reputation according to explicit policy.
- Slashing must never be triggered by an unsigned public observation alone.
- The local model must support dry-run slash evaluation.

## Verification

Verification determines whether work satisfies acceptance criteria.

Verification record fields:

- verification ID
- task ID
- verifier
- method: deterministic test, human review, policy check, signed attestation, or composite
- evidence hash
- result: pass, fail, inconclusive
- timestamp
- policy result
- notes reference, if any

Requirements:

- Verification must be separate from worker self-report.
- Payment release requires a passing verification or explicit dispute resolution.
- Verification failures must preserve submitted evidence for appeal/dispute.

## Agent payments

Agent payments are settlement records linked to escrow, not direct writes to reputation.

Required fields:

- payment ID
- escrow ID
- payer
- payee
- amount
- denomination
- adapter: local, Base, x402, or other
- status: proposed, locked, released, refunded, failed, cancelled
- transaction/reference hash when available
- timestamp

Default local payments are simulated ledger events only.

## Disputes

Disputes protect both payer and worker.

Required states:

- opened
- evidence_submitted
- under_review
- resolved_for_worker
- resolved_for_payer
- split_resolution
- escalated
- closed

Requirements:

- Opening a dispute freezes escrow release/refund.
- Both sides may attach evidence.
- Resolver authority must be known before task acceptance.
- Resolution must emit payment and reputation events.

## Governance

Governance controls policy changes and high-risk economic parameters.

Governed parameters:

- slashable rules
- marketplace risk classes
- verifier eligibility
- dispute resolver eligibility
- maximum default spend
- adapter enablement
- reputation weights
- attestation trust classes

Requirements:

- Governance changes are proposals with actor, rationale, diff, policy result, approval record, and activation timestamp.
- Local default governance may be single-authority, but the model must preserve audit records for later multi-sig or DAO-style adapters.
- Governance cannot retroactively alter completed economic history.

## Adapter boundaries

Base, x402, ERC-4337, hosted wallet, and marketplace APIs must be adapters over the local model.

Adapters may translate:

- identity binding to wallet signatures
- escrow transitions to contract calls
- payment records to transaction hashes
- attestations to signed or on-chain attestations
- governance approvals to multisig or DAO actions

Adapters must not own:

- core task state
- policy decisions
- memory provenance
- reputation derivation
- dispute rules

## Minimum local acceptance tests

- Identity can be created locally without wallet binding.
- Wallet binding can be added, revoked, and audited.
- Escrow cannot release before verification.
- Dispute freezes escrow until resolution.
- Slash requires explicit rule and evidence.
- Unsigned public observation cannot release payment or increase verified reputation.
- Reputation score is recomputable from events.
- Payment record does not mutate reputation directly.
- Governance proposal changes future policy only.
- Audit export is deterministic.

## Implementation order

1. Local event ledger for economy actions.
2. Identity and attestation records.
3. Escrow state machine.
4. Verification and dispute state machines.
5. Reputation derivation from events.
6. Marketplace listing/bid/assignment model.
7. Wallet abstraction and local signing adapter.
8. ERC-4337 intent state model.
9. Base/x402 adapter interfaces with no network default.
10. Governance proposal and activation model.
