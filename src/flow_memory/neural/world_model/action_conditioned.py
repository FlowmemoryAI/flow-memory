"""Tiny action-conditioned world model."""

from __future__ import annotations
from typing import Any

from flow_memory.neural.torch_optional import require_torch


class TinyActionConditionedWorldModel:
    def __init__(self, action_scale: float = 0.05) -> None:
        self.torch = require_torch()
        self.action_scale = action_scale

    def predict_next(self, latent_state: Any, action_embedding: Any) -> Any:
        if latent_state.ndim != 3:
            raise ValueError(f"latent_state must use [B,N,D], got {tuple(latent_state.shape)}")
        if action_embedding.ndim == 2:
            action_embedding = action_embedding.unsqueeze(1)
        action = action_embedding
        if action.shape[-1] != latent_state.shape[-1]:
            repeats = (latent_state.shape[-1] + action.shape[-1] - 1) // action.shape[-1]
            action = action.repeat(1, 1, repeats)[..., : latent_state.shape[-1]]
        return latent_state + action * self.action_scale

    def __call__(self, latent_state: Any, action_embedding: Any) -> Any:
        return self.predict_next(latent_state, action_embedding)
