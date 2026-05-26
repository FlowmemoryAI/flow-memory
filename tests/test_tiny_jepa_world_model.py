import pytest


def test_tiny_jepa_world_model_predicts_shape() -> None:
    torch = pytest.importorskip("torch")
    from flow_memory.neural.perception.dual_stream import TinyDualStreamEncoder
    from flow_memory.neural.world_model.jepa import TinyJEPAWorldModel

    features = TinyDualStreamEncoder()(torch.rand((1, 4, 3, 8, 8)))
    prediction = TinyJEPAWorldModel().predict(features)
    assert tuple(prediction.predicted_latent.shape) == tuple(features.fused_tokens.shape)
