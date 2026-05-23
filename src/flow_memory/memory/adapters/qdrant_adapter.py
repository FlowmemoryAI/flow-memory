"""Optional Qdrant memory adapter seam."""
from __future__ import annotations


class QdrantMemoryAdapter:
    def __init__(self, url: str, collection: str = "flow_memory") -> None:
        self.url = url
        self.collection = collection

    def _client(self):
        try:
            from qdrant_client import QdrantClient  # type: ignore
        except Exception as exc:
            raise RuntimeError("Qdrant adapter requires optional dependency: qdrant-client") from exc
        return QdrantClient(url=self.url)

    def describe(self) -> dict[str, str]:
        return {"adapter": "qdrant", "url": self.url, "collection": self.collection}
