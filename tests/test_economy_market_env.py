from flow_memory.rl.envs.economy_market_env import EconomyMarketEnv


def test_economy_market_env_deterministic_success_action():
    env=EconomyMarketEnv(seed=3)
    first=env.step(env.action_labels.index("bid_fair"))
    env.reset(seed=3)
    second=env.step(env.action_labels.index("bid_fair"))
    assert first.reward == second.reward
    assert first.info


def test_economy_market_multi_round_settles_after_verifier_selection():
    env = EconomyMarketEnv(seed=5, episode_mode="multi_round", max_steps=5)
    obs = env.reset(seed=5)
    assert obs["economy"]["phase"] == "open"
    bid = env.step(env.action_labels.index("bid_low"))
    assert bid.info["metrics"]["phase"] == "bidding"
    assert bid.observation["economy"]["bid_round"] == 1
    improve = env.step(env.action_labels.index("bid_fair"))
    assert improve.observation["economy"]["selected_bid"] == "bid_fair"
    verifier = env.step(env.action_labels.index("request_verifier"))
    assert verifier.observation["economy"]["verifier_selected"] is True
    settle = env.step(env.action_labels.index("bid_fair"))
    assert settle.done is True
    assert settle.reward > 0
    assert settle.info["metrics"]["settlement"] is True


def test_economy_market_multi_round_overpriced_bid_disputes():
    env = EconomyMarketEnv(seed=5, episode_mode="multi_round", max_steps=5)
    env.step(env.action_labels.index("bid_low"))
    disputed = env.step(env.action_labels.index("bid_high"))
    assert disputed.reward < 0
    assert disputed.info["metrics"]["dispute"] is True
    assert disputed.observation["economy"]["open_disputes"] == 1
