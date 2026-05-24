import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_script(args: list[str], out: Path) -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, *args, "--json-out", str(out)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    stdout_payload = json.loads(completed.stdout)
    file_payload = json.loads(out.read_text(encoding="utf-8"))
    assert stdout_payload == file_payload
    return file_payload


def test_launch_scripts_write_json_out(tmp_path):
    local = run_script(["scripts/launch_local_agent.py", "--goal", "Explore and report"], tmp_path / "local.json")
    flow = run_script(["scripts/launch_flowlang_agent.py", "examples/flowlang_agent.flow", "--goal", "Run the declared agent"], tmp_path / "flowlang.json")
    neural = run_script(["scripts/launch_neural_agent.py", "--backend", "tiny_torch", "--goal", "Explore and report"], tmp_path / "neural.json")
    network = run_script(["scripts/launch_local_agent_network.py", "--scenario", "basic-economy"], tmp_path / "network.json")
    assert local["launch_mode"] == "cli"
    assert flow["launch_mode"] == "flowlang"
    assert neural["launch_mode"] == "neural"
    assert network["launch_mode"] == "local_agent_network"
