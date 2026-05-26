"""Tiny dorsal motion encoder with appearance-suppressed trajectory signatures."""

from __future__ import annotations
from typing import Any

from flow_memory.neural.features import DorsalFeatures
from flow_memory.neural.perception.appearance_free import AppearanceFreeTransform
from flow_memory.neural.torch_optional import require_torch


class TinyDorsalMotionEncoder:
    def __init__(self, latent_dim: int = 8) -> None:
        self.torch = require_torch()
        self.latent_dim = latent_dim
        self.transform = AppearanceFreeTransform()

    def encode(self, video: Any) -> DorsalFeatures:
        torch = self.torch
        views = self.transform(video)
        silhouette = views.silhouette
        batch, frames, _, height, width = silhouette.shape
        yy = torch.linspace(0.0, 1.0, height, dtype=video.dtype, device=video.device).view(1, 1, 1, height, 1)
        xx = torch.linspace(0.0, 1.0, width, dtype=video.dtype, device=video.device).view(1, 1, 1, 1, width)
        mass = silhouette.sum(dim=(-1, -2), keepdim=True).clamp_min(1e-6)
        cx = (silhouette * xx).sum(dim=(-1, -2), keepdim=True) / mass
        cy = (silhouette * yy).sum(dim=(-1, -2), keepdim=True) / mass
        centroid = torch.cat([cx.flatten(2), cy.flatten(2)], dim=2).squeeze(1)
        velocity = torch.zeros_like(centroid)
        velocity[:, 1:] = centroid[:, 1:] - centroid[:, :-1]
        signature = torch.cat([centroid.mean(dim=1), velocity.mean(dim=1), velocity[:, -1]], dim=1)
        repeats = (self.latent_dim + signature.shape[1] - 1) // signature.shape[1]
        motion_token = signature.repeat(1, repeats)[:, : self.latent_dim].view(batch, 1, self.latent_dim)
        geometry_token = centroid.reshape(batch, 1, frames * 2)
        depth_proxy = silhouette.sum(dim=(-1, -2)).mean(dim=1)
        egomotion_proxy = velocity.mean(dim=1)
        return DorsalFeatures(
            motion_tokens=motion_token,
            geometry_tokens=geometry_token,
            flow_proxy=views.flow_proxy,
            depth_proxy=depth_proxy,
            egomotion_proxy=egomotion_proxy,
            invariance_metrics={"appearance_suppression": 1.0, "temporal_consistency": float(1.0 / (1.0 + velocity.var().item()))},
            metadata={"latent_dim": self.latent_dim, "trajectory_shape": tuple(centroid.shape)},
        )

    def __call__(self, video: Any) -> DorsalFeatures:
        return self.encode(video)
