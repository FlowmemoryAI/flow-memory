"""Track before/after learning metrics for local agent improvement demos."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class ImprovementMetric:
    name: str
    before: float
    after: float
    higher_is_better: bool = True

    @property
    def improved(self) -> bool:
        return self.after >= self.before if self.higher_is_better else self.after <= self.before

    def as_record(self) -> Mapping[str, Any]:
        return {"name": self.name, "before": self.before, "after": self.after, "improved": self.improved, "higher_is_better": self.higher_is_better}


@dataclass
class ImprovementTracker:
    metrics: list[ImprovementMetric] = field(default_factory=list)

    def add(self, name: str, before: float, after: float, *, higher_is_better: bool = True) -> ImprovementMetric:
        metric = ImprovementMetric(name, before, after, higher_is_better)
        self.metrics.append(metric)
        return metric

    def summary(self) -> Mapping[str, Any]:
        return {"ok": all(metric.improved for metric in self.metrics), "metrics": tuple(metric.as_record() for metric in self.metrics)}
