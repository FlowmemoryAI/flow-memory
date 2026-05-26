import pytest


def test_dorsal_more_stable_than_ventral_under_color_change() -> None:
    torch = pytest.importorskip("torch")
    from flow_memory.neural.perception.dual_stream import TinyDualStreamEncoder
    from flow_memory.neural.training.appearance_free_dataset import AppearanceFreeMotionDataset

    rgb, randomized, _sample = AppearanceFreeMotionDataset(size=1, seed=5).as_torch_pair(0)
    encoder = TinyDualStreamEncoder(latent_dim=8)
    a = encoder(rgb)
    b = encoder(randomized)
    dorsal_delta = torch.mean((a.dorsal.motion_tokens - b.dorsal.motion_tokens) ** 2).item()
    ventral_delta = torch.mean((a.ventral.appearance_signature - b.ventral.appearance_signature) ** 2).item()
    assert dorsal_delta <= ventral_delta + 1e-6
