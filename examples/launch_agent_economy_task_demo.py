from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.economy.economy_v3 import EconomyV3


def run_demo() -> dict[str, object]:
    economy = EconomyV3()
    result = economy.run_success_lifecycle("did:flow:requester", "did:flow:worker", "Summarize local launch readiness", 4.0)
    return {
        "ok": result["status"] == "settled",
        "launch_mode": "economy_task",
        "lifecycle": "create_task -> bid -> assign -> escrow -> submit -> verify -> settle -> reputation_update",
        "result": result,
        "reputation": economy.reputation_for("did:flow:worker").score,
        "simulated_today": True,
        "real_funds_used": False,
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2, sort_keys=True, default=str))
