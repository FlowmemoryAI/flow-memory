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
    visual_events: tuple[Mapping[str, Any], ...] = ()
    visual_state: Mapping[str, Any] = field(default_factory=dict)

    def as_record(self) -> Mapping[str, Any]:
        record: dict[str, Any] = {
            "ok": self.ok,
            "scenarios": tuple(report.as_record() for report in self.scenarios),
            "topology": dict(self.topology),
        }
        if self.visual_events:
            record["visual_events"] = tuple(dict(event) for event in self.visual_events)
        if self.visual_state:
            record["visual_state"] = dict(self.visual_state)
        return record
