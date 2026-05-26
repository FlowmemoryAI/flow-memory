import pytest


def test_tiny_dual_stream_encoder_shape() -> None:
    torch = pytest.importorskip("torch")
    from flow_memory.neural.perception.dual_stream import TinyDualStreamEncoder

    features = TinyDualStreamEncoder(latent_dim=8)(torch.rand((1, 4, 3, 8, 8)))
    assert tuple(features.fused_tokens.shape) == (1, 2, 8)
