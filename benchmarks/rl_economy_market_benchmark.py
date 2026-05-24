from __future__ import annotations

from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


import json
from pathlib import Path
from flow_memory.rl.evaluator import RLEvaluator
from flow_memory.rl.policies import HeuristicPolicy, RandomPolicy
from flow_memory.rl.registry import make_env

if __name__ == "__main__":
    heuristic=RLEvaluator().evaluate(make_env("economy_market", seed=1), HeuristicPolicy(), episodes=10)
    random=RLEvaluator().evaluate(make_env("economy_market", seed=1), RandomPolicy(seed=1), episodes=10)
    result={"ok": True, "env_id": "economy_market", "heuristic": heuristic, "random": random, "prototype_metric": heuristic.get("mean_reward",0) >= random.get("mean_reward",0)}
    out=Path("artifacts/rl/rl_economy_market_benchmark.json"); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(json.dumps(result, indent=2, sort_keys=True))
