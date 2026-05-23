import pytest


def test_tiny_torch_backend_encodes_when_torch_available():
    torch = pytest.importorskip("torch")
    from flow_memory.neural.backends.tiny_torch import TinyTorchBackend

    backend = TinyTorchBackend()
    assert tuple(backend.encode_latents(torch.rand((1, 4, 3, 8, 8))).shape) == (1, 2, 8)
