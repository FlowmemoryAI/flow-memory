import json
import subprocess
import sys
from pathlib import Path

from flow_memory.network import LocalNetworkOrchestrator, default_topology

ROOT = Path(__file__).resolve().parents[1]


def test_local_network_topology_roles_exist():
    topology = default_topology()
    assert topology.by_role("requester").profile.identity == "did:flow:requester"
    assert topology.by_role("worker").card.has_capability("submit_work")
    assert topology.by_role("verifier").card.has_capability("verify_work")


def test_local_network_basic_economy():
    report = LocalNetworkOrchestrator().run("basic-economy")
    assert report.ok is True
    assert report.scenarios[0].data["status"] == "settled"


def test_local_network_neural_agent():
    report = LocalNetworkOrchestrator().run("neural-agent")
    assert report.ok is True
    assert report.scenarios[0].data["neural"]["backend"] == "tiny_torch"


def test_local_network_rl_training():
    report = LocalNetworkOrchestrator().run("rl-training")
    assert report.ok is True
    assert report.scenarios[0].data["advisory_only"] is True


def test_local_network_dispute_slashing():
    report = LocalNetworkOrchestrator().run("dispute-slashing")
    assert report.ok is True
    assert report.scenarios[0].data["status"] == "slashed"


def test_run_local_network_script_writes_json_report(tmp_path):
    out = tmp_path / "local_network_report.json"
    completed = subprocess.run(
        [sys.executable, "scripts/run_local_network.py", "--scenario", "all", "--json-out", str(out)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert out.exists()
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["ok"] is True
