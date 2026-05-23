"""Tiny JEPA-style latent predictor."""

from __future__ import annotations

from flow_memory.neural.features import DualStreamFeatures, WorldModelPrediction
from flow_memory.neural.torch_optional import require_torch


class TinyJEPAWorldModel:
    def __init__(self, drift_scale: float = 0.1) -> None:
        self.torch = require_torch()
        self.drift_scale = drift_scale

    def predict(self, features: DualStreamFeatures, *, horizon_steps: int = 1) -> WorldModelPrediction:
        torch = self.torch
        fused = features.fused_tokens
        dorsal = features.dorsal.motion_tokens
        drift = dorsal.mean(dim=1, keepdim=True).repeat(1, fused.shape[1], 1) * (self.drift_scale * horizon_steps)
        predicted_latent = fused + drift
        predicted_dorsal = dorsal + dorsal.mean(dim=1, keepdim=True) * (self.drift_scale * horizon_steps)
        uncertainty = float(torch.clamp(drift.abs().mean(), 0, 1).item())
        return WorldModelPrediction(predicted_latent=predicted_latent, predicted_dorsal=predicted_dorsal, horizon_steps=horizon_steps, uncertainty=uncertainty)

    def __call__(self, features: DualStreamFeatures, *, horizon_steps: int = 1) -> WorldModelPrediction:
        return self.predict(features, horizon_steps=horizon_steps)
