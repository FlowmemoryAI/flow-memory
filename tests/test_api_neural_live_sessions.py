from flow_memory.api.router import create_default_router
from flow_memory.api.scopes import NEURAL_READ_SCOPE, NEURAL_TRAIN_SCOPE, NEURAL_VALIDATE_SCOPE, required_scopes_for


def test_api_neural_live_session_lifecycle():
    router = create_default_router()
    created = router.dispatch(
        "POST",
        "/neural/live/sessions",
        {"agent_id": "api-agent", "config": {"enabled": True, "backend": "tiny_torch", "live_mode": True, "policy_fallback": "allow_non_neural", "learning_enabled": True}},
    )
    session_id = created["session"]["session_id"]

    listed = router.dispatch("GET", "/neural/live/sessions")
    assert any(session["session_id"] == session_id for session in listed["sessions"])

    step = router.dispatch("POST", f"/neural/live/sessions/{session_id}/step", {"context": {"goal": "Explore and report"}})
    assert step["step"]["ok"] is True
    assert step["step"]["local_only"] is True

    learning = router.dispatch("POST", f"/neural/live/sessions/{session_id}/learn", {"sample": {"outcome": "success"}})
    assert learning["learning"]["status"] == "learned"

    checkpoint = router.dispatch("POST", f"/neural/live/sessions/{session_id}/checkpoint", {})
    assert checkpoint["checkpoint"]["metadata_only"] is True
    assert checkpoint["raw_weights_exposed"] is False

    stopped = router.dispatch("POST", f"/neural/live/sessions/{session_id}/stop", {})
    assert stopped["stop"]["status"] == "stopped"


def test_api_neural_live_scope_mapping():
    assert required_scopes_for("GET", "/neural/live/sessions") == (NEURAL_READ_SCOPE,)
    assert required_scopes_for("POST", "/neural/live/sessions") == (NEURAL_VALIDATE_SCOPE,)
    assert required_scopes_for("POST", "/neural/live/sessions/session-1/step") == (NEURAL_VALIDATE_SCOPE,)
    assert required_scopes_for("POST", "/neural/live/sessions/session-1/learn") == (NEURAL_TRAIN_SCOPE,)
