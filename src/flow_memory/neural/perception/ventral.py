"""Tiny ventral encoder prototype."""

from __future__ import annotations
from typing import Any

from flow_memory.neural.features import VentralFeatures
from flow_memory.neural.torch_optional import require_torch


class TinyVentralEncoder:
    """Small deterministic torch module-like encoder for semantic/appearance tokens."""

    def __init__(self, latent_dim: int = 8) -> None:
        self.torch = require_torch()
        self.latent_dim = latent_dim

    def encode(self, video: Any) -> VentralFeatures:
        torch = self.torch
        if video.ndim != 5:
            raise ValueError(f"video must use [B,T,C,H,W], got {tuple(video.shape)}")
        batch = video.shape[0]
        pooled = video.mean(dim=(1, 3, 4))
        appearance = video.std(dim=(1, 3, 4))
        base = torch.cat([pooled, appearance], dim=1)
        repeats = (self.latent_dim + base.shape[1] - 1) // base.shape[1]
        token = base.repeat(1, repeats)[:, : self.latent_dim]
        semantic_tokens = token.view(batch, 1, self.latent_dim)
        logits = torch.stack([pooled.mean(dim=1), appearance.mean(dim=1)], dim=1)
        return VentralFeatures(semantic_tokens=semantic_tokens, entity_logits=logits, appearance_signature=pooled, metadata={"latent_dim": self.latent_dim})

    def __call__(self, video: Any) -> VentralFeatures:
        return self.encode(video)
