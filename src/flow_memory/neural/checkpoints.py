"""Local checkpoint registry for optional neural backends."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class CheckpointRef:
    name: str
    path: str
    backend: str = "tiny_torch"
    metadata: Mapping[str, str] | None = None

    def exists(self) -> bool:
        return Path(self.path).exists()

    def as_record(self) -> dict[str, object]:
        return {"name": self.name, "path": self.path, "backend": self.backend, "exists": self.exists(), "metadata": dict(self.metadata or {})}


class CheckpointRegistry:
    def __init__(self) -> None:
        self._refs: dict[str, CheckpointRef] = {}

    def register(self, name: str, path: str, *, backend: str = "tiny_torch", metadata: Mapping[str, str] | None = None) -> CheckpointRef:
        if "://" in path or path.startswith("hf://"):
            raise ValueError("checkpoint registry accepts local paths only by default")
        ref = CheckpointRef(name=name, path=path, backend=backend, metadata=metadata)
        self._refs[name] = ref
        return ref

    def resolve(self, name: str) -> CheckpointRef:
        if name not in self._refs:
            raise KeyError(f"checkpoint not registered: {name}")
        return self._refs[name]

    def records(self) -> tuple[dict[str, object], ...]:
        return tuple(ref.as_record() for ref in self._refs.values())
