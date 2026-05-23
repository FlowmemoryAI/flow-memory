"""Evaluation and surprise metrics."""

from __future__ import annotations

from dataclasses import dataclass

from flow_memory.core.types import ActionResult, Evaluation, Prediction


@dataclass
class SurpriseEvaluator:
    """Compares predicted confidence to observed execution result."""

    failure_penalty: float = 0.75

    def measure(self, prediction: Prediction, result: ActionResult) -> Evaluation:
        expected_success = prediction.confidence
        observed_success = 1.0 if result.success else 0.0
        surprise = abs(expected_success - observed_success)
        if not result.success:
            surprise += self.failure_penalty
        surprise = min(1.0, round(surprise, 4))
        return Evaluation(
            surprise_score=surprise,
            metrics={
                "expected_success": expected_success,
                "observed_success": observed_success,
                "result_error": result.error,
            },
        )
