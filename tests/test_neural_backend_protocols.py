
from flow_memory.neural.backends.base import NeuralVideoBackend


def test_neural_backend_protocol_exists() -> None:
    assert NeuralVideoBackend.__name__ == "NeuralVideoBackend"
