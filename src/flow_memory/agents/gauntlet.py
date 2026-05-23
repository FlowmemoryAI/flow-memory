"""Public entry points for the deterministic local agent reliability gauntlet."""

from __future__ import annotations

from typing import Any, Mapping

from flow_memory.agents.reliability import ReliabilityGauntlet, ReliabilityGauntletResult, run_reliability_gauntlet
from flow_memory.agents.scenarios import DEFAULT_SCENARIOS, ScenarioReport


def run_offline_reliability_gauntlet() -> Mapping[str, Any]:
    return run_reliability_gauntlet()


__all__ = [
    "DEFAULT_SCENARIOS",
    "ReliabilityGauntlet",
    "ReliabilityGauntletResult",
    "ScenarioReport",
    "run_offline_reliability_gauntlet",
    "run_reliability_gauntlet",
]
