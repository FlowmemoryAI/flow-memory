"""Self-improvement output evaluator."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class OutputScore:
    target_id: str
    score: float
    flags: tuple[str, ...] = ()


@dataclass
class SelfEvaluator:
    def score(self, target_id: str, output: object, expected_fields: tuple[str, ...] = ()) -> OutputScore:
        flags: list[str] = []
        value = str(output or "")
        score = 3.0 if value.strip() else 1.0
        if isinstance(output, Mapping):
            missing = [field for field in expected_fields if field not in output]
            if missing:
                flags.append("missing_fields")
                score -= 1.0
            else:
                score += 1.0
        if len(value) > 100:
            score += 1.0
        return OutputScore(target_id, max(1.0, min(5.0, score)), tuple(flags))
