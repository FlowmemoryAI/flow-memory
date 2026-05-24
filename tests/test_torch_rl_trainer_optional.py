from flow_memory.neural.torch_optional import is_torch_available
from flow_memory.rl.torch_trainer import TorchRLTrainerConfig, train_torch_actor_critic_smoke


def test_torch_actor_critic_trainer_skips_without_torch_or_runs():
    result = train_torch_actor_critic_smoke(TorchRLTrainerConfig(steps=1, seed=2))
    assert result["ok"] is True
    if is_torch_available():
        assert result["skipped"] is False
        assert result["backend"] == "torch_actor_critic"
        assert result["losses"]
        assert "before" in result and "after" in result
    else:
        assert result["skipped"] is True
        assert "Optional dependency" in result["reason"]


def test_torch_actor_critic_cuda_request_skips_when_unavailable():
    result = train_torch_actor_critic_smoke(TorchRLTrainerConfig(steps=1, device="cuda"))
    assert result["ok"] is True
    if is_torch_available():
        import torch

        if torch.cuda.is_available():
            assert result["skipped"] is False
            assert result["device"] == "cuda"
        else:
            assert result["skipped"] is True
            assert "CUDA requested" in result["reason"]
    else:
        assert result["skipped"] is True
