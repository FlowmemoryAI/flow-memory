import pytest


def test_appearance_free_transform_shapes():
    torch = pytest.importorskip("torch")
    from flow_memory.neural.perception.appearance_free import AppearanceFreeTransform

    video = torch.zeros((1, 3, 3, 8, 8), dtype=torch.float32)
    video[:, :, :, 2:4, 2:4] = 1.0
    views = AppearanceFreeTransform()(video)
    assert tuple(views.flow_proxy.shape) == (1, 2, 2, 8, 8)
