"""Minimal cognitive-loop smoke benchmark."""

from __future__ import annotations

from flow_memory import Agent


def run(iterations: int = 10) -> dict[str, float]:
    agent = Agent.create("bench")
    successes = 0
    surprises = []
    for idx in range(iterations):
        cycle = agent.run_cycle(f"Explore local environment iteration {idx} and report")
        successes += int(cycle.action_result.success)
        surprises.append(cycle.evaluation.surprise_score)
    return {
        "iterations": float(iterations),
        "success_rate": successes / iterations,
        "mean_surprise": sum(surprises) / iterations,
    }


if __name__ == "__main__":
    print(run())
