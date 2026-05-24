from flow_memory.flowlang.parser import parse_flowlang
from flow_memory.ir.agent_adapter import agent_profile_from_ir

def test_flowlang_rl_config_compiles_to_agent_profile():
    source = "agent RlAgent\nidentity did:example:rl\ngoal Learn safe routing\nrl:\n  enabled: true\n  backend: local_tabular\n  training_envs: [safety_gate, economy_market]\n  max_training_steps: 100\n"
    spec=parse_flowlang(source)
    profile=agent_profile_from_ir(spec)
    assert profile.rl_config["enabled"] is True
    assert profile.rl_config["training_envs"] == ["safety_gate", "economy_market"]
