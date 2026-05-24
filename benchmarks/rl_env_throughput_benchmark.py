from __future__ import annotations

from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


import json, time
from pathlib import Path
from flow_memory.rl.policies import HeuristicPolicy
from flow_memory.rl.registry import make_env

if __name__ == "__main__":
    env=make_env("gridworld", seed=1)
    policy=HeuristicPolicy()
    steps=0
    start=time.perf_counter()
    for ep in range(100):
        obs=env.reset(ep)
        for _ in range(env.max_steps):
            step=env.step(policy.act(obs, env)); obs=step.observation; steps += 1
            if step.done: break
    elapsed=max(time.perf_counter()-start, 1e-9)
    result={"ok": True, "steps": steps, "steps_per_second": steps/elapsed}
    out=Path("artifacts/rl/rl_env_throughput_benchmark.json"); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(json.dumps(result, indent=2, sort_keys=True))
