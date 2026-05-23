"""Paired appearance-randomized and appearance-free synthetic clips."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Mapping

from flow_memory.neural.training.synthetic_motion_dataset import SyntheticMotionDataset


@dataclass(frozen=True)
class AppearanceFreeSample:
    rgb: list[list[list[list[float]]]]
    randomized: list[list[list[list[float]]]]
    silhouette: list[list[list[list[float]]]]
    flow_like: list[list[list[list[float]]]]
    trajectory: tuple[tuple[float, float], ...]
    direction: str
    metadata: Mapping[str, Any]

    def as_record(self) -> Mapping[str, Any]:
        return {"direction": self.direction, "trajectory": tuple(self.trajectory), "metadata": dict(self.metadata)}


class AppearanceFreeMotionDataset:
    def __init__(self, size: int = 16, *, seed: int = 0, frames: int = 6, height: int = 16, width: int = 16) -> None:
        self.base = SyntheticMotionDataset(size=size, seed=seed, frames=frames, height=height, width=width)
        self.seed = seed

    def __len__(self) -> int:
        return len(self.base)

    def __getitem__(self, index: int) -> AppearanceFreeSample:
        sample = self.base[index]
        rng = random.Random(self.seed + index * 1729)
        multipliers = [0.4 + rng.random() * 1.2 for _ in range(3)]
        randomized = _map_video(sample.video, lambda value, channel, _y, _x: min(1.0, value * multipliers[channel] + (0.02 * channel)))
        silhouette = _silhouette(sample.video)
        flow_like = _flow_like(silhouette)
        return AppearanceFreeSample(
            rgb=sample.video,
            randomized=randomized,
            silhouette=silhouette,
            flow_like=flow_like,
            trajectory=sample.trajectory,
            direction=sample.direction,
            metadata=sample.metadata,
        )

    def as_torch_pair(self, index: int):
        from flow_memory.neural.torch_optional import require_torch

        torch = require_torch()
        sample = self[index]
        return torch.tensor(sample.rgb, dtype=torch.float32).unsqueeze(0), torch.tensor(sample.randomized, dtype=torch.float32).unsqueeze(0), sample


def _map_video(video, fn):
    out = []
    for frame in video:
        channels = []
        for channel_idx, channel in enumerate(frame):
            rows = []
            for y, row in enumerate(channel):
                rows.append([fn(value, channel_idx, y, x) for x, value in enumerate(row)])
            channels.append(rows)
        out.append(channels)
    return out


def _silhouette(video):
    out = []
    for frame in video:
        height = len(frame[0])
        width = len(frame[0][0])
        mask = [[0.0 for _ in range(width)] for _ in range(height)]
        for y in range(height):
            for x in range(width):
                value = sum(frame[channel][y][x] for channel in range(3)) / 3.0
                mask[y][x] = 1.0 if value > 0.05 else 0.0
        out.append([mask, mask, mask])
    return out


def _flow_like(video):
    out = []
    previous = video[0]
    out.append(previous)
    for frame in video[1:]:
        height = len(frame[0])
        width = len(frame[0][0])
        delta = [[abs(frame[0][y][x] - previous[0][y][x]) for x in range(width)] for y in range(height)]
        out.append([delta, delta, delta])
        previous = frame
    return out
