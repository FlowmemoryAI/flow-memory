from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from flow_memory.rl.evaluator import RLEvaluator
from flow_memory.rl.policies import HeuristicPolicy, RandomPolicy, TabularQPolicy
from flow_memory.rl.registry import make_env
from flow_memory.rl.trainer import SimpleQLearningTrainer


def compare_policies(env_id: str = "safety_gate", *, episodes: int = 20) -> dict[str, object]:
    evaluator = RLEvaluator()
    random_report = evaluator.evaluate(make_env(env_id, seed=1), RandomPolicy(seed=1), episodes=episodes)
    heuristic_report = evaluator.evaluate(make_env(env_id, seed=1), HeuristicPolicy(), episodes=episodes)
    q_policy = TabularQPolicy(epsilon=0.05, seed=2)
    training = SimpleQLearningTrainer(make_env(env_id, seed=2), q_policy).train(episodes=max(episodes, 20))
    q_report = evaluator.evaluate(make_env(env_id, seed=3), q_policy, episodes=episodes)
    best = max(
        ("random", random_report),
        ("heuristic", heuristic_report),
        ("tabular_q", q_report),
        key=lambda item: float(item[1].get("mean_reward", 0.0)),
    )[0]
    return {
        "ok": True,
        "env_id": env_id,
        "episodes": episodes,
        "random": random_report,
        "heuristic": heuristic_report,
        "tabular_q": q_report,
        "training": training.as_record(),
        "best_policy": best,
        "tabular_q_improved": training.improved,
    }


if __name__ == "__main__":
    result = compare_policies()
    out = ROOT / "artifacts" / "rl" / "rl_policy_comparison_benchmark.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
