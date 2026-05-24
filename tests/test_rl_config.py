from flow_memory.rl.config import RLConfig

def test_rl_config_validation():
    assert RLConfig(training_envs=("safety_gate",)).validate() == ()
    assert RLConfig(max_training_steps=-1).validate()
