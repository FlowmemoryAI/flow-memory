import json
from flow_memory.rl.policies import TabularQPolicy
from flow_memory.rl.wasm_export import export_tabular_policy

def test_export_tabular_policy_for_browser_demo(tmp_path):
    out=tmp_path/"policy.json"
    export_tabular_policy(TabularQPolicy(q={"s":[0.0,1.0]}), out)
    data=json.loads(out.read_text())
    assert data["format"] == "flow-memory-tabular-q-v1"
