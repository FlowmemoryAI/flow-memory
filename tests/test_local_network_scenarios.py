import json
import subprocess
import sys
from pathlib import Path

from flow_memory.network import LocalNetworkOrchestrator, default_topology

ROOT = Path(__file__).resolve().parents[1]


def test_local_network_topology_roles_exist() -> None:
    topology = default_topology()
    assert topology.by_role("requester").profile.identity == "did:flow:requester"
    assert topology.by_role("worker").card.has_capability("submit_work")
    assert topology.by_role("verifier").card.has_capability("verify_work")


def test_local_network_basic_economy() -> None:
    report = LocalNetworkOrchestrator().run("basic-economy")
    assert report.ok is True
    assert report.scenarios[0].data["status"] == "settled"


def test_local_network_neural_agent() -> None:
    report = LocalNetworkOrchestrator().run("neural-agent")
    assert report.ok is True
    assert report.scenarios[0].data["neural"]["backend"] == "tiny_torch"


def test_local_network_rl_training() -> None:
    report = LocalNetworkOrchestrator().run("rl-training")
    assert report.ok is True
    assert report.scenarios[0].data["advisory_only"] is True


def test_local_network_dispute_slashing() -> None:
    report = LocalNetworkOrchestrator().run("dispute-slashing")
    assert report.ok is True
    assert report.scenarios[0].data["status"] == "slashed"


def test_local_network_memory_learning() -> None:
    report = LocalNetworkOrchestrator().run("memory-learning")
    assert report.ok is True
    assert report.scenarios[0].data["memory_writes"]


def test_local_network_safety_approval() -> None:
    report = LocalNetworkOrchestrator().run("safety-approval")
    assert report.ok is True
    decision = report.scenarios[0].data["policy_decision"]
    assert decision["requires_human"] is True


def test_local_network_visual_events_from_all_scenarios() -> None:
    report = LocalNetworkOrchestrator().run("all", emit_visual_events=True)
    record = report.as_record()
    assert report.ok is True
    assert record["visual_events"]
    assert record["visual_state"]["runtime"]["agents"] == 4
    scenario_names = {scenario.scenario for scenario in report.scenarios}
    assert {"memory-learning", "safety-approval"} <= scenario_names


def test_run_local_network_script_writes_json_report(tmp_path: Path) -> None:
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
