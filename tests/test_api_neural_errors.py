import json

from flow_memory.api.http_server import HttpApiConfig, HttpApiGateway


def test_unknown_neural_gpu_run_returns_structured_404():
    gateway = HttpApiGateway(config=HttpApiConfig(enable_rate_limit=False))

    response = gateway.handle("GET", "/neural/gpu-runs/missing-run", {})

    assert response.status == 404
    assert response.body["error"]["code"] == "neural.gpu_run_not_found"
    assert response.body["error"]["details"]["run_id"] == "missing-run"


def test_validate_smoke_unknown_backend_returns_structured_error():
    gateway = HttpApiGateway(config=HttpApiConfig(enable_rate_limit=False))
    body = json.dumps({"backend": "not-a-backend"}).encode("utf-8")

    response = gateway.handle("POST", "/neural/validate-smoke", {}, body)

    assert response.status == 400
    assert response.body["error"]["code"] == "request.invalid"
    assert response.body["error"]["details"]["backend"] == "not-a-backend"


def test_train_smoke_rejects_unsafe_output_path_before_running():
    gateway = HttpApiGateway(config=HttpApiConfig(enable_rate_limit=False))
    body = json.dumps({"out": "../outside"}).encode("utf-8")

    response = gateway.handle("POST", "/neural/train-smoke", {}, body)

    assert response.status == 400
    assert response.body["error"]["code"] == "request.invalid"
