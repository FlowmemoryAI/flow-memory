from flow_memory.rl.registry import make_env

def test_flow_env_reset_step_render_close():
    env=make_env("tool_use", seed=7)
    obs=env.reset()
    step=env.step(env.action_labels.index("use_safe_tool"))
    assert obs["env_id"] == "tool_use"
    assert step.done is True
    assert step.info["success"] is True
    assert "tool_use" in env.render()
    env.close()
