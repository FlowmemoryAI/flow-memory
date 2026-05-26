from flow_memory.rl.registry import make_env
from flow_memory.rl.vector_env import FlowVectorEnv

def test_vector_env_steps_multiple_envs_deterministically() -> None:
    vec = FlowVectorEnv([lambda: make_env("gridworld", seed=1), lambda: make_env("gridworld", seed=2)])
    obs = vec.reset(seed=10)
    assert len(obs) == 2
    steps = vec.step([1, 1])
    assert len(steps) == 2
