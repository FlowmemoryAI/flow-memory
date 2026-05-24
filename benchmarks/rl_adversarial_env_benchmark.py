from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.rl.evaluator import RLEvaluator
from flow_memory.rl.policies import HeuristicPolicy, RandomPolicy
from flow_memory.rl.registry import make_env

ADVERSARIAL_ENVS = ("reputation_gaming", "sybil_risk", "colluding_verifier")


def run_adversarial_benchmark(*, episodes: int = 10) -> dict[str, object]:
    evaluator = RLEvaluator()
    results: dict[str, object] = {}
    for env_id in ADVERSARIAL_ENVS:
        random_metrics = evaluator.evaluate(make_env(env_id, seed=3), RandomPolicy(seed=3), episodes=episodes)
        heuristic_metrics = evaluator.evaluate(make_env(env_id, seed=3), HeuristicPolicy(), episodes=episodes)
        results[env_id] = {
            "random": random_metrics,
            "heuristic": heuristic_metrics,
            "heuristic_safer_than_random": float(heuristic_metrics.get("mean_safety_violation_rate", 0.0)) <= float(random_metrics.get("mean_safety_violation_rate", 0.0)),
            "heuristic_reward_delta": round(float(heuristic_metrics.get("mean_reward", 0.0)) - float(random_metrics.get("mean_reward", 0.0)), 6),
        }
    return {
        "ok": True,
        "episodes": episodes,
        "envs": ADVERSARIAL_ENVS,
        "results": results,
        "prototype_limitations": [
            "deterministic local abuse-pattern fixtures",
            "not a production Sybil or collusion detector",
            "not a PufferLib or CUDA throughput benchmark",
        ],
    }


if __name__ == "__main__":
    payload = run_adversarial_benchmark()
    out = ROOT / "artifacts" / "rl" / "rl_adversarial_env_benchmark.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
