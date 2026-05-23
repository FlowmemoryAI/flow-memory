"""CPU-safe tiny agent-policy smoke trainer."""

from __future__ import annotations

from pathlib import Path

from flow_memory.neural.agent.policy import TinyAgentPolicyNetwork
from flow_memory.neural.torch_optional import OptionalDependencyError, require_torch


def train_smoke(*, steps: int = 2, checkpoint_dir: str = ".flow_memory/neural_artifacts") -> dict[str, object]:
    try:
        torch = require_torch()
    except OptionalDependencyError as exc:
        return {"ok": False, "skipped": True, "reason": str(exc)}
    policy = TinyAgentPolicyNetwork()
    scores = []
    for index in range(steps):
        base = torch.ones(4) * (index + 1)
        score = policy.score(base, base * 0.5, base * 0.25, base * 0.75)
        scores.append(score.as_record())
    out = Path(checkpoint_dir)
    out.mkdir(parents=True, exist_ok=True)
    checkpoint = out / "tiny_agent_policy_smoke.pt"
    torch.save({"scores": scores}, checkpoint)
    return {"ok": True, "scores": scores, "checkpoint": str(checkpoint)}


if __name__ == "__main__":
    import json

    print(json.dumps(train_smoke(), indent=2))
