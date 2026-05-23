"""Tiny deterministic text/trace embedder."""

from __future__ import annotations

import hashlib
import math
from typing import Any


class TinyMemoryEmbedder:
    def __init__(self, dimensions: int = 32) -> None:
        self.dimensions = dimensions

    def embed(self, item: Any) -> tuple[float, ...]:
        text = repr(item).lower()
        vector = [0.0 for _ in range(self.dimensions)]
        for token in text.replace("_", " ").replace("-", " ").split():
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=4).digest()
            index = int.from_bytes(digest, "big") % self.dimensions
            vector[index] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return tuple(value / norm for value in vector)
