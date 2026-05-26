from flow_memory.rl.envs.gridworld import GridWorld

def test_gridworld_reaches_goal() -> None:
    env = GridWorld(seed=1)
    env.reset()
    for action in (1, 3, 1, 3):
        step = env.step(action)
    assert step.info.get("success") is True
    assert step.reward > 0
