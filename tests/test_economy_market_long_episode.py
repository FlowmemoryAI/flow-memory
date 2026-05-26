from flow_memory.rl.envs.economy_market_env import EconomyMarketEnv
from flow_memory.rl.vector_env import FlowVectorEnv


def test_economy_market_long_episode_success_lifecycle() -> None:
    env = EconomyMarketEnv(seed=9, episode_mode="long")
    assert env.reset()["economy"]["phase"] == "open"
    first = env.step(env.action_labels.index("bid_fair"))
    assert first.done is False
    assert first.observation["economy"]["phase"] == "bid_submitted"
    second = env.step(env.action_labels.index("request_verifier"))
    assert second.done is False
    assert second.observation["economy"]["phase"] == "verifier_selected"
    final = env.step(env.action_labels.index("bid_fair"))
    assert final.done is True
    assert final.info["settlement"] is True
    assert final.observation["economy"]["phase"] == "settled"
    assert final.observation["agent"]["reputation"] > 0


def test_economy_market_long_episode_dispute_path() -> None:
    env = EconomyMarketEnv(seed=9, episode_mode="long")
    env.reset()
    step = env.step(env.action_labels.index("bid_high"))
    assert step.observation["economy"]["phase"] == "disputed"
    assert step.observation["economy"]["open_disputes"] == 1


def test_economy_market_long_episode_vectorizes() -> None:
    vec = FlowVectorEnv((lambda: EconomyMarketEnv(seed=1, episode_mode="long"), lambda: EconomyMarketEnv(seed=2, episode_mode="long")))
    obs = vec.reset(seed=20)
    assert len(obs) == 2
    steps = vec.step([1, 1])
    assert all(step.observation["economy"]["phase"] == "bid_submitted" for step in steps)
