from __future__ import annotations

import json
from pathlib import Path

from flow_memory.neural import is_torch_available


def main() -> dict[str, object]:
    if not is_torch_available():
        return {"ok": True, "skipped": True, "reason": "torch not installed"}
    from flow_memory.neural.perception.dual_stream import TinyDualStreamEncoder
    from flow_memory.neural.training.synthetic_motion_dataset import SyntheticMotionDataset
    from flow_memory.neural.world_model.jepa import TinyJEPAWorldModel
    from flow_memory.neural.world_model.surprise import compute_surprise_score

    video, _sample = SyntheticMotionDataset(size=1, seed=22).as_torch(0)
    features = TinyDualStreamEncoder()(video)
    prediction = TinyJEPAWorldModel().predict(features)
    matched = compute_surprise_score(prediction, prediction.predicted_latent, prediction.predicted_dorsal).free_energy_proxy
    mismatched = compute_surprise_score(prediction, features.fused_tokens + 1.0, features.dorsal.motion_tokens + 1.0).free_energy_proxy
    return {"ok": True, "matched_surprise": matched, "mismatched_surprise": mismatched, "separation": mismatched - matched}


if __name__ == "__main__":
    result = main()
    Path(".flow_memory").mkdir(exist_ok=True)
    Path(".flow_memory/neural_world_model_prediction_benchmark.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
