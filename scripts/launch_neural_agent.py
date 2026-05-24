"""Launch a Flow Memory agent with optional neural advisory metadata."""
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


def launch_neural_agent(goal: str, backend: str = "tiny_torch") -> dict[str, object]:
    profile = AgentProfile(
        name="Neural Launch Agent",
        identity="did:flow:neural-launch-agent",
        description="Public-alpha launch path with neural advisory scoring.",
        goals=(goal,),
        capabilities=("local_reasoning", "neural_advisory"),
        allowed_tools=("observe_environment", "respond"),
        allowed_skills=("research_brief",),
        neural_config={"backend": backend, "perception": "dual_stream", "world_model": "tiny_jepa", "plan_scorer": "tiny"},
        autonomy_mode="supervised",
        metadata={"launch_path": "neural"},
    )
    result = AgentRunner(profile).run_cycle(goal)
    neural = dict(result.output.get("neural", {}))
    return {
        "ok": bool(result.accepted or result.requires_approval),
        "launch_mode": "neural",
        "backend": backend,
        "goal": goal,
        "accepted": result.accepted,
        "requires_approval": result.requires_approval,
        "neural": neural,
        "fallback_or_skip_reason": neural.get("reason", ""),
        "safety_authority": neural.get("safety_authority", "policy_engine_and_approval_gate"),
        "audit_event_count": len(result.audit_events),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch a neural-advisory Flow Memory agent")
    parser.add_argument("--backend", default="tiny_torch", choices=("none", "tiny_torch", "vjepa2", "videomae"))
    parser.add_argument("--goal", default="Explore and report")
    args = parser.parse_args()
    print(json.dumps(launch_neural_agent(args.goal, args.backend), indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
