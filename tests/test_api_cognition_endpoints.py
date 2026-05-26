import json

from flow_memory.api.http_server import HttpApiConfig, HttpApiGateway
from flow_memory.api.router import create_default_router
from flow_memory.api.scopes import COGNITION_READ_SCOPE, COGNITION_RUN_SCOPE, COGNITION_WRITE_SCOPE, required_scopes_for


def test_router_cognition_predict_and_tick_are_local_and_policy_gated():
    router = create_default_router()

    prediction = router.dispatch(
        "POST",
        "/cognition/predict",
        {"agent_id": "api-cognition-agent", "goal": "verify dashboard", "action": "check mission-control route"},
    )
    tick = router.dispatch(
        "POST",
        "/cognition/tick",
        {"agent": "api-cognition-agent", "goal": "verify dashboard", "action": "check mission-control route", "write_experience": False},
    )

    assert prediction["ok"] is True
    assert prediction["predictions"]
    assert tick["ok"] is True
    assert tick["prediction"]["prediction_id"].startswith("prediction_record_")
    assert tick["experience"]["experience_id"].startswith("experience_")
    assert tick["safety_authority"] == "policy_engine_and_approval_gate"


def test_cognition_api_scopes_are_enforced_by_gateway():
    gateway = HttpApiGateway(config=HttpApiConfig(require_scopes=True, enable_rate_limit=False))
    body = json.dumps({"goal": "verify dashboard", "action": "check mission-control route", "write_experience": False}).encode("utf-8")

    denied = gateway.handle("POST", "/cognition/tick", {"x-flow-memory-scopes": COGNITION_READ_SCOPE}, body)
    allowed = gateway.handle("POST", "/cognition/tick", {"x-flow-memory-scopes": f"{COGNITION_RUN_SCOPE} {COGNITION_WRITE_SCOPE}"}, body)
    read_allowed = gateway.handle(
        "POST",
        "/cognition/predict",
        {"x-flow-memory-scopes": COGNITION_READ_SCOPE},
        json.dumps({"goal": "verify dashboard", "action": "check mission-control route"}).encode("utf-8"),
    )

    assert denied.status == 403
    assert denied.body["error"]["code"] == "auth.forbidden"
    assert allowed.status == 200
    assert allowed.body["data"]["ok"] is True
    assert read_allowed.status == 200
    assert read_allowed.body["data"]["predictions"]

    benchmark_denied = gateway.handle(
        "POST",
        "/cognition/benchmarks/run",
        {"x-flow-memory-scopes": COGNITION_READ_SCOPE},
        json.dumps({"scenario": "dashboard-stale-server", "trials": 2}).encode("utf-8"),
    )
    benchmark_allowed = gateway.handle(
        "POST",
        "/cognition/benchmarks/run",
        {"x-flow-memory-scopes": f"{COGNITION_RUN_SCOPE} {COGNITION_WRITE_SCOPE}"},
        json.dumps({"scenario": "dashboard-stale-server", "trials": 2}).encode("utf-8"),
    )

    assert benchmark_denied.status == 403
    assert benchmark_allowed.status == 200
    assert benchmark_allowed.body["data"]["ok"] is True


def test_cognition_scope_mapping_is_specific_before_launch_and_visual_fallbacks():
    assert required_scopes_for("POST", "/cognition/predict") == (COGNITION_READ_SCOPE,)
    assert required_scopes_for("POST", "/cognition/tick") == (COGNITION_RUN_SCOPE, COGNITION_WRITE_SCOPE)
    assert required_scopes_for("GET", "/cognition/experiences") == (COGNITION_READ_SCOPE,)
    assert required_scopes_for("GET", "/launch/console/runs/demo/predictions") == (COGNITION_READ_SCOPE,)
    assert required_scopes_for("GET", "/visual/embodiment/demo/cognition") == (COGNITION_READ_SCOPE,)
    assert required_scopes_for("POST", "/cognition/benchmarks/run") == (COGNITION_RUN_SCOPE, COGNITION_WRITE_SCOPE)
    assert required_scopes_for("POST", "/cognition/lessons/consolidate") == (COGNITION_WRITE_SCOPE,)
    assert required_scopes_for("GET", "/cognition/lessons") == (COGNITION_READ_SCOPE,)
    assert required_scopes_for("GET", "/cognition/metrics") == (COGNITION_READ_SCOPE,)
