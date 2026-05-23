from __future__ import annotations

import json
from pathlib import Path

from flow_memory.neural import is_torch_available


def main() -> dict[str, object]:
    if not is_torch_available():
        return {"ok": True, "skipped": True, "reason": "torch not installed"}
    import torch
    from flow_memory.neural.perception.dual_stream import TinyDualStreamEncoder
    from flow_memory.neural.training.appearance_free_dataset import AppearanceFreeMotionDataset

    dataset = AppearanceFreeMotionDataset(size=4, seed=21)
    encoder = TinyDualStreamEncoder()
    invariance = []
    for index in range(len(dataset)):
        a, b, _sample = dataset.as_torch_pair(index)
        fa = encoder(a).dorsal.motion_tokens
        fb = encoder(b).dorsal.motion_tokens
        invariance.append(float(1.0 / (1.0 + torch.mean((fa - fb) ** 2).item())))
    return {"ok": True, "appearance_invariance_score": sum(invariance) / len(invariance), "samples": len(invariance)}


if __name__ == "__main__":
    result = main()
    Path(".flow_memory").mkdir(exist_ok=True)
    Path(".flow_memory/neural_appearance_free_motion_benchmark.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
