"""Neural backend registry."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flow_memory.neural.config import NeuralBackendConfig

BackendFactory = Callable[[NeuralBackendConfig], Any]


class NeuralBackendRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, BackendFactory] = {}

    def register(self, name: str, factory: BackendFactory) -> None:
        if not name.strip():
            raise ValueError("backend name is required")
        self._factories[name] = factory

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._factories))

    def create(self, config: NeuralBackendConfig) -> Any:
        if config.backend not in self._factories:
            raise KeyError(f"neural backend is not registered: {config.backend}")
        errors = config.validate()
        if errors:
            raise ValueError("; ".join(errors))
        return self._factories[config.backend](config)
