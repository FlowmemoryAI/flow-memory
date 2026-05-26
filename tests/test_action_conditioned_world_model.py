import pytest


def test_action_conditioned_world_model_shape() -> None:
    torch = pytest.importorskip("torch")
    from flow_memory.neural.world_model.action_conditioned import TinyActionConditionedWorldModel

    latent = torch.zeros((1, 2, 8))
    action = torch.ones((1, 8))
    assert tuple(TinyActionConditionedWorldModel().predict_next(latent, action).shape) == (1, 2, 8)
