"""Neural training status helpers for learning reports."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class NeuralTrainingStatus:
    available: bool
    backend: str
    status: str
    reason: str = ""

    def as_record(self) -> Mapping[str, Any]:
        return {"available": self.available, "backend": self.backend, "status": self.status, "reason": self.reason, "advisory_only": True}


def neural_training_status(backend: str = "tiny_torch") -> NeuralTrainingStatus:
    try:
        import torch  # type: ignore
    except Exception:
        return NeuralTrainingStatus(False, backend, "skipped", "torch is not installed")
    return NeuralTrainingStatus(True, backend, "available", f"torch {torch.__version__} import succeeded")
