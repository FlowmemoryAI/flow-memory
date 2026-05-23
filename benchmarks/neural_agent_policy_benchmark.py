from __future__ import annotations

import json
from pathlib import Path

from flow_memory.neural.agent.risk_model import TinyRiskModel
from flow_memory.neural.agent.skill_router import TinySkillRouter


def main() -> dict[str, object]:
    risk = TinyRiskModel().score("wallet transfer unsafe action").as_record()
    routes = [score.as_record() for score in TinySkillRouter().rank_skills("research safety", ({"id": "research", "description": "research safety"}, {"id": "wallet", "description": "wallet transfer", "risk": 0.9}))]
    return {"ok": True, "unsafe_plan_flagging": risk, "skill_routing": routes}


if __name__ == "__main__":
    result = main()
    Path(".flow_memory").mkdir(exist_ok=True)
    Path(".flow_memory/neural_agent_policy_benchmark.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
