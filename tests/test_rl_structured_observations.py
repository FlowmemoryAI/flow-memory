from flow_memory.rl.registry import make_env


def test_flow_env_observation_contains_agent_economy_safety_memory_features() -> None:
    env = make_env("economy_market", seed=4)
    obs = env.reset()
    assert set(("agent", "economy", "safety", "memory")).issubset(obs)
    assert obs["agent"]["risk_budget_remaining"] == 1.0
    step = env.step(env.action_labels.index("bid_high"))
    assert step.observation["economy"]["open_disputes"] == 1
    assert step.observation["agent"]["risk_budget_remaining"] < 1.0


def test_memory_actions_update_memory_feature() -> None:
    env = make_env("memory_retrieval", seed=4)
    step = env.step(env.action_labels.index("retrieve_relevant_memory"))
    assert step.observation["memory"]["relevance"] > 0
