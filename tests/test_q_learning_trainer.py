from flow_memory.rl.policies import TabularQPolicy
from flow_memory.rl.registry import make_env
from flow_memory.rl.trainer import SimpleQLearningTrainer

def test_q_learning_trainer_improves_simple_safety_env():
    env=make_env("safety_gate", seed=0)
    trainer=SimpleQLearningTrainer(env, TabularQPolicy(epsilon=0.0, seed=0))
    result=trainer.train(episodes=20)
    assert result.improved is True
    assert result.mean_reward_after >= result.mean_reward_before
