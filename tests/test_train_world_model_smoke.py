import pytest


def test_train_world_model_smoke() -> None:
    pytest.importorskip("torch")
    from flow_memory.neural.training.train_world_model import train_smoke

    result = train_smoke(steps=1)
    assert result["ok"] is True
