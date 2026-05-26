"""Optional Qdrant episodic-memory adapter skeleton."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass
class QdrantEpisodicAdapter:
    url: str = "http://localhost:6333"
    collection: str = "flow_memory_episodes"

    def _client(self) -> Any:
        try:
            from qdrant_client import QdrantClient
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("Install flow-memory[memory] to use QdrantEpisodicAdapter") from exc
        return QdrantClient(url=self.url)

    def upsert_embedding(self, record_id: str, vector: Sequence[float], payload: Mapping[str, Any]) -> None:
        client = self._client()
        try:
            from qdrant_client.models import PointStruct
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("qdrant-client models are unavailable") from exc
        client.upsert(collection_name=self.collection, points=[PointStruct(id=record_id, vector=list(vector), payload=dict(payload))])
