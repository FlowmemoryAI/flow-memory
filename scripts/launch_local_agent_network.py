"""Launch the local multi-agent Flow Memory network demo."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.network import LocalNetworkOrchestrator


def launch_local_agent_network(scenario: str = "all") -> dict[str, object]:
    report = LocalNetworkOrchestrator().run(scenario).as_record()
    return {"ok": bool(report.get("ok")), "launch_mode": "local_agent_network", "report": report}


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch a local Flow Memory multi-agent network")
    parser.add_argument("--scenario", default="all", choices=("basic-economy", "neural-agent", "rl-training", "dispute-slashing", "all"))
    args = parser.parse_args()
    payload = launch_local_agent_network(args.scenario)
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
