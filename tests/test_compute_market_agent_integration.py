from flow_memory.agents.profile import AgentProfile
from flow_memory.agents.runner import AgentRunner


def compute_config(max_total_cost: float = 0.01):
    return {
        "enabled": True,
        "task_profile": {"model": "small-general", "expected_input_tokens": 1000, "expected_output_tokens": 500},
        "budget_policy": {"max_total_cost": max_total_cost, "max_quote": max_total_cost, "dry_run_required": True, "strategy": "cheapest_eligible", "payment_rail": "local_credits"},
    }


def test_agent_compute_binding_serialization_defaults():
    profile = AgentProfile(name="compute", compute_config=compute_config())
    record = profile.as_record()

    assert record["compute_config"]["enabled"] is True
    assert profile.validate() == ()


def test_agent_runner_records_compute_economic_memory():
    profile = AgentProfile(name="compute", identity="did:flow:compute-agent", allowed_tools=("respond",), compute_config=compute_config())
    result = AgentRunner(profile).run_cycle("Explore and report")

    assert result.accepted is True
    assert result.output["compute"]["status"] == "planned"
    assert result.output["compute"]["economic_memory"]["no_funds_moved"] is True
    assert any(record["kind"] == "compute_economic_memory" for record in result.memory_records)


def test_agent_compute_fail_closed_when_policy_missing():
    profile = AgentProfile(name="compute", allowed_tools=("respond",), compute_config={"enabled": True})
    result = AgentRunner(profile).run_cycle("Explore and report")

    assert result.accepted is False
    assert result.requires_approval is True
    assert result.output["compute"]["status"] == "fail_closed"
    assert "budget policy missing" in result.output["reason"]


def test_agent_compute_fail_closed_when_over_budget():
    profile = AgentProfile(name="compute", allowed_tools=("respond",), compute_config=compute_config(max_total_cost=0.00000001))
    result = AgentRunner(profile).run_cycle("Explore and report")

    assert result.accepted is False
    assert result.output["compute"]["status"] == "fail_closed"
    assert "exceeds budget" in result.output["reason"]
