import pytest

from flow_memory.neural.torch_optional import is_torch_available
from flow_memory.rl.registry import make_env
from flow_memory.rl.torch_policy import TorchPolicy, torch_policy_status, train_torch_policy_smoke


def test_torch_policy_status_imports_without_torch() -> None:
    status = torch_policy_status()
    assert status["backend"] == "torch"
    assert status["available"] in {True, False}


def test_torch_policy_constructor_requires_torch_when_absent() -> None:
    env = make_env("safety_gate")
    if is_torch_available():
        policy = TorchPolicy(env)
        assert env.action_space.contains(policy.act(env.reset(), env))
    else:
        with pytest.raises(ImportError):
            TorchPolicy(env)


def test_torch_policy_smoke_skips_without_torch_or_trains_with_torch() -> None:
    result = train_torch_policy_smoke(steps=1)
    assert result["ok"] is True
    if is_torch_available():
        assert result["skipped"] is False
        assert result["losses"]
    else:
        assert result["skipped"] is True
