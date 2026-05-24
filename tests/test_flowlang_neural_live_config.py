from flow_memory.flowlang.parser import parse_flowlang
from flow_memory.ir.agent_adapter import agent_profile_from_ir


def test_flowlang_brace_neural_live_block_converts_to_agent_profile():
    source = '''
agent LiveResearchAgent {
  goal: "research and summarize local project state"

  neural {
    enabled: true
    backend: "tiny_torch"
    live_mode: true
    learning_enabled: true
    seed: 1337
    model_profile: "local-small"
    perception_streams: ["text", "events", "memory"]
    plan_scoring_enabled: true
    risk_scoring_enabled: true
    memory_retrieval_enabled: true
    telemetry_enabled: true
    policy_fallback: "allow_non_neural"
  }

  policy {
    autonomy: "supervised"
    approval_required: true
  }
}
'''
    spec = parse_flowlang(source)
    profile = agent_profile_from_ir(spec)

    assert profile.name == "LiveResearchAgent"
    assert profile.goals == ("research and summarize local project state",)
    assert profile.neural_config["backend"] == "tiny_torch"
    assert profile.neural_config["live_mode"] is True
    assert profile.neural_config["learning_enabled"] is True
    assert profile.neural_config["perception_streams"] == ["text", "events", "memory"]
    assert not profile.validate()


def test_flowlang_legacy_neural_block_still_round_trips():
    source = '''
agent: legacy
neural:
  backend: tiny_torch
  live_mode: true
  policy_fallback: allow_non_neural
goal: Explore and report
'''
    profile = agent_profile_from_ir(parse_flowlang(source))

    assert profile.neural_config["backend"] == "tiny_torch"
    assert profile.neural_config["live_mode"] is True
    assert profile.neural_config["policy_fallback"] == "allow_non_neural"
