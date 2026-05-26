from flow_memory.rl.rewards import RewardSpec

def test_reward_spec_scores_weighted_signals() -> None:
    spec=RewardSpec(task_success=2.0, slashing_penalty=-5.0)
    assert spec.score({"task_success": 1, "slashing_penalty": 1}) == -3.0
    assert "task_success" in spec.as_record()
