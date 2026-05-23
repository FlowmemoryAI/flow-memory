"""Protocols for language-neutral neural backend seams."""

from __future__ import annotations

from typing import Any, Protocol


class NeuralVideoBackend(Protocol):
    def encode_video(self, video: Any) -> Any: ...
    def encode_latents(self, video: Any) -> Any: ...


class NeuralWorldModelBackend(Protocol):
    def predict_next_latent(self, latent: Any, action: Any | None = None) -> Any: ...


class NeuralMemoryBackend(Protocol):
    def embed(self, item: Any) -> tuple[float, ...]: ...


class NeuralPolicyBackend(Protocol):
    def score(self, *args: Any, **kwargs: Any) -> Any: ...
