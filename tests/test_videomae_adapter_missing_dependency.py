import pytest

from flow_memory.neural import OptionalDependencyError
from flow_memory.neural.backends.videomae import VideoMAEAdapter
from flow_memory.neural.config import NeuralBackendConfig


def test_videomae_adapter_requires_local_checkpoint_or_dependency() -> None:
    with pytest.raises(OptionalDependencyError):
        VideoMAEAdapter(NeuralBackendConfig(backend="videomae"))
