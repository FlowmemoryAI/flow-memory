from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.agents.profile import AgentProfile
from flow_memory.agents.runner import AgentRunner
from flow_memory.flowlang.parser import parse_flowlang_file
from flow_memory.ir.agent_adapter import agent_profile_from_ir


def launch_python_agent(prompt: str = "Explore and report") -> dict[str, object]:
    profile = AgentProfile(
        name="Launch Neural Agent",
        identity="did:flow:launch-demo",
        goals=(prompt,),
        allowed_tools=("respond", "observe_environment"),
        allowed_skills=("research_brief",),
        neural_config={"backend": "tiny_torch"},
        autonomy_mode="supervised",
    )
    result = AgentRunner(profile).run_cycle(prompt)
    return {
        "ok": result.accepted or result.requires_approval,
        "mode": "python_agent",
        "agent": profile.as_record(),
        "neural": result.output.get("neural", {}),
        "requires_approval": result.requires_approval,
        "events": len(result.audit_events),
    }


def launch_flowlang_agent(path: str | Path = ROOT / "examples" / "flowlang_agent.flow") -> dict[str, object]:
    spec = parse_flowlang_file(path)
    profile = agent_profile_from_ir(spec)
    result = AgentRunner(profile).run_cycle("Run the declared agent")
    return {
        "ok": result.accepted or result.requires_approval,
        "mode": "flowlang_agent",
        "agent_name": profile.name,
        "neural": result.output.get("neural", {}),
        "requires_approval": result.requires_approval,
    }


def main() -> int:
    payload = {
        "python_agent": launch_python_agent(),
        "flowlang_agent": launch_flowlang_agent(),
        "safety_authority": "policy_engine_and_approval_gate",
        "commands": {
            "cpu_local": "python -m flow_memory --json \"Explore and report\"",
            "ml_install": "pip install -e \".[dev,ml]\"",
            "tiny_torch": "python -m flow_memory --neural tiny_torch --json \"Explore and report\"",
            "flowlang": "python -m flow_memory --flow examples/flowlang_agent.flow --json \"Run the declared agent\"",
            "api_server": "python scripts/run_local_api_server.py --host 127.0.0.1 --port 8765",
        },
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
