"""Tensor contract helpers for optional neural modules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from flow_memory.neural.torch_optional import tensor_shape


@dataclass(frozen=True)
class TensorContract:
    name: str
    expected_rank: int
    convention: str

    def validate(self, value: Any) -> tuple[str, ...]:
        shape = tensor_shape(value)
        if len(shape) != self.expected_rank:
            return (f"{self.name} expected rank {self.expected_rank} ({self.convention}), got shape {shape}",)
        return ()


VIDEO_TENSOR = TensorContract("video", 5, "[B, T, C, H, W]")
LATENT_TOKENS = TensorContract("latent_tokens", 3, "[B, N, D]")
TRAJECTORY = TensorContract("trajectory", 3, "[B, T, 2]")
FLOW_PROXY = TensorContract("flow_proxy", 5, "[B, T-1, 2, H, W]")


def validate_video_tensor(value: Any) -> tuple[str, ...]:
    return VIDEO_TENSOR.validate(value)
