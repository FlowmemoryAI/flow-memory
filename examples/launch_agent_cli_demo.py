from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.agents import AgentProfile, AgentRunner


def run_demo() -> dict[str, object]:
    profile = AgentProfile(
        name="CLI Demo Agent",
        identity="did:flow:cli-demo",
        goals=("Explore and report",),
        capabilities=("local_reasoning",),
        allowed_tools=("observe_environment", "respond"),
        autonomy_mode="autonomous_local",
    )
    result = AgentRunner(profile).run_cycle("Explore and report")
    return {
        "ok": result.accepted,
        "launch_mode": "cli",
        "agent_id": profile.agent_id,
        "memory_records": len(result.memory_records),
        "audit_events": len(result.audit_events),
        "safety_authority": "policy_engine_and_approval_gate",
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), indent=2, sort_keys=True, default=str))
