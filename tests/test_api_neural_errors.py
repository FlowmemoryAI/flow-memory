from flow_memory.api.http_server import HttpApiConfig, HttpApiGateway

def test_neural_unknown_gpu_run_returns_structured_error():
    gateway=HttpApiGateway(config=HttpApiConfig(enable_rate_limit=False))
    response=gateway.handle("GET", "/neural/gpu-runs/does-not-exist", {"x-flow-memory-scopes":"neural:evidence"})
    assert response.status == 404
    assert response.body["error"]["code"] == "request.invalid"
