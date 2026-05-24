import json

from flow_memory.api.http_server import HttpApiConfig, HttpApiGateway


def test_http_gateway_serves_neural_status():
    gateway = HttpApiGateway(config=HttpApiConfig(enable_rate_limit=False))

    response = gateway.handle("GET", "/neural/status", {"x-flow-memory-scopes": "neural:read"})

    assert response.status == 200
    assert response.body["data"]["ok"] is True
    assert "gpu_evidence_ok" in response.body["data"]


def test_http_gateway_neural_train_smoke_runs_local_metadata_only():
    gateway = HttpApiGateway(config=HttpApiConfig(enable_rate_limit=False))
    body = json.dumps(
        {"steps": 1, "seed": 0, "out": "artifacts/neural/http_api_train_smoke"}
    ).encode("utf-8")

    response = gateway.handle("POST", "/neural/train-smoke", {"x-flow-memory-scopes": "neural:train"}, body)

    assert response.status == 200
    assert response.body["data"]["raw_weights_returned"] is False
    assert response.body["data"]["steps"] == 1
