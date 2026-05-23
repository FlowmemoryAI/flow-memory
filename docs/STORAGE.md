# Storage

## Purpose

Storage should make agent memory, audit, manifests, and economy state durable without forcing optional infrastructure on the core package. SQLite is the intended local production-shaped baseline for structured state; Redis, Qdrant, Neo4j, and chain adapters remain deployment-specific seams.

## Implemented behavior

Status: prototype/adapter seam.

- Core memory currently includes `JsonlMemoryStore`, an append-only JSONL helper for episodic records.
- Optional storage adapters expose lazy seams for Redis working memory, Qdrant episodic/vector storage, and Neo4j semantic graph storage.
- The package keeps optional third-party storage dependencies out of the default runtime path.
- SQLite is not implemented as an observed first-class repository in the current tree; this document records the required local durable-storage shape.

## Limitations

- JSONL storage has no schema migrations, indexes, transactional updates, compaction, or concurrent-writer guarantees.
- Optional adapters validate dependency availability and return clients; they do not define full repository semantics.
- There is no observed SQLite schema for agent cycles, memories, manifests, audit events, or economy transitions.
- Backup, restore, encryption-at-rest, retention, and multi-process locking are not yet implemented.

## Next steps

- Add a SQLite repository layer with explicit migrations and narrow tables for memories, audit events, signed manifests, economy tasks, bids, submissions, attestations, and settlements.
- Make writes idempotent where external retries are possible.
- Store manifest digests and signatures alongside every admitted runtime artifact.
- Add repository interfaces so JSONL and optional external stores are adapters, not hidden global dependencies.
- Define backup, compaction, retention, and corruption-recovery procedures before production use.
