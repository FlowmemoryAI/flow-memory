"""Tiny neural-style evaluator."""

from __future__ import annotations

from typing import Any

from flow_memory.neural.features import NeuralEvaluationResult


class TinyNeuralEvaluator:
    def evaluate(self, output: Any, *, policy_allowed: bool = True, surprise: float = 0.0, memory_hits: int = 0, economic_value: float = 0.0) -> NeuralEvaluationResult:
        text = repr(output)
        output_quality = min(1.0, 0.35 + len(text) / 400.0)
        policy_compliance = 1.0 if policy_allowed else 0.0
        novelty = max(0.0, min(1.0, surprise))
        memory_usefulness = min(1.0, memory_hits / 5.0)
        econ = min(1.0, economic_value / 10.0)
        return NeuralEvaluationResult(output_quality, policy_compliance, novelty, memory_usefulness, econ)
