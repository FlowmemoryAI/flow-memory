from flow_memory.api.router import create_default_router

def test_neural_router_endpoints_return_metadata():
    router=create_default_router()
    status=router.dispatch("GET", "/neural/status")
    assert status["ok"] is True
    assert "torch" in status
    assert router.dispatch("GET", "/neural/backends")["backends"]
    assert "checkpoints" in router.dispatch("GET", "/neural/checkpoints")

def test_neural_gpu_runs_route_handles_absent_evidence():
    router=create_default_router()
    runs=router.dispatch("GET", "/neural/gpu-runs")
    assert "runs" in runs
