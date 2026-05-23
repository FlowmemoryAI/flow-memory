"""Tiny dual-stream neural perception encoder."""

from __future__ import annotations

from flow_memory.neural.features import DualStreamFeatures
from flow_memory.neural.perception.dorsal import TinyDorsalMotionEncoder
from flow_memory.neural.perception.ventral import TinyVentralEncoder
from flow_memory.neural.torch_optional import require_torch


class TinyDualStreamEncoder:
    def __init__(self, latent_dim: int = 8) -> None:
        self.torch = require_torch()
        self.ventral = TinyVentralEncoder(latent_dim=latent_dim)
        self.dorsal = TinyDorsalMotionEncoder(latent_dim=latent_dim)
        self.latent_dim = latent_dim

    def encode(self, video):
        ventral = self.ventral(video)
        dorsal = self.dorsal(video)
        fused = self.torch.cat([ventral.semantic_tokens, dorsal.motion_tokens], dim=1)
        return DualStreamFeatures(ventral=ventral, dorsal=dorsal, fused_tokens=fused, metadata={"latent_dim": self.latent_dim})

    def __call__(self, video):
        return self.encode(video)
