import pytest

from flow_memory.neural import OptionalDependencyError
from flow_memory.neural.backends.vjepa2 import VJEPA2Adapter
from flow_memory.neural.config import NeuralBackendConfig


def test_vjepa2_adapter_requires_local_checkpoint_or_dependency() -> None:
    with pytest.raises(OptionalDependencyError):
        VJEPA2Adapter(NeuralBackendConfig(backend="vjepa2"))
