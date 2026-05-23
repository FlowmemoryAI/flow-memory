import pytest


def test_tiny_ventral_encoder_shape():
    torch = pytest.importorskip("torch")
    from flow_memory.neural.perception.ventral import TinyVentralEncoder

    features = TinyVentralEncoder(latent_dim=8)(torch.rand((1, 4, 3, 8, 8)))
    assert tuple(features.semantic_tokens.shape) == (1, 1, 8)
