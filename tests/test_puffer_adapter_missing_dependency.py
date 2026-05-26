import pytest
from flow_memory.rl.puffer_adapter import PufferLibAdapter, PufferLibUnavailable

def test_puffer_adapter_missing_dependency_fails_clearly() -> None:
    adapter=PufferLibAdapter()
    if adapter.available:
        pytest.skip("pufferlib installed locally")
    with pytest.raises(PufferLibUnavailable):
        adapter.make_env("safety_gate")
