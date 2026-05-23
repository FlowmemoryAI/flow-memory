"""Lazy optional adapters for Redis, Qdrant, and Neo4j.

The core package intentionally runs without these dependencies. These adapters validate
that the relevant third-party package is installed and then provide a minimal object seam
for deployment code to integrate with the in-memory models.
"""

from __future__ import annotations

from dataclasses import dataclass


def _require(module_name: str) -> object:
    try:
        module = __import__(module_name)
    except ImportError as exc:
        raise RuntimeError(
            f"Optional dependency '{module_name}' is not installed. Install flow-memory[memory]."
        ) from exc
    return module


@dataclass
class RedisWorkingMemoryAdapter:
    url: str = "redis://localhost:6379/0"

    def client(self) -> object:
        redis = _require("redis")
        return redis.Redis.from_url(self.url)  # type: ignore[attr-defined]


@dataclass
class QdrantEpisodicAdapter:
    url: str = "http://localhost:6333"
    collection: str = "flow_memory_episodes"

    def client(self) -> object:
        qdrant_client = _require("qdrant_client")
        return qdrant_client.QdrantClient(url=self.url)  # type: ignore[attr-defined]


@dataclass
class Neo4jSemanticAdapter:
    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = "flowmemory"

    def driver(self) -> object:
        neo4j = _require("neo4j")
        return neo4j.GraphDatabase.driver(self.uri, auth=(self.user, self.password))  # type: ignore[attr-defined]
