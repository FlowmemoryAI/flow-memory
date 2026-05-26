import pytest


def test_flow_memory_and_neural_import_without_torch() -> None:
    import flow_memory
    import flow_memory.neural as neural

    assert flow_memory.__version__
    assert isinstance(neural.is_torch_available(), bool)


def test_torch_feature_fails_clearly_without_torch() -> None:
    from flow_memory.neural import is_torch_available, OptionalDependencyError
    from flow_memory.neural.perception.ventral import TinyVentralEncoder

    if is_torch_available():
        pytest.skip("torch available")
    with pytest.raises(OptionalDependencyError):
        TinyVentralEncoder()
