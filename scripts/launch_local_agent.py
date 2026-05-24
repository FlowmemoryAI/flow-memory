"""Launch a local Flow Memory agent and print a JSON run record."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.agents import AgentProfile, AgentRunner


def launch_local_agent(goal: str) -> dict[str, object]:
    profile = AgentProfile(
        name="Local Launch Agent",
        identity="did:flow:local-launch-agent",
        description="Public-alpha local launch path agent.",
        goals=(goal,),
        capabilities=("local_reasoning", "safe_tool_use"),
        allowed_tools=("observe_environment", "respond"),
        allowed_skills=("research_brief",),
        autonomy_mode="autonomous_local",
        metadata={"launch_path": "cli"},
    )
    result = AgentRunner(profile).run_cycle(goal)
    return {
        "ok": bool(result.accepted or result.requires_approval),
        "launch_mode": "cli",
        "agent": profile.as_record(),
        "goal": goal,
        "accepted": result.accepted,
        "requires_approval": result.requires_approval,
        "output": dict(result.output),
        "audit_event_count": len(result.audit_events),
        "memory_record_count": len(result.memory_records),
        "safety_authority": "policy_engine_and_approval_gate",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch a local Flow Memory agent")
    parser.add_argument("--goal", default="Explore and report")
    args = parser.parse_args()
    print(json.dumps(launch_local_agent(args.goal), indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
