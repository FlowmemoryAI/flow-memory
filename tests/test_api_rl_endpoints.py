from flow_memory.api.router import create_default_router


def test_rl_router_envs_and_benchmarks():
    router = create_default_router()
    envs = router.dispatch("GET", "/rl/envs")
    assert "safety_gate" in envs["envs"]
    benchmarks = router.dispatch("GET", "/rl/benchmarks")
    assert "benchmarks" in benchmarks


def test_rl_router_evaluate_and_train_smoke():
    router = create_default_router()
    evaluation = router.dispatch("POST", "/rl/evaluate", {"env_id": "safety_gate", "policy": "heuristic", "episodes": 2})
    assert evaluation["ok"] is True
    assert evaluation["metrics"]["mean_success_rate"] == 1.0
    training = router.dispatch("POST", "/rl/train-smoke", {"env_id": "safety_gate", "episodes": 5})
    assert training["ok"] is True
    assert training["training"]["improved"] is True
