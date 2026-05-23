"""Deterministic tiny synthetic motion dataset."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class SyntheticMotionSample:
    video: list[list[list[list[float]]]]
    direction: str
    speed: int
    trajectory: tuple[tuple[float, float], ...]
    depth_scale: float
    metadata: Mapping[str, Any]

    def as_record(self) -> Mapping[str, Any]:
        return {
            "shape": (len(self.video), len(self.video[0]), len(self.video[0][0]), len(self.video[0][0][0])),
            "direction": self.direction,
            "speed": self.speed,
            "trajectory": tuple(self.trajectory),
            "depth_scale": self.depth_scale,
            "metadata": dict(self.metadata),
        }


class SyntheticMotionDataset:
    """Generate tiny [T, C, H, W] clips with deterministic motion labels."""

    def __init__(self, size: int = 16, *, frames: int = 6, height: int = 16, width: int = 16, seed: int = 0, camera_motion: bool = False) -> None:
        self.size = size
        self.frames = frames
        self.height = height
        self.width = width
        self.seed = seed
        self.camera_motion = camera_motion

    def __len__(self) -> int:
        return self.size

    def __getitem__(self, index: int) -> SyntheticMotionSample:
        rng = random.Random(self.seed + index * 9973)
        directions = (("right", (1, 0)), ("left", (-1, 0)), ("down", (0, 1)), ("up", (0, -1)))
        direction, (dx, dy) = directions[index % len(directions)]
        speed = 1 + (index % 2)
        shape = ("square", "circle", "triangle")[index % 3]
        color = (rng.random() * 0.8 + 0.2, rng.random() * 0.8 + 0.2, rng.random() * 0.8 + 0.2)
        start_x = self.width // 2 - dx * speed * self.frames // 2
        start_y = self.height // 2 - dy * speed * self.frames // 2
        video: list[list[list[list[float]]]] = []
        trajectory: list[tuple[float, float]] = []
        for frame_idx in range(self.frames):
            cam_x = frame_idx if self.camera_motion else 0
            cam_y = frame_idx // 2 if self.camera_motion else 0
            cx = min(max(start_x + dx * speed * frame_idx + cam_x, 2), self.width - 3)
            cy = min(max(start_y + dy * speed * frame_idx + cam_y, 2), self.height - 3)
            trajectory.append((cx / max(1, self.width - 1), cy / max(1, self.height - 1)))
            frame = [[[0.0 for _ in range(self.width)] for _ in range(self.height)] for _ in range(3)]
            for y in range(max(0, cy - 2), min(self.height, cy + 3)):
                for x in range(max(0, cx - 2), min(self.width, cx + 3)):
                    inside = True
                    if shape == "circle":
                        inside = (x - cx) ** 2 + (y - cy) ** 2 <= 5
                    elif shape == "triangle":
                        inside = y >= cy - 2 and abs(x - cx) <= y - (cy - 2)
                    if inside:
                        texture = 0.85 + 0.15 * math.sin((x + y + index) * 1.7)
                        for channel in range(3):
                            frame[channel][y][x] = color[channel] * texture
            video.append(frame)
        return SyntheticMotionSample(
            video=video,
            direction=direction,
            speed=speed,
            trajectory=tuple(trajectory),
            depth_scale=1.0 + 0.05 * speed,
            metadata={"shape": shape, "camera_motion": self.camera_motion, "index": index},
        )

    def as_torch(self, index: int):
        from flow_memory.neural.torch_optional import require_torch

        torch = require_torch()
        sample = self[index]
        return torch.tensor(sample.video, dtype=torch.float32).unsqueeze(0), sample
