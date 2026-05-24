"""Report dataclasses for local Flow Memory network runs."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class ScenarioReport:
    scenario: str
    ok: bool
    summary: str
    data: Mapping[str, Any] = field(default_factory=dict)

    def as_record(self) -> Mapping[str, Any]:
        return {"scenario": self.scenario, "ok": self.ok, "summary": self.summary, "data": dict(self.data)}


@dataclass(frozen=True)
class LocalNetworkReport:
    ok: bool
    scenarios: tuple[ScenarioReport, ...]
    topology: Mapping[str, Any]

    def as_record(self) -> Mapping[str, Any]:
        return {
            "ok": self.ok,
            "scenarios": tuple(report.as_record() for report in self.scenarios),
            "topology": dict(self.topology),
        }
