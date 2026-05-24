from flow_memory.rl.envs.economy_market_env import EconomyMarketEnv


def test_economy_market_env_deterministic_success_action():
    env=EconomyMarketEnv(seed=3)
    first=env.step(env.action_labels.index("bid_fair"))
    env.reset(seed=3)
    second=env.step(env.action_labels.index("bid_fair"))
    assert first.reward == second.reward
    assert first.info
