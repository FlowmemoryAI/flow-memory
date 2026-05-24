from flow_memory.agents.profile import AgentProfile
from flow_memory.agents.runner import AgentRunner
from flow_memory.neural import is_torch_available


def test_agent_runner_records_neural_live_step_with_allowed_fallback():
    profile = AgentProfile(
        name="live",
        allowed_tools=("respond",),
        neural_config={
            "enabled": True,
            "backend": "tiny_torch",
            "live_mode": True,
            "learning_enabled": True,
            "policy_fallback": "allow_non_neural",
            "telemetry_enabled": True,
            "seed": 123,
        },
    )

    result = AgentRunner(profile).run_cycle("Explore and report")

    assert result.accepted is True
    assert result.output["neural"]["live_step"]["ok"] is True
    assert result.output["neural"]["session_id"]
    assert any(record["kind"] == "neural_live_step" for record in result.memory_records)
    assert result.output["neural"]["live_step"]["safety_authority"] == "policy_engine_and_approval_gate"


def test_agent_runner_neural_live_fail_closed_when_unavailable_and_required():
    profile = AgentProfile(
        name="live-fail",
        allowed_tools=("respond",),
        neural_config={
            "enabled": True,
            "backend": "tiny_torch",
            "live_mode": True,
            "policy_fallback": "fail_closed",
            "telemetry_enabled": True,
        },
    )

    result = AgentRunner(profile).run_cycle("Explore and report")

    if is_torch_available():
        assert result.accepted is True
    else:
        assert result.accepted is False
        assert result.requires_approval is True
        assert result.output["neural"]["status"] == "fail_closed"
        assert any(record["kind"] == "neural_fail_closed" for record in result.memory_records)


def test_agent_profile_validates_neural_live_policy_fallback():
    profile = AgentProfile(name="bad", neural_config={"backend": "tiny_torch", "policy_fallback": "unsafe_bypass"})
    assert "unknown neural policy_fallback: unsafe_bypass" in profile.validate()
