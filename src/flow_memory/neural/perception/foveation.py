"""Foveated video processing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from flow_memory.neural.torch_optional import tensor_shape


@dataclass(frozen=True)
class FoveatedVideo:
    center: Any
    peripheral: Any
    metadata: Mapping[str, Any]

    def as_record(self) -> Mapping[str, Any]:
        return {"center_shape": tensor_shape(self.center), "peripheral_shape": tensor_shape(self.peripheral), "metadata": dict(self.metadata)}


class FoveatedVideoProcessor:
    def __init__(self, center_fraction: float = 0.5, peripheral_stride: int = 2) -> None:
        if not 0 < center_fraction <= 1:
            raise ValueError("center_fraction must be in (0, 1]")
        if peripheral_stride < 1:
            raise ValueError("peripheral_stride must be >= 1")
        self.center_fraction = center_fraction
        self.peripheral_stride = peripheral_stride

    def process(self, video: Any) -> FoveatedVideo:
        shape = tensor_shape(video)
        if len(shape) != 5:
            raise ValueError(f"video must use [B, T, C, H, W], got {shape}")
        _, _, _, height, width = shape
        crop_h = max(1, int(height * self.center_fraction))
        crop_w = max(1, int(width * self.center_fraction))
        y0 = (height - crop_h) // 2
        x0 = (width - crop_w) // 2
        if hasattr(video, "__getitem__") and hasattr(video, "ndim"):
            center = video[:, :, :, y0 : y0 + crop_h, x0 : x0 + crop_w]
            peripheral = video[:, :, :, :: self.peripheral_stride, :: self.peripheral_stride]
        else:
            center = _crop_list_video(video, y0, x0, crop_h, crop_w)
            peripheral = _stride_list_video(video, self.peripheral_stride)
        return FoveatedVideo(center=center, peripheral=peripheral, metadata={"center_fraction": self.center_fraction, "peripheral_stride": self.peripheral_stride})


def _crop_list_video(video, y0: int, x0: int, crop_h: int, crop_w: int):
    return [[[[row[x0 : x0 + crop_w] for row in channel[y0 : y0 + crop_h]] for channel in frame] for frame in batch] for batch in video]


def _stride_list_video(video, stride: int):
    return [[[[row[::stride] for row in channel[::stride]] for channel in frame] for frame in batch] for batch in video]
