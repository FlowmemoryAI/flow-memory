from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.flowlang.runner import run_flowlang_agent


def run_demo() -> dict[str, object]:
    result = dict(run_flowlang_agent(ROOT / "examples" / "flowlang_agent.flow", "Run the declared agent"))
    return {
        "ok": bool(result.get("accepted") or result.get("requires_approval")),
        "launch_mode": "flowlang",
        "result": result,
        "safety_authority": "policy_engine_and_approval_gate",
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2, sort_keys=True, default=str))
