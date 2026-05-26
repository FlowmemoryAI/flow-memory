from flow_memory.neural.config import NeuralBackendConfig
from flow_memory.neural.registry import NeuralBackendRegistry


def test_neural_backend_registry_create() -> None:
    registry = NeuralBackendRegistry()
    registry.register("none", lambda config: {"backend": config.backend})
    assert registry.names() == ("none",)
    assert registry.create(NeuralBackendConfig()).get("backend") == "none"
