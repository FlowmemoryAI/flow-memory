import pytest


def test_neural_losses_run_with_torch() -> None:
    torch = pytest.importorskip("torch")
    from flow_memory.neural.training.losses import predictive_latent_loss, temporal_consistency_loss

    x = torch.zeros((1, 2, 4))
    assert predictive_latent_loss(x, x).item() == 0
    assert temporal_consistency_loss(x).item() == 0
