"""Offline reliability gauntlet runner for Flow Memory agents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from flow_memory.agents.scenarios import DEFAULT_SCENARIOS, ReliabilityScenario, ScenarioReport


@dataclass(frozen=True)
class ReliabilityGauntletResult:
    reports: tuple[ScenarioReport, ...]

    @property
    def passed(self) -> bool:
        return all(report.passed for report in self.reports)

    @property
    def scenario_count(self) -> int:
        return len(self.reports)

    def as_record(self) -> Mapping[str, Any]:
        return {
            "passed": self.passed,
            "scenario_count": self.scenario_count,
            "reports": [report.as_record() for report in self.reports],
        }


class ReliabilityGauntlet:
    def __init__(self, scenarios: Iterable[ReliabilityScenario] | None = None) -> None:
        self.scenarios = tuple(scenarios) if scenarios is not None else tuple(scenario() for scenario in DEFAULT_SCENARIOS)

    def run(self) -> ReliabilityGauntletResult:
        return ReliabilityGauntletResult(tuple(scenario.run() for scenario in self.scenarios))


def run_reliability_gauntlet() -> Mapping[str, Any]:
    return ReliabilityGauntlet().run().as_record()
