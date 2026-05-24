from pathlib import Path

from flow_memory.api.router import create_default_router

ROOT = Path(__file__).resolve().parents[1]


def test_neural_router_manifest_and_read_endpoints():
    router = create_default_router()

    manifest = router.dispatch("GET", "/manifest")
    endpoints = {(endpoint["method"], endpoint["path"], endpoint["name"]) for endpoint in manifest["endpoints"]}
    assert ("GET", "/neural/status", "neural_status") in endpoints
    assert ("POST", "/neural/train-smoke", "neural_train_smoke") in endpoints

    status = router.dispatch("GET", "/neural/status")
    backends = router.dispatch("GET", "/neural/backends")
    runs = router.dispatch("GET", "/neural/gpu-runs")
    benchmarks = router.dispatch("GET", "/neural/benchmarks")

    assert status["ok"] is True
    assert any(backend["name"] == "tiny_torch" for backend in backends["backends"])
    assert "runs" in runs
    assert "benchmarks" in benchmarks


def test_neural_validate_smoke_and_checkpoint_metadata_only():
    router = create_default_router()
    checkpoint_dir = ROOT / "artifacts" / "neural" / "api_endpoint_test" / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = checkpoint_dir / "tiny.pt"
    checkpoint.write_bytes(b"checkpoint bytes")
    try:
        validation = router.dispatch("POST", "/neural/validate-smoke", {"backend": "none"})
        checkpoints = router.dispatch("GET", "/neural/checkpoints")
    finally:
        checkpoint.unlink(missing_ok=True)

    assert validation["ok"] is True
    assert checkpoints["raw_weights_returned"] is False
    record = next(item for item in checkpoints["checkpoints"] if item["name"] == "tiny.pt")
    assert record["size_bytes"] == len(b"checkpoint bytes")
    assert "checkpoint bytes" not in str(record)
