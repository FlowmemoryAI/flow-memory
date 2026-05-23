# Protocol Gateways

Status: MCP, A2A, and libp2p gateway seams; local manifests and adapters only unless separately implemented.

## Purpose

Describe how Flow Memory should expose memory, skills, agents, and economy actions through external protocols without coupling the core runtime to one transport. Gateways translate protocol messages into local requests, capability checks, policy decisions, and auditable handler calls.

## Local-safe behavior

- The core runtime remains callable without MCP, A2A, or libp2p dependencies.
- Gateway handlers should validate protocol input before mapping it to local router or agent actions.
- Tool calls, delegation, marketplace actions, and memory writes must pass through the same policy and audit boundaries as local execution.
- Protocol identities should be mapped to local actor IDs and capabilities before any side effect.
- Unknown protocol methods, peers, tools, and schemas should fail closed.

## Limitations

- No production MCP server, A2A federation, or libp2p peer network is claimed here.
- Peer discovery, NAT traversal, pubsub durability, message authentication, replay defense, backpressure, schema migration, and abuse controls remain unverified.
- Protocol compatibility with external clients must be tested against real implementations before public claims.
- Gateway support does not make underlying Web3, sandbox, database, or ML adapters production-ready.

## Next implementation steps

1. Define protocol-neutral gateway interfaces for request validation, identity binding, capability checks, dispatch, and audit output.
2. Implement a local MCP gateway for read-only manifest, health, and safe memory/tool inspection before enabling mutations.
3. Add A2A agent-card exchange and delegation only after signature and replay rules are defined.
4. Add libp2p transport behind explicit configuration, authenticated peers, bounded queues, and deny-by-default message handling.
5. Run compatibility, fuzz, and abuse tests against real clients before publishing gateway endpoints.
