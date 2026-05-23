import pytest


def test_surprise_increases_for_mismatch():
    torch = pytest.importorskip("torch")
    from flow_memory.neural.features import WorldModelPrediction
    from flow_memory.neural.world_model.surprise import compute_surprise_score

    predicted = torch.zeros((1, 2, 4))
    prediction = WorldModelPrediction(predicted, predicted[:, :1])
    same = compute_surprise_score(prediction, predicted, predicted[:, :1])
    mismatch = compute_surprise_score(prediction, predicted + 1, predicted[:, :1] + 1)
    assert mismatch.free_energy_proxy > same.free_energy_proxy
