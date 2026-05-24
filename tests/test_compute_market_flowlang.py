from flow_memory.agents.runner import AgentRunner
from flow_memory.flowlang.parser import parse_flowlang
from flow_memory.ir.agent_adapter import agent_profile_from_ir


FLOW = """
agent Compute Agent
identity did:flow:compute
belief Compute routes are dry-run only
goal Explore and report
tool respond
autonomy autonomous_local
risk_budget 1.0
compute:
  enabled: true
  budget_limit: 0.01
  max_quote: 0.01
  preferred_strategy: cheapest_eligible
  allowed_providers: [local-cpu, market-sim-small]
  allowed_routes: [local-cpu-small, market-small]
  dry_run_required: true
  payment_rail_preference: local_credits
  model: small-general
  expected_input_tokens: 1000
  expected_output_tokens: 500
"""


def test_flowlang_compute_config_round_trips_to_agent_profile():
    spec = parse_flowlang(FLOW)
    profile = agent_profile_from_ir(spec)

    assert spec.metadata["compute_market"]["enabled"] is True
    assert profile.compute_config["budget_policy"]["max_quote"] == 0.01
    assert profile.compute_config["task_profile"]["model"] == "small-general"


def test_flowlang_compute_config_affects_runner_behavior():
    profile = agent_profile_from_ir(parse_flowlang(FLOW))
    result = AgentRunner(profile).run_cycle("Explore and report")

    assert result.accepted is True
    assert result.output["compute"]["status"] == "planned"
    assert result.output["compute"]["payment_intent"]["no_funds_moved"] is True
