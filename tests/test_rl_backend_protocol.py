from flow_memory.rl.backends import LocalRLBackend, RLBackendConfig

def test_local_rl_backend_runs_policy() -> None:
    backend=LocalRLBackend(RLBackendConfig(env_id="tool_use", policy="heuristic"))
    result=backend.evaluate(episodes=2)
    assert result["success_rate"] == 1.0
