from collections.abc import Callable

from flow_memory.rl.env import FlowEnv
from flow_memory.rl.registry import env_names, make_env
from flow_memory.rl.vector_env import FlowVectorEnv

def _factory(name: str) -> Callable[[], FlowEnv]:
    return lambda: make_env(name, seed=5)


def test_adversarial_envs_are_registered_and_vectorizable() -> None:
    names = set(env_names())
    expected = {"reputation_gaming", "sybil_risk", "colluding_verifier"}
    assert expected <= names

    factories: tuple[Callable[[], FlowEnv], ...] = tuple(_factory(name) for name in sorted(expected))
    vector = FlowVectorEnv(factories)
    observations = vector.reset(seed=21)
    assert tuple(obs["env_id"] for obs in observations) == tuple(sorted(expected))
    results = vector.step([0, 0, 0])
    assert len(results) == 3
    assert all("metrics" in result.info for result in results)
