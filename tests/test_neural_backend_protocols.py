from typing import get_type_hints

from flow_memory.neural.backends.base import NeuralVideoBackend


def test_neural_backend_protocol_exists():
    assert NeuralVideoBackend
