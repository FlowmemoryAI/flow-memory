"""CPU-safe tiny world-model smoke trainer."""

from __future__ import annotations

from pathlib import Path

from flow_memory.neural.perception.dual_stream import TinyDualStreamEncoder
from flow_memory.neural.training.synthetic_motion_dataset import SyntheticMotionDataset
from flow_memory.neural.torch_optional import OptionalDependencyError, require_torch
from flow_memory.neural.world_model.jepa import TinyJEPAWorldModel
from flow_memory.neural.world_model.surprise import compute_surprise_score


def train_smoke(*, steps: int = 2, checkpoint_dir: str = ".flow_memory/neural_artifacts") -> dict[str, object]:
    try:
        torch = require_torch()
    except OptionalDependencyError as exc:
        return {"ok": False, "skipped": True, "reason": str(exc)}
    dataset = SyntheticMotionDataset(size=max(steps, 1), seed=13)
    encoder = TinyDualStreamEncoder()
    model = TinyJEPAWorldModel()
    scores: list[float] = []
    for index in range(steps):
        video, _sample = dataset.as_torch(index)
        features = encoder(video)
        prediction = model(features)
        scores.append(compute_surprise_score(prediction, features.fused_tokens + 0.01, features.dorsal.motion_tokens + 0.01).free_energy_proxy)
    out = Path(checkpoint_dir)
    out.mkdir(parents=True, exist_ok=True)
    checkpoint = out / "tiny_world_model_smoke.pt"
    torch.save({"scores": scores}, checkpoint)
    return {"ok": True, "scores": scores, "checkpoint": str(checkpoint)}


if __name__ == "__main__":
    import json

    print(json.dumps(train_smoke(), indent=2))
