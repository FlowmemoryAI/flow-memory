"""Evaluate the tiny neural stack on local synthetic data."""

from __future__ import annotations

from flow_memory.neural.training.train_agent_policy import train_smoke as train_agent_policy_smoke
from flow_memory.neural.training.train_tiny_dual_stream import train_smoke as train_dual_stream_smoke
from flow_memory.neural.training.train_world_model import train_smoke as train_world_model_smoke


def evaluate_stack() -> dict[str, object]:
    return {
        "dual_stream": train_dual_stream_smoke(steps=1),
        "world_model": train_world_model_smoke(steps=1),
        "agent_policy": train_agent_policy_smoke(steps=1),
    }


if __name__ == "__main__":
    import json

    print(json.dumps(evaluate_stack(), indent=2))
