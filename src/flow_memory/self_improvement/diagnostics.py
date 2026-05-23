"""Local diagnostics for runtime and skill health."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class DiagnosticFinding:
    target_id: str
    severity: str
    message: str
    metadata: Mapping[str, object]


@dataclass
class DiagnosticsEngine:
    def inspect(self, target_id: str, health: Mapping[str, object]) -> tuple[DiagnosticFinding, ...]:
        findings: list[DiagnosticFinding] = []
        if health.get("ok") is False:
            findings.append(DiagnosticFinding(target_id, "high", "health check failed", dict(health)))
        if health.get("rate_limited") is True:
            findings.append(DiagnosticFinding(target_id, "medium", "provider or skill is rate limited", dict(health)))
        return tuple(findings)
