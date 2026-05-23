"""Local cosine neural memory retriever."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from flow_memory.neural.memory.embedder import TinyMemoryEmbedder


@dataclass(frozen=True)
class RetrievalHit:
    item: Any
    score: float

    def as_record(self) -> Mapping[str, object]:
        return {"item": repr(self.item), "score": self.score}


class NeuralMemoryRetriever:
    def __init__(self, embedder: TinyMemoryEmbedder | None = None) -> None:
        self.embedder = embedder or TinyMemoryEmbedder()
        self._items: list[Any] = []
        self._vectors: list[tuple[float, ...]] = []

    def add(self, item: Any) -> None:
        self._items.append(item)
        self._vectors.append(self.embedder.embed(item))

    def extend(self, items) -> None:
        for item in items:
            self.add(item)

    def search(self, query: Any, *, top_k: int = 3) -> tuple[RetrievalHit, ...]:
        q = self.embedder.embed(query)
        hits = [RetrievalHit(item, _cosine(q, vector)) for item, vector in zip(self._items, self._vectors)]
        return tuple(sorted(hits, key=lambda hit: hit.score, reverse=True)[:top_k])


def _cosine(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return float(sum(x * y for x, y in zip(a, b)))
