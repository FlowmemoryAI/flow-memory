"""Appearance-suppression transforms for dorsal motion encoding."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from flow_memory.neural.torch_optional import require_torch, tensor_shape


@dataclass(frozen=True)
class AppearanceFreeViews:
    grayscale: Any
    frame_delta: Any
    edge_proxy: Any
    flow_proxy: Any
    silhouette: Any
    randomized: Any
    metadata: Mapping[str, Any]

    def as_record(self) -> Mapping[str, Any]:
        return {key: tensor_shape(getattr(self, key)) for key in ("grayscale", "frame_delta", "edge_proxy", "flow_proxy", "silhouette", "randomized")} | {"metadata": dict(self.metadata)}


class AppearanceFreeTransform:
    def __init__(self, threshold: float = 0.05) -> None:
        self.threshold = threshold

    def __call__(self, video: Any) -> AppearanceFreeViews:
        if hasattr(video, "ndim"):
            return self._torch(video)
        raise ValueError("AppearanceFreeTransform currently expects a torch tensor [B,T,C,H,W]")

    def _torch(self, video: Any) -> AppearanceFreeViews:
        torch = require_torch()
        if video.ndim != 5:
            raise ValueError(f"video must use [B,T,C,H,W], got {tuple(video.shape)}")
        grayscale = video.mean(dim=2, keepdim=True)
        delta = torch.zeros_like(grayscale)
        delta[:, 1:] = (grayscale[:, 1:] - grayscale[:, :-1]).abs()
        gx = torch.zeros_like(grayscale)
        gy = torch.zeros_like(grayscale)
        gx[..., :, 1:] = (grayscale[..., :, 1:] - grayscale[..., :, :-1]).abs()
        gy[..., 1:, :] = (grayscale[..., 1:, :] - grayscale[..., :-1, :]).abs()
        edge = gx + gy
        flow_scalar = delta[:, 1:]
        flow_proxy = torch.cat([flow_scalar, flow_scalar], dim=2)
        silhouette = (grayscale > self.threshold).to(video.dtype)
        means = video.mean(dim=(-1, -2), keepdim=True).clamp_min(1e-6)
        randomized = silhouette.repeat(1, 1, 3, 1, 1) * means.flip(2)
        return AppearanceFreeViews(grayscale, delta, edge, flow_proxy, silhouette, randomized, {"threshold": self.threshold})
