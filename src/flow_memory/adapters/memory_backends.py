"""Optional Redis/Qdrant/Neo4j backend seams."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RedisWorkingMemoryConfig:
    url: str = "redis://localhost:6379/0"


@dataclass
class QdrantEpisodicMemoryConfig:
    url: str = "http://localhost:6333"
    collection: str = "flow_memory_episodic"


@dataclass
class Neo4jSemanticMemoryConfig:
    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = "flowmemory"


def require_memory_extra(package: str) -> None:
    try:
        __import__(package)
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Install flow-memory[memory] to use external memory backends") from exc
