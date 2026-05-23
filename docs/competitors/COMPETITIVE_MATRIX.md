# Competitive matrix

## Sources and retrieval status

| Competitor | Sources used | Retrieval gaps |
|---|---|---|
| Nookplot | https://github.com/nookprotocol/nookplot, with review context for `api/src/server.ts` and `api/src/routes/intelligence.ts` | Primary docs URL returned only landing metadata. Search found Mintlify docs, but direct fetch returned HTTP 410. |
| AEON | README claims supplied in review context | No independently fetched repository URL was available in this task context. Treat as README claims pending verification. |
| ODEI | https://github.com/odei-ai/memory and API-doc context supplied in review context | API documentation text was not directly fetched in this task. Exact schemas and names require verification. |

## Capability comparison

| Area | Nookplot | AEON | ODEI | Flow Memory requirement |
|---|---|---|---|---|
| Default operating model | TypeScript network/API stack with SDK, CLI, contracts, MCP, Base/x402 context | Automation platform with broad skill catalog and unattended operation claims | Local-first governed graph memory | Local/offline safe by default; network, chain, and gateway adapters optional. |
| Memory model | Semantic network and intelligence endpoints are described | Persistent memory claimed | Constitutional graph, provenance, temporal auditability | Graph memory with guarded writes, provenance, temporal queries, and deterministic local persistence. |
| Agent coordination | Community health, experts, consensus, trust path, bridge agents | Schedules, reactive triggers, MCP/A2A gateways | Governed query/write lanes for memory | Local deterministic coordination first; trust paths and consensus must be inspectable. |
| Skills/tools | API, SDK, CLI, MCP implied | 121 skills and skill catalog claimed | Guardrail and governed APIs, not primarily skill-count oriented | Skill manifests with permissions, safety class, deterministic tests, and execution audit. |
| Reputation | Repository context includes identity/reputation | Quality scoring claimed | Signed/provenance lanes can support trustworthy claims | Reputation must be event-sourced from evidence, disputes, verification, and policy outcomes. |
| Economy | Contracts, Base/x402, settlement context | Not central in supplied context | Public/signed separation relevant to economic claims | Escrow, marketplace, attestations, slashing, payments, disputes, and governance as local/offline models before deployment. |
| Safety/governance | API hardening and audit behavior described | Self-healing/repair claims require policy scrutiny | Guardian enforcement and constitutional graph | One policy path for memory writes, tool use, economic actions, and reputation changes. |
| Integration posture | Cloudflare, x402, MCP, SDK, contracts | GitHub Actions, MCP, A2A, dashboard | API guardrails and memory repo | Adapters only; core must not depend on hosted services or external gateways. |
| Evidence quality | Public repo context; docs retrieval gap | README claims only in this task | Repo/API-doc context, exact docs not fetched | Keep implementation claims tied to tests, source, and deterministic local behavior. |

## Required Flow Memory design responses

### 1. Governed local memory

- All memory writes go through a guarded mutation API.
- Every memory item records provenance: author/observer, task, source, evidence hash, timestamp, policy result, and transformation chain.
- Temporal queries must support current state, state at time, changes since time, contradicted claims, and expired claims.
- Public observations and signed/economic records must remain separate lanes.

### 2. Inspectable trust and coordination

- Implement trust-path explanation before network effects.
- Track agent expertise by completed tasks and evidence, not self-declared labels alone.
- Community health metrics must be computable locally from event logs: failures, disputes, slashes, stale claims, unsafe writes, unresolved reviews, and settlement state.
- Consensus must expose participants, evidence, dissent, threshold, and final decision.

### 3. Evidence-backed skill economy

- Skills require manifests with permissions, allowed resources, safety class, deterministic examples, and owner/version metadata.
- Skill execution must emit immutable local events.
- Quality scoring must be decomposed; do not use one opaque aggregate.
- Self-repair is a proposal unless it passes policy, tests, provenance, and approval requirements for risky scopes.

### 4. Base-readiness without deployment claims

- Provide interfaces and local simulations for identity, wallet abstraction, ERC-4337 path, escrow, marketplace, reputation, attestations, slashing, verification, agent payments, disputes, and governance.
- Do not imply real funds, audited contracts, production deployment, or mainnet readiness.
- Keep settlement adapters behind interfaces.

### 5. API posture

- If Flow Memory exposes HTTP later, hardening must include request IDs, structured errors, audit logs, explicit CORS, security headers, rate limits, read/write separation, and policy checks at all mutation boundaries.
- Read-only APIs must never expose secret, private, or unsigned-to-signed privilege escalation paths.

## Near-term implementation checklist

| Requirement | Local/offline acceptance criterion |
|---|---|
| Guarded memory write | Unit test proves unsafe write is rejected with structured reason and audit event. |
| Provenance | Unit test proves memory record includes source, actor, task, timestamp, evidence hash, and policy result. |
| Trust path | Unit test proves trust path can be explained and rejected when no evidence exists. |
| Reputation event | Unit test proves reputation changes require evidence and do not mutate balances. |
| Escrow simulation | Unit test proves escrow lock, release, dispute, and slash transitions are deterministic. |
| Skill manifest | Unit test proves unregistered or over-permissioned skill is denied. |
| Public/signed lane | Unit test proves unsigned public observation cannot release escrow or increase verified reputation. |
| Audit export | Unit test proves export order and hashes are deterministic across runs. |

## Non-goals

- Do not claim production Base deployment.
- Do not claim audited contracts unless an audit exists.
- Do not add hosted dependencies to the default runtime.
- Do not copy competitor terminology unless it maps to Flow Memory's actual modules.
