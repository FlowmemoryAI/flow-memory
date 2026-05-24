from __future__ import annotations

from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


import json
from pathlib import Path
from flow_memory.rl.policies import TabularQPolicy
from flow_memory.rl.registry import make_env
from flow_memory.rl.trainer import SimpleQLearningTrainer

if __name__ == "__main__":
    result=SimpleQLearningTrainer(make_env("safety_gate", seed=0), TabularQPolicy(epsilon=0.0)).train(episodes=30).as_record()
    result={"ok": True, **result}
    out=Path("artifacts/rl/rl_training_smoke_benchmark.json"); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(json.dumps(result, indent=2, sort_keys=True))
