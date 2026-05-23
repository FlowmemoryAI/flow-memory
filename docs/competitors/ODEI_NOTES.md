# ODEI competitor notes

## Sources reviewed

- ODEI API documentation referenced in review context. Source URL to verify when available: ODEI API docs.
- Public memory repository referenced in review context: https://github.com/odei-ai/memory
- Retrieval gap: this task context did not include directly fetched API documentation text. Claims below are based on supplied review context and should be rechecked against live docs before implementing compatibility assumptions.

## Observed positioning

ODEI emphasizes governed memory rather than unconstrained agent recall. The API docs and `odei-ai/memory` repository are described as centering on:

- constitutional graph
- local-first graph memory
- guarded writes
- provenance, temporal data, and auditability
- Guardian enforcement
- public and signed lane separation
- governed query APIs
- guardrail APIs

## Engineering-relevant capabilities to track

### Constitutional graph

ODEI's constitutional graph framing suggests memory is governed by explicit policy relationships, not just vector similarity or chronological logs.

Flow Memory requirements:

- Store policy constraints as graph-addressable objects linked to memories, agents, tasks, and tools.
- Every memory write should record which policy allowed, denied, or constrained the write.
- Query results should be able to explain governing constraints, not only return content.

### Local-first graph memory

ODEI's local-first emphasis overlaps directly with Flow Memory's default offline-safe runtime.

Flow Memory requirements:

- Keep local graph memory usable without hosted services, network calls, cloud embeddings, or external identity providers.
- Use deterministic local IDs and content hashes so memory can later be synchronized or attested without rewriting history.
- Separate local persistence from optional publication, marketplace, or chain adapters.

### Guarded writes and Guardian enforcement

ODEI's Guardian model implies writes are mediated by a policy enforcement layer.

Flow Memory requirements:

- Route all memory mutations through one guarded write API.
- Enforce capability checks before mutation: writer identity, scope, sensitivity, retention policy, task context, and evidence requirements.
- Return structured denial reasons for unsafe writes.
- Audit both accepted and rejected writes.

### Provenance, temporal state, and auditability

ODEI's emphasis on provenance and temporal memory is an important bar for Flow Memory.

Flow Memory requirements:

- Track origin, author, observer, timestamp, task ID, evidence hash, and transformation chain for each memory item.
- Never overwrite memory in place without retaining prior version metadata.
- Support temporal queries: state at time, changes since time, active claims, expired claims, contradicted claims.
- Make audit export deterministic and locally reproducible.

### Public and signed lane separation

ODEI's public/signed lane distinction is a useful design constraint for Flow Memory's future networked mode.

Flow Memory requirements:

- Separate unsigned public observations from signed commitments, attestations, and economic records.
- Prevent unsigned memory from directly increasing reputation, releasing escrow, or satisfying verification requirements.
- Require signatures or local trusted authority records for claims that affect funds, identity, governance, or slashing.

### Governed query and guardrail APIs

Flow Memory requirements:

- Query APIs must apply policy before returning sensitive memory.
- Guardrail APIs should be callable independently from agent execution so tests, CLI, dashboards, and future services all use the same enforcement layer.
- Query responses should include policy metadata when safe: redaction status, governing rule IDs, provenance summary, and confidence/evidence state.

## Gaps and cautions

- The supplied context does not prove implementation completeness, performance, adoption, or production security.
- API names and exact schemas require direct verification from ODEI docs before compatibility work.
- Guardian enforcement should be studied for concepts, but Flow Memory should not adopt external terminology unless it maps cleanly to local policy and safety modules.

## Flow Memory response

Flow Memory should make governed memory a core invariant: local-first graph storage, guarded writes, provenance-preserving updates, temporal audit, signed/public lane separation, and policy-aware query APIs.
