from flow_memory.neural.config import NeuralBackendConfig, neural_config_from_mapping


def test_neural_config_validates_supported_backends() -> None:
    assert NeuralBackendConfig(backend="none").validate() == ()
    assert "unknown neural backend" in NeuralBackendConfig(backend="bogus").validate()[0]


def test_neural_config_from_mapping() -> None:
    cfg = neural_config_from_mapping({"backend": "tiny_torch", "device": "cpu"})
    assert cfg.backend == "tiny_torch"
    assert cfg.device == "cpu"
