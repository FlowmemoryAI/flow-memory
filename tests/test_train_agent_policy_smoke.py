import pytest


def test_train_agent_policy_smoke() -> None:
    pytest.importorskip("torch")
    from flow_memory.neural.training.train_agent_policy import train_smoke

    result = train_smoke(steps=1)
    assert result["ok"] is True
