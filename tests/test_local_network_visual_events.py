import json
import subprocess
import sys
from pathlib import Path

from flow_memory.network import LocalNetworkOrchestrator

ROOT = Path(__file__).resolve().parents[1]


def test_network_report_contains_reduced_visual_state_when_enabled():
    report = LocalNetworkOrchestrator().run("all", emit_visual_events=True)
    record = report.as_record()
    assert record["visual_state"]["runtime"]["events"] >= 6
    assert record["visual_state"]["agents"]
    assert record["visual_state"]["tasks"]
    assert record["visual_state"]["safety"]


def test_run_local_network_visual_script_writes_events(tmp_path):
    report_path = tmp_path / "network.json"
    visual_path = tmp_path / "visual.json"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_local_network.py",
            "--scenario",
            "all",
            "--emit-visual-events",
            "--json-out",
            str(report_path),
            "--visual-out",
            str(visual_path),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    visual = json.loads(visual_path.read_text(encoding="utf-8"))
    assert visual["events"]
    assert visual["state"]["runtime"]["agents"] == 4
