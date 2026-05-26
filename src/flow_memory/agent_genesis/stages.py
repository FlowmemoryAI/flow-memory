"""Agent development stages."""
from __future__ import annotations

from typing import Any, Mapping

STAGES = ("seed", "awake", "apprentice", "specialist", "trusted", "mentor")


def calculate_stage(metrics: Mapping[str, Any]) -> str:
    if int(metrics.get("network_reuse_count", 0) or 0) > 0 and int(metrics.get("contributions_made", 0) or 0) > 0:
        return "mentor"
    if float(metrics.get("policy_compliance", 0.0) or 0.0) >= 0.95 and float(metrics.get("prediction_accuracy", 0.0) or 0.0) >= 0.75:
        return "trusted"
    if int(metrics.get("benchmarks_passed", 0) or 0) > 0:
        return "specialist"
    if int(metrics.get("lessons_learned", 0) or 0) > 0 or int(metrics.get("prediction_errors", 0) or 0) > 0:
        return "apprentice"
    if int(metrics.get("runs_completed", 0) or 0) > 0:
        return "awake"
    return "seed"


def stage_record(stage: str) -> Mapping[str, Any]:
    return {"stage": stage, "rank": STAGES.index(stage) if stage in STAGES else 0, "stages": STAGES}
