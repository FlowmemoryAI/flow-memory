from __future__ import annotations

import json
from pathlib import Path

from flow_memory.agents.planner import CognitivePlanner
from flow_memory.neural.agent.plan_scorer import TinyPlanScorer


def main() -> dict[str, object]:
    planner = CognitivePlanner()
    plans = [planner.create_plan("write local report"), planner.create_plan("settle marketplace escrow", allowed_skills=("economic-task",))]
    scores = [score.as_record() for score in TinyPlanScorer().rank(plans)]
    return {"ok": True, "scores": scores}


if __name__ == "__main__":
    result = main()
    Path(".flow_memory").mkdir(exist_ok=True)
    Path(".flow_memory/neural_plan_scoring_benchmark.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
