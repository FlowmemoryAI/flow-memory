import pytest


def test_tiny_dorsal_encoder_shape() -> None:
    torch = pytest.importorskip("torch")
    from flow_memory.neural.perception.dorsal import TinyDorsalMotionEncoder

    video = torch.zeros((1, 4, 3, 8, 8), dtype=torch.float32)
    video[:, :, :, 2:4, 2:4] = 1.0
    features = TinyDorsalMotionEncoder(latent_dim=8)(video)
    assert tuple(features.motion_tokens.shape) == (1, 1, 8)
