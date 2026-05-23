"""Local self-improvement health signals."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

DEGRADATION_FLAGS: frozenset[str] = frozenset(
    {
        "api_error",
        "stale_data",
        "rate_limited",
        "unsafe_action",
        "low_quality",
        "failed_test",
        "missing_dependency",
    }
)


@dataclass(frozen=True)
class HealthReport:
    """Snapshot of detected degradation flags and supporting evidence."""

    flags: frozenset[str] = frozenset()
    evidence: Mapping[str, str] = field(default_factory=dict)

    @property
    def degraded(self) -> bool:
        return bool(self.flags)

    def has(self, flag: str) -> bool:
        return flag in self.flags


@dataclass
class HealthMonitor:
    """Deterministic local detector for degradation conditions."""

    stale_after_seconds: float = 3600.0
    low_quality_threshold: float = 0.5

    def assess(
        self,
        *,
        api_errors: int = 0,
        data_age_seconds: float | None = None,
        rate_limited: bool = False,
        unsafe_actions: int = 0,
        quality_score: float | None = None,
        failed_tests: Sequence[str] = (),
        missing_dependencies: Sequence[str] = (),
    ) -> HealthReport:
        flags: set[str] = set()
        evidence: dict[str, str] = {}

        if api_errors > 0:
            flags.add("api_error")
            evidence["api_error"] = str(api_errors)

        if data_age_seconds is not None and data_age_seconds > self.stale_after_seconds:
            flags.add("stale_data")
            evidence["stale_data"] = str(data_age_seconds)

        if rate_limited:
            flags.add("rate_limited")
            evidence["rate_limited"] = "true"

        if unsafe_actions > 0:
            flags.add("unsafe_action")
            evidence["unsafe_action"] = str(unsafe_actions)

        if quality_score is not None and quality_score < self.low_quality_threshold:
            flags.add("low_quality")
            evidence["low_quality"] = str(quality_score)

        if failed_tests:
            flags.add("failed_test")
            evidence["failed_test"] = ",".join(failed_tests)

        if missing_dependencies:
            flags.add("missing_dependency")
            evidence["missing_dependency"] = ",".join(missing_dependencies)

        return HealthReport(flags=frozenset(flags), evidence=evidence)

    def from_flags(
        self,
        flags: Sequence[str],
        evidence: Mapping[str, str] | None = None,
    ) -> HealthReport:
        unknown = tuple(flag for flag in flags if flag not in DEGRADATION_FLAGS)
        if unknown:
            raise ValueError("unknown degradation flags: " + ", ".join(unknown))
        return HealthReport(flags=frozenset(flags), evidence=evidence or {})
