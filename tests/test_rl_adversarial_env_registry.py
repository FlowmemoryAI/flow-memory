from flow_memory.rl.registry import env_names, make_env
from flow_memory.rl.vector_env import FlowVectorEnv


def test_adversarial_envs_are_registered_and_vectorizable():
    names = set(env_names())
    expected = {"reputation_gaming", "sybil_risk", "colluding_verifier"}
    assert expected <= names

    vector = FlowVectorEnv(tuple(lambda name=name: make_env(name, seed=5) for name in sorted(expected)))
    observations = vector.reset(seed=21)
    assert tuple(obs["env_id"] for obs in observations) == tuple(sorted(expected))
    results = vector.step([0, 0, 0])
    assert len(results) == 3
    assert all("metrics" in result.info for result in results)
