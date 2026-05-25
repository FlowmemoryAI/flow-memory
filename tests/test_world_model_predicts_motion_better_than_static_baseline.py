import pytest


def test_tiny_world_model_static_baseline_contract():
    pytest.importorskip("torch")
    from flow_memory.neural.perception.dual_stream import TinyDualStreamEncoder
    from flow_memory.neural.training.synthetic_motion_dataset import SyntheticMotionDataset
    from flow_memory.neural.world_model.jepa import TinyJEPAWorldModel
    from flow_memory.neural.world_model.surprise import compute_surprise_score

    video, _sample = SyntheticMotionDataset(size=1, seed=9).as_torch(0)
    features = TinyDualStreamEncoder()(video)
    prediction = TinyJEPAWorldModel(drift_scale=0.0).predict(features)
    score = compute_surprise_score(prediction, features.fused_tokens, features.dorsal.motion_tokens)
    assert score.free_energy_proxy >= 0.0
