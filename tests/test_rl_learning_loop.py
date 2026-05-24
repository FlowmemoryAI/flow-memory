from flow_memory.learning.rl_learning import run_safety_gate_learning


def test_rl_learning_loop_improves_safety_gate_reward():
    report = run_safety_gate_learning(episodes=20)
    assert report.env_id == "safety_gate"
    assert report.improved is True
    assert report.after >= report.before
