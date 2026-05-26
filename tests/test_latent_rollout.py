import pytest


def test_latent_rollout_returns_predictions() -> None:
    torch = pytest.importorskip("torch")
    from flow_memory.neural.perception.dual_stream import TinyDualStreamEncoder
    from flow_memory.neural.world_model.jepa import TinyJEPAWorldModel
    from flow_memory.neural.world_model.rollout import latent_rollout

    features = TinyDualStreamEncoder()(torch.rand((1, 4, 3, 8, 8)))
    assert len(latent_rollout(TinyJEPAWorldModel(), features, steps=2)) >= 1
