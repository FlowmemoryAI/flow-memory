from flow_memory.rl.envs.memory_retrieval_env import MemoryRetrievalEnv


def test_memory_retrieval_env_deterministic_success_action():
    env=MemoryRetrievalEnv(seed=3)
    first=env.step(env.action_labels.index("retrieve_relevant_memory"))
    env.reset(seed=3)
    second=env.step(env.action_labels.index("retrieve_relevant_memory"))
    assert first.reward == second.reward
    assert first.info
