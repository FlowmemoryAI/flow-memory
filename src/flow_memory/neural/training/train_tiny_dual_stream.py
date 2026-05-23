"""CPU-safe tiny dual-stream smoke trainer."""

from __future__ import annotations

from pathlib import Path

from flow_memory.neural.perception.dual_stream import TinyDualStreamEncoder
from flow_memory.neural.training.appearance_free_dataset import AppearanceFreeMotionDataset
from flow_memory.neural.training.losses import appearance_suppression_loss
from flow_memory.neural.torch_optional import OptionalDependencyError, require_torch


def train_smoke(*, steps: int = 2, checkpoint_dir: str = ".flow_memory/neural_artifacts") -> dict[str, object]:
    try:
        torch = require_torch()
    except OptionalDependencyError as exc:
        return {"ok": False, "skipped": True, "reason": str(exc)}
    dataset = AppearanceFreeMotionDataset(size=max(steps, 1), seed=11)
    encoder = TinyDualStreamEncoder()
    losses: list[float] = []
    for index in range(steps):
        rgb, randomized, _sample = dataset.as_torch_pair(index)
        a = encoder(rgb).dorsal.motion_tokens
        b = encoder(randomized).dorsal.motion_tokens
        losses.append(float(appearance_suppression_loss(a, b).item()))
    out = Path(checkpoint_dir)
    out.mkdir(parents=True, exist_ok=True)
    checkpoint = out / "tiny_dual_stream_smoke.pt"
    torch.save({"losses": losses}, checkpoint)
    return {"ok": True, "losses": losses, "checkpoint": str(checkpoint)}


if __name__ == "__main__":
    import json

    print(json.dumps(train_smoke(), indent=2))
