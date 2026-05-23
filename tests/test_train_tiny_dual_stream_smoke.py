import pytest


def test_train_tiny_dual_stream_smoke():
    pytest.importorskip("torch")
    from flow_memory.neural.training.train_tiny_dual_stream import train_smoke

    result = train_smoke(steps=1)
    assert result["ok"] is True
