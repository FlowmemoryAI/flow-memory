"""Local deterministic learning metadata for prediction error."""
from __future__ import annotations

import hashlib
from typing import Any, Mapping


def learning_update_from_experience(experience: Mapping[str, Any]) -> Mapping[str, Any]:
    error = float(dict(experience.get("prediction_error", {})).get("prediction_error", experience.get("prediction_error", 0.0)) or 0.0)
    before = _unit_hash(str(experience.get("experience_id", "")), "before", str(error))
    after = max(0.0, round(before * (1.0 - min(error, 1.0) * 0.35), 6))
    return {
        "performed": True,
        "mode": "local_deterministic",
        "learning_signal": "prediction_error",
        "loss_before": before,
        "loss_after": after,
        "prediction_error": round(error, 6),
        "raw_weights_written": False,
        "external_model_calls": False,
    }


def _unit_hash(*parts: str) -> float:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:12]
    return round(int(digest, 16) / float(0xFFFFFFFFFFFF), 6)
