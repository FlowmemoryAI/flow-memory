"""Agent autonomy modes and execution gating."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class AutonomyMode(str, Enum):
    MANUAL = "manual"
    SUPERVISED = "supervised"
    AUTONOMOUS_LOCAL = "autonomous_local"
    AUTONOMOUS_ECONOMIC = "autonomous_economic"
    DISABLED = "disabled"


_RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


@dataclass(frozen=True)
class AutonomyDecision:
    allowed: bool
    requires_approval: bool
    reason: str

    def as_record(self) -> Mapping[str, object]:
        return {"allowed": self.allowed, "requires_approval": self.requires_approval, "reason": self.reason}


def decide_autonomy(
    mode: str,
    *,
    risk_level: str = "low",
    economic_value: float = 0.0,
    max_spend: float = 0.0,
) -> AutonomyDecision:
    if mode == AutonomyMode.DISABLED.value:
        return AutonomyDecision(False, False, "agent disabled")
    if mode == AutonomyMode.MANUAL.value:
        return AutonomyDecision(False, True, "manual mode requires approval")
    if mode == AutonomyMode.SUPERVISED.value:
        if economic_value > 0 or _RISK_ORDER.get(risk_level, 3) >= _RISK_ORDER["high"]:
            return AutonomyDecision(False, True, "supervised mode requires approval for risky/economic action")
        return AutonomyDecision(True, False, "supervised safe local action")
    if mode == AutonomyMode.AUTONOMOUS_LOCAL.value:
        if economic_value > 0:
            return AutonomyDecision(False, True, "local autonomy requires approval for economic action")
        if _RISK_ORDER.get(risk_level, 3) >= _RISK_ORDER["high"]:
            return AutonomyDecision(False, True, "local autonomy requires approval for high risk")
        return AutonomyDecision(True, False, "autonomous local action")
    if mode == AutonomyMode.AUTONOMOUS_ECONOMIC.value:
        if economic_value > max_spend:
            return AutonomyDecision(False, True, "economic action exceeds risk budget")
        if _RISK_ORDER.get(risk_level, 3) >= _RISK_ORDER["critical"]:
            return AutonomyDecision(False, True, "critical risk requires approval")
        return AutonomyDecision(True, False, "economic action within risk budget")
    return AutonomyDecision(False, True, f"unknown autonomy mode: {mode}")
