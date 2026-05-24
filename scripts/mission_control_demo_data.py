"""Generate Mission Control demo data from a real local network run."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flow_memory.network import LocalNetworkOrchestrator
from scripts.export_visual_replay import export_visual_replay


def generate_demo_data(*, scenario: str = "all", report_out: Path | None = None, replay_out: Path | None = None) -> dict[str, object]:
    report_path = report_out or ROOT / "artifacts" / "network" / "mission_control_demo_report.json"
    replay_path = replay_out or ROOT / "dashboard" / "src" / "mock-data" / "local-network-replay.json"
    report = LocalNetworkOrchestrator().run(scenario, emit_visual_events=True).as_record()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    replay = export_visual_replay(report_path, replay_path)
    return {
        "ok": bool(report.get("ok")) and bool(replay.get("ok")),
        "scenario": scenario,
        "report_path": str(report_path),
        "replay_path": str(replay_path),
        "event_count": replay["metadata"]["event_count"],
        "agent_count": replay["metadata"]["agent_count"],
        "task_count": replay["metadata"]["task_count"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Mission Control demo data")
    parser.add_argument("--scenario", default="all")
    parser.add_argument("--report-out", type=Path, default=None)
    parser.add_argument("--replay-out", type=Path, default=None)
    args = parser.parse_args()
    payload = generate_demo_data(scenario=args.scenario, report_out=args.report_out, replay_out=args.replay_out)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
