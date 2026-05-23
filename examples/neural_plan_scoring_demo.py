from __future__ import annotations

import json

from flow_memory.agents.planner import CognitivePlanner
from flow_memory.neural.agent.plan_scorer import TinyPlanScorer
from flow_memory.neural.agent.risk_model import TinyRiskModel

plan = CognitivePlanner().create_plan("write local report")
print(json.dumps({"plan": plan.as_record(), "score": TinyPlanScorer().score_plan(plan).as_record(), "risk": TinyRiskModel().score(plan.as_record()).as_record()}, indent=2))
