"""Tiny local torch backend."""

from __future__ import annotations

from flow_memory.neural.config import NeuralBackendConfig
from flow_memory.neural.perception.dual_stream import TinyDualStreamEncoder
from flow_memory.neural.world_model.action_conditioned import TinyActionConditionedWorldModel


class TinyTorchBackend:
    def __init__(self, config: NeuralBackendConfig | None = None) -> None:
        self.config = config or NeuralBackendConfig(backend="tiny_torch")
        self.encoder = TinyDualStreamEncoder()
        self.world_model = TinyActionConditionedWorldModel()

    def encode_video(self, video):
        return self.encoder(video)

    def encode_latents(self, video):
        return self.encode_video(video).fused_tokens

    def predict_next_latent(self, latent, action=None):
        if action is None:
            action = latent.mean(dim=1)
        return self.world_model.predict_next(latent, action)
