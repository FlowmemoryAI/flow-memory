# Nookplot competitor notes

## Sources reviewed

- Public repository: https://github.com/nookprotocol/nookplot
- Repository API entrypoint referenced in review context: https://github.com/nookprotocol/nookplot/blob/main/api/src/server.ts
- Repository intelligence routes referenced in review context: https://github.com/nookprotocol/nookplot/blob/main/api/src/routes/intelligence.ts
- Retrieval gap: the primary docs URL only returned landing metadata. Search results indicated Mintlify-hosted docs, but direct fetch returned HTTP 410. Treat any docs-only claims as unverified until the docs are recoverable.

## Observed positioning

Nookplot appears to be an agent coordination and economic-settlement stack rather than a memory-only product. The public repository is described as a TypeScript stack with API services, CLI commands, SDK, contracts, MCP support, Base/x402 payment integration, identity/reputation primitives, coordination features, and economic settlement.

## Engineering-relevant capabilities to track

### API and runtime hardening

`api/src/server.ts` is described as an Express service using helmet, CORS, rate limiting, audit behavior, x402 payment flow handling, Cloudflare integration, and a read-only SDK surface.

Flow Memory requirements:

- Keep local/offline execution as the default; do not require a hosted API to use core memory, planning, safety, or economy primitives.
- Define an equivalent production API hardening checklist before exposing Flow Memory over HTTP: security headers, explicit CORS policy, rate limits, audit logging, request IDs, deterministic error shapes, and read/write capability boundaries.
- Keep read-only APIs separate from write/economic actions so hosted integrations can be audited independently.

### Semantic network and intelligence routes

`api/src/routes/intelligence.ts` is described as exposing semantic network endpoints including:

- `community-health`
- `reputation`
- `agent-topics`
- `experts`
- `consensus`
- `trending`
- `trust-path`
- `bridge-agents`

Flow Memory requirements:

- Treat reputation as an input to routing and trust decisions, not as a cosmetic leaderboard.
- Model trust paths explicitly: given source agent, target agent, and task context, the system should explain why the relationship is trusted or rejected.
- Add local graph queries for agent topics, expertise, consensus state, and bridge agents before adding networked endpoints.
- Make community-health metrics deterministic and inspectable: active agents, failed tasks, disputed tasks, slashed agents, unresolved safety violations, stale memories, and unverifiable claims.

### Identity, reputation, and settlement

Nookplot's repository context includes identity, reputation, coordination, Base/x402, contracts, and economic settlement.

Flow Memory requirements:

- Keep identity provider-agnostic: local key identity first, DID or wallet binding as optional attestations.
- Separate reputation events from balances and payments. Payment success must not imply task quality.
- Require provenance for all reputation changes: task ID, evaluator, evidence hash, timestamp, and dispute window.
- Keep settlement adapters behind an interface so Base, x402, local escrow, and offline ledgers do not leak into core agent logic.

## Gaps and cautions

- Mintlify docs could not be directly retrieved due to HTTP 410; verify docs once reachable before copying endpoint names, CLI names, or protocol details beyond repository-observed context.
- Repository presence does not prove production adoption, audited contracts, reliable hosted uptime, or real economic volume.
- Base/x402 support should be treated as a competitor integration direction, not proof that Flow Memory must deploy to Base by default.

## Flow Memory response

- Build the local deterministic memory/economy substrate first.
- Expose an optional Base-readiness layer with identity, escrow, marketplace, reputation, attestations, slashing, verification, agent payments, disputes, and governance, without implying deployment.
- Prioritize inspectable trust and provenance over broad endpoint count.
