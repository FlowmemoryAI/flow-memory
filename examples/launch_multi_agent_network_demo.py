from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.network import LocalNetworkOrchestrator


def run_demo() -> dict[str, object]:
    report = LocalNetworkOrchestrator().run("basic-economy").as_record()
    return {"ok": bool(report.get("ok")), "launch_mode": "multi_agent_network", "report": report}


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2, sort_keys=True, default=str))
