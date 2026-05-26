from flow_memory.flowlang.parser import parse_flowlang
from flow_memory.ir.agent_adapter import agent_profile_from_ir


def test_flowlang_neural_block_compiles_to_profile() -> None:
    source = """
agent NeuralAgent
identity did:flow:neural
neural:
  backend: tiny_torch
  perception: dual_stream
goal: Explore
skill local:
  permissions: [respond]
  risk: low
plan p:
  steps: [local]
"""
    agent = parse_flowlang(source)
    profile = agent_profile_from_ir(agent)
    assert profile.neural_config["backend"] == "tiny_torch"
