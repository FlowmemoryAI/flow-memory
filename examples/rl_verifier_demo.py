from __future__ import annotations

from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


import json
from flow_memory.rl.evaluator import RLEvaluator
from flow_memory.rl.policies import HeuristicPolicy
from flow_memory.rl.registry import make_env

ENV_ID = 'verifier'

if __name__ == "__main__":
    env = make_env(ENV_ID, seed=7)
    report = RLEvaluator().evaluate(env, HeuristicPolicy(), episodes=3)
    print(json.dumps({"ok": True, "env_id": ENV_ID, "metrics": report}, indent=2, sort_keys=True))
