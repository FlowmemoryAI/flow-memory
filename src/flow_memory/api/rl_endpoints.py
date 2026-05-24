"""Flow Arena RL endpoint handlers for the local API router."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from flow_memory.rl.evaluator import RLEvaluator
from flow_memory.rl.policies import HeuristicPolicy, RandomPolicy, TabularQPolicy
from flow_memory.rl.registry import env_names, make_env
from flow_memory.rl.trainer import SimpleQLearningTrainer

ROOT = Path(__file__).resolve().parents[3]


def rl_envs() -> Mapping[str, Any]:
    return {"envs": env_names(), "default": "safety_gate"}


def rl_benchmarks(root: str | Path = ROOT) -> Mapping[str, Any]:
    artifact_dir = Path(root) / "artifacts" / "rl"
    results = []
    if artifact_dir.exists():
        for path in sorted(artifact_dir.glob("rl_*benchmark*.json")):
            results.append({"name": path.stem, "path": str(path.relative_to(root)), "bytes": path.stat().st_size})
    return {"benchmarks": tuple(results), "raw_artifacts_exposed": False}


def rl_evaluate(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    env_id = str(payload.get("env_id", "safety_gate"))
    policy_name = str(payload.get("policy", "heuristic"))
    episodes = int(payload.get("episodes", 5))
    if episodes < 1 or episodes > 100:
        raise ValueError("episodes must be 1..100")
    env = make_env(env_id)
    policy = _policy(policy_name)
    metrics = RLEvaluator().evaluate(env, policy, episodes=episodes)
    return {"ok": True, "env_id": env_id, "policy": policy_name, "metrics": metrics}


def rl_train_smoke(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    env_id = str(payload.get("env_id", "safety_gate"))
    episodes = int(payload.get("episodes", 20))
    if episodes < 1 or episodes > 200:
        raise ValueError("episodes must be 1..200")
    trainer = SimpleQLearningTrainer(make_env(env_id), TabularQPolicy(epsilon=0.05))
    result = trainer.train(episodes=episodes).as_record()
    return {"ok": True, "env_id": env_id, "policy": "tabular_q", "training": result, "local_only": True}


def write_rl_benchmark_snapshot(root: str | Path = ROOT) -> Mapping[str, Any]:
    root_path = Path(root)
    out = root_path / "artifacts" / "rl" / "api_rl_snapshot.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"envs": rl_envs(), "evaluation": rl_evaluate({"env_id": "safety_gate", "policy": "heuristic", "episodes": 3})}
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"ok": True, "path": str(out.relative_to(root_path))}


def _policy(name: str):
    if name == "random":
        return RandomPolicy(seed=0)
    if name in {"tabular", "tabular_q"}:
        return TabularQPolicy(epsilon=0.0)
    if name == "heuristic":
        return HeuristicPolicy()
    raise ValueError(f"unknown RL policy: {name}")
